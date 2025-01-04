import json
import os
import sys
from time import perf_counter
from datetime import timedelta


import simcal
from sklearn.metrics import mean_squared_error as sklearn_mean_squared_error
from pathlib import Path
from typing import List, Callable, Any
import simcal as sc

import SMPISimulator
from GroundTruth import MPIGroundTruth

class SMPISimulatorCalibrator:
    def __init__(self, algorithm: str, simulator: SMPISimulator, param_file: str):
        self.algorithm = algorithm
        self.simulator = simulator
        self.param_file = param_file

    def compute_calibration(self, time_limit: float, num_threads: int):
        if self.algorithm == "grid":
            calibrator = sc.calibrators.Grid()
        elif self.algorithm == "random":
            calibrator = sc.calibrators.Random()
        elif self.algorithm == "gradient":
            calibrator = sc.calibrators.GradientDescent(0.01, 1)
        elif self.algorithm == "bo":
            calibrator = sc.calibrators.BayesianOptimization(seed=0)
        else:
            raise Exception(f"Unknown calibration algorithm {self.algorithm}")
    
        
        # Adding platform params by reading in a txt file that should contain python code
        try:
            with open(self.param_file, 'r') as file:
                code = file.read()
                print(f"{code}")
                print("-----------------------------------------------------")
                # Execute the code in the current interpreter's context
                compile(code, self.param_file, 'exec')
                exec(code, globals(), locals())
        except FileNotFoundError:
            print(f"Error: The file '{self.param_file}' does not exist.")
        except Exception as e:
            print(f"An error occurred while executing the file: {e}")


        # Adding smpi params
        # should be called like so:
        # split into 9 parts
        # --cfg=network/bandwidth-factor:"65472:0.940694;15424:0.697866;9376:0.58729;5776:1.08739;3484:0.77493;1426:0.608902;732:0.341987;257:0.338112;0:0.812084"
        # calibrator.add_param("network/bandwidth-factor", sc.parameter.Linear(0, 10).format("%.2f"))
        
        #latency: 65472:11.6436; 15424:3.48845; 9376:2.59299; 5776:2.18796; 3484:1.88101; 1426:1.61075; 732:1.9503; 257:1.95341;0:2.01467
        # split into 9 parts
        # calibrator.add_param("network/latency-factor", sc.parameter.Linear(0, 100).format("%.2f"))

        # Define the coordinator for the calibrator, in this case it's a ThreadPool
        coordinator = sc.coordinators.ThreadPool(pool_size=num_threads)

        try:
            start_time = perf_counter()
            calibration, loss = calibrator.calibrate(self.simulator, timelimit=time_limit, coordinator=coordinator)
            elapsed = int(perf_counter() - start_time)
            sys.stderr.write(f"Actually ran in {timedelta(seconds=elapsed)}\n----------------\n")
        except Exception as error:
            sys.stderr.write(str(type(error)))
            sys.stderr.write(f"Error while running experiments: {error}\n")
            sys.exit(1)

        return calibration, loss
