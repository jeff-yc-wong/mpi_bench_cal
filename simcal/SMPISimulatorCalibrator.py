import json
import os
import sys
import traceback
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
        elif self.algorithm == "skopt.gp":
            calibrator = sc.calibrators.ScikitOptimizer(10, "GP", 0)
        elif self.algorithm == "skopt.et":
            calibrator = sc.calibrators.ScikitOptimizer(10,"ET",0)
        elif self.algorithm == "skopt.rf":
            calibrator = sc.calibrators.ScikitOptimizer(10,"RF",0)
        elif self.algorithm == "skopt.gbrt":
            calibrator = sc.calibrators.ScikitOptimizer(10,"GBRT",0)
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
            # print(f"Error: The file '{self.param_file}' does not exist.")
            raise FileNotFoundError(f"Error: The file '{self.param_file}' does not exist.")
        except Exception as e:
            print(f"An error occurred while executing the file: {e}")

        coordinator = None

        try:
            start_time = perf_counter()
            calibration, loss = calibrator.calibrate(self.simulator, timelimit=time_limit, coordinator=coordinator)
            elapsed = int(perf_counter() - start_time)
            sys.stderr.write(f"Actually ran in {timedelta(seconds=elapsed)}\n----------------\n")
        except Exception as error:
            sys.stderr.write(f"Error while running experiments: {error}\n")
            if hasattr(error, 'exception'):
                sys.stderr.write(f"\n---------------\n")
                # If the error has an 'exception' attribute, use it
                e = error.exception
                traceback.print_exception(type(e), e, e.__traceback__)
                sys.exit(1)

        return calibration, loss
