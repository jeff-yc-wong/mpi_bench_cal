import sys
import os
import json
import simcal as sc
from typing import List, Callable, Any
from pathlib import Path
import pandas as pd
import re
from math import sqrt
import numpy as np
from time import perf_counter
from GroundTruth import MPIGroundTruth
from Utils import explained_variance_error

MPI_EXEC = Path("/home/wongy/mpi_bench_cal/bin")
summit = Path("/home/wongy/mpi_bench_cal/Summit")
cwd = Path.cwd()

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

    def run_single_simulation(self, benchmark, iterations, calibration, byte_size):
        smpi_args_dict = {}
        node_args_dict = {}
        topology_args_dict = {}
        executable = MPI_EXEC / self.benchmark_parent
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
        template_node = "/home/wongy/mpi_bench_cal/Summit/config/node_config.json"
        template_topology = (
            "/home/wongy/mpi_bench_cal/Summit/config/6-racks-no-gpu-no-nvme.json"
        )

        with open(template_node, "r") as f:
            node = json.load(f)
            for key, value in node_args_dict.items():
                node[key] = str(value)

        with open("node_config.json", "w") as f:
            json.dump(node, f, indent=4)

        with open(template_topology, "r") as f:
            topology = json.load(f)
            topology["name"] = "summit_temp"
            for key, value in topology_args_dict.items():
                topology[key] = str(value)

        with open("topology.json", "w") as f:
            json.dump(topology, f, indent=4)

        # Calling the summit platform generator
        platform_args = (
            [summit / "summit_generator.py"]
            + [cwd / "node_config.json"]
            + [cwd / "topology.json"]
        )
        _, std_err, exit_code = sc.bash("python3", platform_args)
        if exit_code:
            sys.stderr.write(
                f"Platform was unable to be built and has failed with exit code {exit_code}!\n\n{std_err}\n"
            )
            exit(1)

        platform_file = cwd / "summit_temp.so"

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
            self.num_procs,
        ]

        std_out, std_err, exit_code = sc.bash(
            "/home/wongy/mpi_bench_cal/bin/wrapper_parallel", cmd_args, std_in=None
        )

        final_results = [float(x) for x in std_out.strip().split(" ") if x != ""]

        return final_results

    def run(
        self, env: sc.Environment, calibration: dict[str, sc.parameters.Value]
    ) -> Any:
        print("Running simulator with calibration: ", calibration)
        res = []
        for i in self.ground_truth[0]:
            temp = self.run_single_simulation(i[0], 10000, calibration, i[3])
            print(temp)
            res.append(temp)
        ret = self.loss_function(res, self.ground_truth[1])
        print("Loss: ", ret)
        return ret

        



if __name__ == "__main__":
    smpi_sim = SMPISimulator("ground_truth",
        "IMB-P2P", "/home/wongy/mpi_bench_cal/hostfile.txt", 0.05
    )

    start_time = perf_counter()
    result = smpi_sim.run_single_simulation("PingPing", 10, {}, "1,2,4,8,16,32,64,128,256,512,1024,2048,4096,8192,16384,32768,65536,131072,262144,524288,1048576,2097152,4194304")

    print(f"Result: {result}")

    print(f"Time taken: {perf_counter() - start_time}")
