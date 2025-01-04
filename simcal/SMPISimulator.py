import sys
import ast
import os
import json
import glob
import simcal as sc
from typing import List, Callable, Any
from pathlib import Path
import shutil
from time import perf_counter
from mpi_groundtruth import MPIGroundTruth
from Utils import explained_variance_error
from calibrate_flops import calibrate_hostspeed

file_abs_path = Path(__file__).parent.absolute()

MPI_EXEC = Path(file_abs_path.parent / "bin").resolve()
summit = Path(file_abs_path / "Summit").resolve()

class SMPISimulator(sc.Simulator):

    def __init__(
        self, ground_truth, benchmark_parent, hostfile, threshold=0.0, num_procs=1, time=0, keep_tmp=False
    ):
        super().__init__()
        self.hostfile = hostfile
        self.benchmark_parent = benchmark_parent
        self.threshold = threshold
        self.time = time
        self.ground_truth = ground_truth
        self.num_procs = num_procs
        self.loss_function = explained_variance_error
        self.hostspeed = 5.2e9
        #self.hostspeed = calibrate_hostspeed()
        self.smpi_args = []
        self.best_loss = None
        self.best_result = None
        self.keep_tmp = keep_tmp

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
        template_topology = summit / "config/6-racks-no-gpu-no-nvme.json"

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

            for key, value in calibration.items():
                if "/" in key:
                    smpi_args.append(f"--cfg={key}:{value}")
                elif key in node_keys:
                    node[key] = value
                elif key in topology_keys:
                    topology[key] = value
                else:
                    print(f"Error: Calibration parameter with Key ({key}) is not valid")
                    exit() 

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

        if exit_code:
            sys.stderr.write(
                f"Platform was unable to be built and has failed with exit code {exit_code}!\n\n{std_err}\n"
            )
            exit(1)

        return tmp_dir


    def run_single_simulation(self, tmp_dir, benchmark, iterations, byte_size):
        executable = MPI_EXEC / self.benchmark_parent

        platform_file = tmp_dir / "summit_temp.so"

        if not platform_file.exists():
            sys.stderr.write("Platform file does not exist!\n")
            exit(1)

        cmd_args = [
            platform_file,
            self.hostfile,
            str(executable),
            benchmark,
            self.threshold,
            iterations,
            ','.join(map(str, byte_size)),
            "--log=root.threshold:error",
            f"--cfg=smpi/host-speed:{self.hostspeed}f"
        ]

        std_out, std_err, exit_code = sc.bash(
            MPI_EXEC / "wrapper_parallel", cmd_args, std_in=None
        )

        error_file = open("sim_stderr.txt", "a")

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

        for i in self.ground_truth[0]:
            temp = self.run_single_simulation(tmp_dir, i[0], 100, i[3])
            res.extend(temp)

            files = glob.glob('p2p_*.log')

            # Loop through and remove each file
            for file in files:
                try:
                    os.remove(file)
                except OSError as e:
                    print(f"Error: {file} : {e.strerror}")

            # print(f"Result for {i[0]}: {temp}")
        time_taken = perf_counter() - start_time
        loss_val = self.loss_function(res, self.ground_truth[1])
        log_output = {"calibration": calibration, "result": res, "loss": loss_val, "time": time_taken}

        print(f"Result: {log_output}", file=sys.stderr)
        print("----------------", file=sys.stderr)

        if not self.keep_tmp:
            my_env.cleanup()
        

        if self.best_loss is None or loss_val < self.best_loss:
            self.best_loss = loss_val
            self.best_result = res
        return loss_val

if __name__ == "__main__":
    import argparse
    # byte_sizes = [0,1,2,4,8,16,32,64,128,256,512,1024,2048,4096,8192,16384,32768,65536,131072,262144,524288,1048576,2097152,4194304]

    benchmarks = ["Birandom", "PingPing", "PingPong"]
    byte_sizes = [0, 1, 2, 4, 8, 16, 32, 64, 128, 256, 512, 1024, 2048, 4096, 8192, 16384, 32768, 65536, 131072, 262144, 524288, 1048576, 2097152, 4194304]
    node_counts = [128]

    parser = argparse.ArgumentParser(description="Script to run the SMPI simulator")

    # byte_sizes is a list of integers separated by commas
    parser.add_argument("byte_sizes", nargs='?', default=byte_sizes, type=lambda s: [int(item) for item in s.split(",")], help="List of byte sizes to calibrate")  # Required
    parser.add_argument("-hf", "--hostfile", type=str, default=file_abs_path / "data/hostfile.txt", help="Path to hostfile")  # Optional argument
    parser.add_argument("-b", "--benchmarks", default=benchmarks, type=lambda s: [item for item in s.split(",")], help="Comma separated list of benchmarks to use for calibration")
    parser.add_argument("-n", "--node_counts", default=node_counts, type=lambda s: [int(item) for item in s.split(",")], help="Comma separated list of node counts to use for calibration")
    parser.add_argument("-f", "--calibration_file", type=str, default="", help="Calibration file to use for calibration") 
    # Parse the arguments
    args = parser.parse_args()

    benchmarks = args.benchmarks
    node_counts = args.node_counts
    byte_sizes = args.byte_sizes

    summit_ground_truth = MPIGroundTruth("../imb-summit.csv")
    summit_ground_truth.set_benchmark_parent("P2P")
    ground_truth_data = summit_ground_truth.get_ground_truth(
        benchmarks=benchmarks, node_counts=node_counts, byte_sizes=byte_sizes)

    print("Known Points: ", ground_truth_data[0])
    print("Data: ", ground_truth_data[1])
        
    smpi_sim = SMPISimulator(ground_truth_data,
        "IMB-P2P", args.hostfile, 0.05, 2, keep_tmp=True
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
