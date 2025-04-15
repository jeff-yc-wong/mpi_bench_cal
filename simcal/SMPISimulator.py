import sys
import ast
import os
import json
import glob
import re
import simcal as sc
from typing import List, Callable, Any
from pathlib import Path
import shutil
from time import perf_counter
from mpi_groundtruth import MPIGroundTruth
from Utils import average_explained_variance_error, max_explained_variance_error
from calibrate_flops import calibrate_hostspeed
import threading
import numpy as np

file_abs_path = Path(__file__).parent.absolute()

MPI_EXEC = Path(file_abs_path.parent / "bin").resolve()
summit = Path(file_abs_path / "Summit").resolve()

class SMPISimulator(sc.Simulator):

    def __init__(
        self, ground_truth, benchmark_parent, hostfile, threshold=0.0, time=0, 
        keep_tmp=False, byte_split=[], topology_template="config/6-racks-no-gpu-no-nvme.json",
        simple=False, loss_aggregator="mean", loss_function="average"
    ):
        super().__init__()
        self.hostfile = hostfile
        self.benchmark_parent = benchmark_parent
        self.threshold = threshold
        self.time = time
        self.ground_truth = ground_truth
        if loss_function == "max":
            self.loss_function = max_explained_variance_error
        elif loss_function == "average":
            self.loss_function = average_explained_variance_error
        else:
            raise Exception(f"Unknown loss function '{loss_function}'")
        if loss_aggregator == "average_agg":
            self.loss_aggregator = np.mean
        elif loss_aggregator == "max_agg":
            self.loss_aggregator = np.max
        else:
            raise Exception(f"Unknown loss aggregator '{loss_aggregator}'")
        # self.hostspeed = 6103515625
        self.hostspeed = calibrate_hostspeed()
        self.smpi_args = []
        self.best_loss = None
        self.best_result = None
        self.keep_tmp = keep_tmp
        self.topology_template = topology_template
        self.simple = simple # whether or not to use simple compute node
        self.lock = threading.Lock()

        # array to store byte split for network/latency-factor and network/bandwidth-factor
        self.byte_split = byte_split

        # Initialize the file to be empty
        with open("sim_stderr.txt", "w") as f:
            f.write("")

        with open("compile_stderr.txt", "w") as f:
            f.write("")

    def need_more_benchs(self, count, iterations, relstderr):
        # setting a minimum iteration of 10
        res = (count < iterations) and (
            (count < 10)
            or (self.threshold < 0.0)
            or (count < 2)
            or (relstderr >= self.threshold)
        )

        # print("DEBUG: need_more_benchs", count, iterations, relstderr, res)

        return res


    def compile_platform(self, env: sc.Environment, calibration: dict[str, sc.parameters.Value]):
        tmp_dir = env.tmp_dir()

        print(f"Creating temporary directory: {tmp_dir}", file=sys.stderr)
        
         # copy summit folder into tmpdir
        shutil.copytree(summit, tmp_dir / "Summit")

        template_node = summit / "config/node_config.json"
        template_topology = summit / self.topology_template

        # Parsing the calibration arguments to sort them into the correct dictionaries
        # Calibration Arguments consist of
        #   1. smpi arguments (passed into the wrapper executable)
        #   2. node arguments (node_config.json)
        #   3. topology arguments (topology.json)

        smpi_args = []

        with open(template_node, "r") as node_f, open(template_topology, "r") as topology_f:
            node = json.load(node_f)
            topology = json.load(topology_f)

            node_keys = node.keys()
            topology_keys = topology.keys()
            # latency_factor = []
            latency_split = {}
            latency_factor = {}
            # bandwidth_factor = []
            bandwidth_split = {}
            bandwidth_factor = {}

            if self.simple:
                topology["node_generator_cb"] = "simple_node"
                    
            for key, value in calibration.items():
                if "/" in key:
                    pattern = r"network/(latency|bandwidth)-factor(-split)?"

                    match = re.match(pattern, key)

                    if match:
                        is_split = bool(match.group(2))
                        index = int(key.split("_")[-1])

                        if is_split:
                            if match.group(1) == "latency":
                                latency_split[index] = value
                            elif match.group(1) == "bandwidth":
                                bandwidth_split[index] = value
                        else:
                            if match.group(1) == "latency":
                                latency_factor[index] = value
                            elif match.group(1) == "bandwidth":
                                bandwidth_factor[index] = value
                    else:
                        smpi_args.append(f"--cfg={key}:{value}")
                elif key in node_keys:
                    node[key] = value
                elif key in topology_keys:
                    topology[key] = value
                else:
                    print(f"Error: Calibration parameter with Key ({key}) is not valid")
                    exit() 

            if len(latency_factor) > 0:
                if len(latency_split) > 0:
                    assert len(latency_split) == len(latency_factor), "Byte split and latency factor must be the same length"
                    self.byte_split = [latency_split[i] for i in sorted(latency_split.keys())]
                else:
                    assert len(self.byte_split) == len(latency_factor), "Byte split and latency factor must be the same length"

                latency_factor = [f"{self.byte_split[i]}:{latency_factor[i]}" for i in range(len(latency_factor))]
                latency_factor = ";".join(latency_factor)
                # print(f"--cfg=network/latency-factor:\"{latency_factor}\"")
                smpi_args.append(f"--cfg=network/latency-factor:\"{latency_factor}\"")

            if len(bandwidth_factor) > 0:
                if len(bandwidth_split) > 0:
                    assert len(bandwidth_split) == len(bandwidth_factor), "Byte split and bandwidth factor must be the same length"
                    self.byte_split = [bandwidth_split[i] for i in sorted(bandwidth_split.keys())]
                else:
                    assert len(self.byte_split) == len(bandwidth_factor), "Byte split and bandwidth factor must be the same length"
                
                bandwidth_factor = [f"{self.byte_split[i]}:{bandwidth_factor[i]}" for i in range(len(bandwidth_factor))]
                bandwidth_factor = ";".join(bandwidth_factor)
                # print(f"--cfg=network/bandwidth-factor:\"{bandwidth_factor}\"")
                smpi_args.append(f"--cfg=network/bandwidth-factor:\"{bandwidth_factor}\"")
                    

            # writing out the new node_config parameters
            with open(tmp_dir / "node_config.json", "w") as f:
                json.dump(node, f, indent=4)

            # writing out the new topology parameters
            topology["name"] = "summit_temp"
            with open(tmp_dir / "topology.json", "w") as f:
                json.dump(topology, f, indent=4)

            self.smpi_args = smpi_args

        # Calling the summit platform generator
        platform_args = (
            [tmp_dir / "Summit/summit_generator.py"]
            + [tmp_dir / "node_config.json"]
            + [tmp_dir / "topology.json"]
        )

        _, std_err, exit_code = env.bash("python3", platform_args)

        with open("compile_stderr.txt", "a") as f:
            f.write(f"Std_err: {std_err}\n")
            f.write(f"Exit Code: {exit_code}\n")
            f.write(f"----------------\n")

        if exit_code:
            sys.stderr.write(
                f"Platform was unable to be built and has failed with exit code {exit_code}!\n\n{std_err}\n"
            )
            exit(1)

        return tmp_dir
    
    def split_list(self, lst, num_parts):
        avg = len(lst) // num_parts
        remainder = len(lst) % num_parts
        result = []
        start = 0

        for i in range(num_parts):
            extra = 1 if i < remainder else 0  # Distribute remainder
            result.append(lst[start:start + avg + extra])
            start += avg + extra

        return result


    def run_single_simulation(self, tmp_dir, benchmark, iterations, byte_size, thresholds=[]):
        executable = MPI_EXEC / self.benchmark_parent

        platform_file = tmp_dir / "summit_temp.so"

        if not platform_file.exists():
            sys.stderr.write("Platform file does not exist!\n")
            exit(1)


        if benchmark.startswith("Stencil2D"):
            benchmark = "Stencil2D"
        
        if benchmark.startswith("Stencil3D"):
            benchmark = "Stencil3D"

        cmd_args = [
            platform_file,
            self.hostfile,
            str(executable),
            benchmark,
            ','.join(thresholds),
            iterations,
            ','.join(map(str, byte_size)),
            "--log=root.threshold:error",
            f"--cfg=smpi/host-speed:{self.hostspeed}f",
            f"--cfg=smpi/coll-selector:\"ompi\"",
            *self.smpi_args
        ]

        error_file = open("sim_stderr.txt", "a")
        print_cmd_args = [str(i) for i in cmd_args]
        error_file.write(f"Command: wrapper_parallel {' '.join(print_cmd_args)}\n")
        error_file.flush()

        std_out, std_err, exit_code = sc.bash(
            MPI_EXEC / "wrapper_parallel", cmd_args, std_in=None
        )


        print(f"Std_err: \n{std_err}", file=error_file)

        final_results = [float(x) for x in std_out.strip().split(" ") if x != ""]

        return final_results

    def run(
        self, env: sc.Environment, calibration: dict[str, sc.parameters.Value]
    ) -> Any:
        calibration = {k: str(v) for k, v in calibration.items()}
        res = []
        my_env = sc.Environment()

        start_time = perf_counter()
        tmp_dir = self.compile_platform(my_env, calibration)

        count = 0

        losses = []

        split_arr = self.split_list(self.ground_truth[1], len(self.ground_truth[0]))

        for i in self.ground_truth[0]:
            # i[0] is the benchmark name
            # i[1] is the number of nodes
            # i[2] is the byte size
            # i[3] is the data
            thresholds = []
            byte_len = len(i[3])
            for byte_index in range(byte_len):
                data = self.ground_truth[1][count * byte_len + byte_index]
                std = np.std(data)
                mean = np.mean(data)

                threshold = round(std / mean , 2)

                if mean == 0 or threshold < 0.05:
                    threshold = 0.05

                threshold = str(threshold)

                thresholds.append(threshold)
            # print(thresholds)

            temp = self.run_single_simulation(tmp_dir, i[0], 10, i[3], thresholds)
            res.extend(temp)

            files = glob.glob('p2p_*.log')

            # Loop through and remove each file
            for file in files:
                try:
                    os.remove(file)
                except OSError as e:
                    print(f"Error: {file} : {e.strerror}")


            loss = self.loss_function(temp, split_arr[count])
            losses.append(loss)

            count += 1
            # print(f"Result for {i[0]}: {temp}")
        time_taken = perf_counter() - start_time
        
        loss_val = self.loss_aggregator(losses)

        log_output = {"calibration": calibration, "result": res, "loss": loss_val, "time": time_taken}

        print(f"Result: {log_output}", file=sys.stderr)
        print("----------------", file=sys.stderr)

        if not self.keep_tmp:
            my_env.cleanup()

        with self.lock:
            if self.best_loss is None or loss_val < self.best_loss:
                self.best_loss = loss_val
                self.best_result = res
        return loss_val

if __name__ == "__main__":
    import argparse
    # byte_sizes = [0,1,2,4,8,16,32,64,128,256,512,1024,2048,4096,8192,16384,32768,65536,131072,262144,524288,1048576,2097152,4194304]

    benchmarks = ["Birandom", "PingPing", "PingPong"]
    byte_sizes = [1024, 2048, 4096, 8192, 16384, 32768, 65536, 131072, 262144, 524288, 1048576, 2097152, 4194304]
    node_counts = [128]

    parser = argparse.ArgumentParser(description="Script to run the SMPI simulator")

    # byte_sizes is a list of integers separated by commas
    parser.add_argument("-top", "--topology_template", type=str, default="config/6-racks-no-gpu-no-nvme.json", help="Calibration file to use for topology") 
    parser.add_argument("-sc", "--simple", action="store_true", help="Use simple compute node")
    parser.add_argument("-s", "--split", default=[], type=lambda s: [int(item) for item in s.split(",")], help="Comma separated list og byte sizes to use for the split") 
    parser.add_argument("-lf", "--loss_function", default="average", choices=["max", "average"], type=str, help="The explained variance loss function to use (average, max)")
    parser.add_argument("-la", "--loss_aggregator", default="average_agg", choices=["max_agg", "average_agg"], type=str, help="The explained variance loss aggregator to use (average, max)")
    parser.add_argument("-hf", "--hostfile", type=str, default=file_abs_path / "data/hostfile.txt", help="Path to hostfile")  # Optional argument
    parser.add_argument("-b", "--benchmarks", default=benchmarks, type=lambda s: [item for item in s.split(",")], help="Comma separated list of benchmarks to use for calibration")
    parser.add_argument("-n", "--node_counts", default=node_counts, type=lambda s: [int(item) for item in s.split(",")], help="Comma separated list of node counts to use for calibration")
    parser.add_argument("-f", "--calibration_file", type=str, default="", help="Calibration file to use for calibration") 
    parser.add_argument("byte_sizes", nargs='?', default=byte_sizes, type=lambda s: [int(item) for item in s.split(",")], help="List of byte sizes to calibrate")  # Required

    # Parse the arguments
    args = parser.parse_args()

    benchmarks = args.benchmarks
    node_counts = args.node_counts
    byte_sizes = args.byte_sizes

    summit_ground_truth = MPIGroundTruth(file_abs_path.parent / "imb-summit.csv")
    summit_ground_truth.set_benchmark_parent("P2P")
    ground_truth_data = summit_ground_truth.get_ground_truth(
        benchmarks=benchmarks, node_counts=node_counts, byte_sizes=byte_sizes)

    print("Known Points: ", ground_truth_data[0])
    print("Data: ", ground_truth_data[1][0:10])
        
    smpi_sim = SMPISimulator(ground_truth_data,
        "IMB-P2P", args.hostfile, 0.05, 2, keep_tmp=True, byte_split=args.split, topology_template=args.topology_template,
        simple=args.simple, loss_aggregator=args.loss_aggregator, loss_function=args.loss_function
    )

    env = sc.Environment()

    calibration = {}
    
    if args.calibration_file: 
        try:
            with open(args.calibration_file, "r") as f:
                data = f.read()
                calibration = ast.literal_eval(data)
        except Exception as e:
            print(f"Error: can't open calibration file {{{args.calibration_file}}} - {e}")
    
    else:
        print("INFO: no calibration file provided, using default values")


    start_time = perf_counter()
    
    results = smpi_sim.run(env, calibration)

    env.cleanup()
