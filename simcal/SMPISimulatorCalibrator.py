import json
import os
import sys
from time import perf_counter

import simcal
from sklearn.metrics import mean_squared_error as sklearn_mean_squared_error
from pathlib import Path
from typing import List, Callable, Any
import simcal as sc

import SMPISimulator

class CalibrationLossEvaluator:
    def __init__(self, simulator: SMPISimulator, ground_truth: List[List[str]], loss: Callable):
        self.simulator : SMPISimulator = simulator
        self.ground_truth : List[List[str]] = ground_truth
        # print("IN CONS:", ground_truth)
        self.loss_function : Callable = loss

#     def __call__(self, calibration: dict[str, sc.parameters.Value], stop_time: float):
#         results = []
# 
#         # Run simulator for all known ground truth points
#         for benchmarks in self.ground_truth:
#             # Get the ground-truth makespan (should contain makespan, Mbytes/sec, Messages/sec)
#             # TODO: maybe store it as a panda dataframe?
#             ground_truth_makespans = [get_makespan(benchmark) for benchmark in benchmarks]
#             # Compute the average
#             average_ground_truth_makespan = sum(ground_truth_makespans) / len(ground_truth_makespans)
#             # Run the simulation for the first benchmark only, since they are all the same
#             simulated_makespan, whatever = self.simulator((benchm, calibration), stoptime=stop_time)
#             results.append((simulated_makespan, average_ground_truth_makespan))
# 
#         simulated_makespans, real_makespans = zip(*results)
#         return self.loss_function(simulated_makespans, real_makespans)

class SMPISimulatorCalibrator:
    def __init__(self, algorithm: str, simulator: SMPISimulator, loss: Callable):
        self.algorithms = algorithm
        self.simulator = SMPISimulator
        self.loss = loss

    def compute_calibration(self, time_limit: float, num_threads: int):
        if self.algorithm == "grid":
            calibrator = sc.calibrators.Grid()
        elif self.algorithm == "random":
            calibrator = sc.calibrators.Random()
        elif self.algorithm == "gradient":
            calibrator = sc.calibrators.GradientDescent(0.001, 0.00001)
        else:
            raise Exception(f"Unknown calibration algorithm {self.algorithm}")
    
        
        # TODO: add params to calibrators
        # calibrator.add_param("a", sc.parameter.Linear(0, 20).format("%.2f"))
        # calibrator.add_param("b", sc.parameter.Linear(0, 8).format("%.2f"))
        # calibrator.add_param("c", sc.parameter.Linear(0, 10).format("%.2f"))
        # calibrator.add_param("d", sc.parameter.Linear(0, 6).format("%.2f"))

        # TODO: implement evaluator
        # evaluator = CalibrationLossEvaluator(self.simulator, <benchmarks?>,self.loss)
        
        coordinator = sc.coordinators.ThreadPool(pool_size=num_threads)


        # try:
        #   start_time = perf_counter()
        #   calibration, loss = calibrator.calibrate(evaluator, timelimit=time_limit, coordinator=coordinator)
        #   elapsed = int(time.perf_counter() - start)
        #   sys.stderr.write(f"Actually ran in {timedelta(seconds=elapsed)}\n")
        #   print("Calibrated Args: ")
        #   print(calibration)
        #   print("----------------")
        #   print(f"Loss: {loss}")
        # except Exception as error:
        #   sys.stderr.write(str(type(error)))
        #   sys.stderr.write(f"Error while running experiments: {error}\n")
        #   sys.exit(1)

        
        # return calibration, loss




