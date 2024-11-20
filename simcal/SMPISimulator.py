import sys
import os
import json
import glob
import simcal as sc
from typing import List, Callable, Any
from pathlib import Path
import pandas as pd
import shutil
from math import sqrt
import numpy as np
from time import perf_counter
from GroundTruth import MPIGroundTruth
from Utils import explained_variance_error
from calibrate_flops import calibrate_hostspeed

MPI_EXEC = Path("../bin").resolve()
summit = Path("./Summit").resolve()

class SMPISimulator(sc.Simulator):

    def __init__(
        self, ground_truth, benchmark_parent, hostfile, threshold=0.0, num_procs=1, time=0
    ):
        super().__init__()
        self.hostfile = hostfile
        self.benchmark_parent = benchmark_parent
        self.threshold = threshold
        self.time = time
        self.ground_truth = ground_truth
        self.num_procs = num_procs
        self.loss_function = explained_variance_error
        self.hostspeed = calibrate_hostspeed()

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


    def compile_platform(self, env: sc.Environment):
        tmp_dir = env.tmp_dir()
        # copy summit folder into tmpdir
        shutil.copytree(summit, tmp_dir / "Summit")

        smpi_args_dict = {}
        node_args_dict = {}
        topology_args_dict = {}
        # iterations = 1 # NOTE: remove this line

        topology_config = ["bandwidth", "latency", "sharing_policy"]

        # Parsing the calibration arguments to sort them into the correct dictionaries
        # Calibration Arguments consist of
        #   1. smpi arguments (passed into the wrapper executable)
        #   2. node arguments (node_config.json)
        #   3. topology arguments (topology.json)

        # TODO: clean this up a bit
        for key, value in calibration.items():
            if "/" in key:
                smpi_args_dict[key] = value
            elif key in topology_config:
                topology_args_dict[key] = value
            else:
                node_args_dict[key] = value

        # parse the smpi_args_dict into cmd args for smpirun
        smpi_args = []
        for key, value in smpi_args_dict.items():
            smpi_args.append(f"--cfg={key}:{value}")

        # Rebuilding the platform .so file with the new node and topology configurations
        template_node = summit / "config/node_config.json"
        template_topology = summit / "config/6-racks-no-gpu-no-nvme.json"


        with open(template_node, "r") as f:
            node = json.load(f)
            for key, value in node_args_dict.items():
                node[key] = str(value)

        with open(tmp_dir / "node_config.json", "w") as f:
            json.dump(node, f, indent=4)

        with open(template_topology, "r") as f:
            topology = json.load(f)
            topology["name"] = "summit_temp"
            for key, value in topology_args_dict.items():
                topology[key] = str(value)

        with open(tmp_dir / "topology.json", "w") as f:
            json.dump(topology, f, indent=4)

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


    def run_single_simulation(self, tmp_dir, benchmark, iterations, calibration, byte_size):
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

        error_file = open("error.log", "a")

        print(f"Std_err: \n{std_err}", file=error_file)

        final_results = [float(x) for x in std_out.strip().split(" ") if x != ""]

        return final_results

    def run(
        self, env: sc.Environment, calibration: dict[str, sc.parameters.Value]
    ) -> Any:
        print("Running simulator with calibration: ", calibration)
        res = []
        start_time = perf_counter()

        tmp_dir = self.compile_platform(env)

        for i in self.ground_truth[0]:
            # print("Running simulation on groundtruth: ", i[0])
            temp = self.run_single_simulation(tmp_dir, i[0], 10000, calibration, i[3])
            res.extend(temp)

            files = glob.glob('p2p_*.log')

            # Loop through and remove each file
            for file in files:
                try:
                    os.remove(file)
                except OSError as e:
                    print(f"Error: {file} : {e.strerror}")

            # print(f"Result for {i[0]}: {temp}")
        print("-----------", file=sys.stderr)
        print(f"Result: \n{res}\n", file=sys.stderr)
        ret = self.loss_function(res, self.ground_truth[1])
        print("Loss: ", ret)
        print(f"Time taken: {perf_counter() - start_time}")
        
        return ret

if __name__ == "__main__":
    # byte_sizes = [0,1,2,4,8,16,32,64,128,256,512,1024,2048,4096,8192,16384,32768,65536,131072,262144,524288,1048576,2097152,4194304]

    byte_sizes = [4194304]

    known_points = [
        ("Birandom", 128, 768, byte_sizes),
        ("PingPing", 128, 768, byte_sizes),
        ("PingPong", 128, 768, byte_sizes)
    ]

    data = np.random.rand(len(known_points) * len(byte_sizes),  5).tolist()

    ground_truth_data = (known_points, data)
        
    smpi_sim = SMPISimulator(ground_truth_data,
        "IMB-P2P", Path("../hostfile.txt").resolve(), 0.05, 24
    )

    env = sc.Environment()

    calibration = {'cpu_speed': '86.85Gf', 'pcie_bw': '145.80Gbps', 'pcie_lat': '16.45ns', 'xbus_bw': '68.54GBps', 'xbus_lat': '11.28ns', 'limiter_bw': '13558.34Gbps', 'latency': '0.0000000030', 'bandwidth': '4375934687030.83'}
#    calibration = {'cpu_speed': '91.81Gf', 'pcie_bw': '133.79Gbps', 'pcie_lat': '15.93ns', 'xbus_bw': '62.72GBps', 'xbus_lat': '5.29ns', 'limiter_bw': '6519.06Gbps', 'latency': '0.0000000081', 'bandwidth': '166664948515.11'}
    start_time = perf_counter()
    
    results = smpi_sim.run(env, calibration)

    print(f"Result: {results}")

    print(f"Time taken: {perf_counter() - start_time}")
