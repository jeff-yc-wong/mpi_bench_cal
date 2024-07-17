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

class CalibrationLossEvaluator:
    def __init__(self, simulator: SMPISimulator, ground_truth: MPIGroundTruth, loss: Callable):
        self.simulator : SMPISimulator = simulator
        self.ground_truth : MPIGroundTruth = ground_truth
        # print("IN CalibrationLossEvaluator:", ground_truth)
        self.loss_function : Callable = loss

    def __call__(self, calibration: dict[str, sc.parameters.Value], stop_time: float):
        results = []

        # Run simulator for all known ground truth points
        # for benchmarks in self.ground_truth:
        #     # Get the ground-truth makespan (should contain makespan, Mbytes/sec, Messages/sec)
        #     # TODO: maybe store it as a panda dataframe?
        #     ground_truth_makespans = [get_makespan(benchmark) for benchmark in benchmarks]
        #     # Compute the average
        #     average_ground_truth_makespan = sum(ground_truth_makespans) / len(ground_truth_makespans)
        #     simulated_makespan, whatever = self.simulator((benchmark, calibration), stoptime=stop_time)
        #     results.append((simulated_makespan, average_ground_truth_makespan))

        # simulated_makespans, real_makespans = zip(*results)
        # return self.loss_function(simulated_makespans, real_makespans)
        return 0
    
    

class SMPISimulatorCalibrator:
    def __init__(self, algorithm: str, simulator: SMPISimulator, ground_truth: MPIGroundTruth, loss: Callable):
        self.algorithms = algorithm
        self.simulator = simulator
        self.ground_truth = ground_truth
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
        # Adding platform params
        calibrator.add_param("cpu_speed", sc.parameter.Linear(0, 20).format("%.2fGf"))
        calibrator.add_param("pcie_bw", sc.parameter.Linear(0, 16).format("%.2fGbps"))
        calibrator.add_param("pcie_lat", sc.parameter.Linear(0, 10).format("%.2fns"))
        calibrator.add_param("xbus_bw", sc.parameter.Linear(0, 64).format("%.2fGBps"))
        calibrator.add_param("xbus_lat", sc.parameter.Linear(0, 10).format("%.2fns"))
        calibrator.add_param("limiter_bw", sc.parameter.Linear(0, 100).format("%.2fGbps"))

        # Adding smpi params
        # bandwidth: 65472:0.940694;15424:0.697866;9376:0.58729;5776:1.08739;3484:0.77493;1426:0.608902;732:0.341987;257:0.338112;0:0.812084
        # TODO: separate each threshold to its own param for both bandwidth and latency?
        # should be called like so:
        # split into 9 parts
        # --cfg=network/bandwidth-factor:"65472:0.940694;15424:0.697866;9376:0.58729;5776:1.08739;3484:0.77493;1426:0.608902;732:0.341987;257:0.338112;0:0.812084"
        # calibrator.add_param("network/bandwidth-factor", sc.parameter.Linear(0, 10).format("%.2f"))
        
        #latency: 65472:11.6436; 15424:3.48845; 9376:2.59299; 5776:2.18796; 3484:1.88101; 1426:1.61075; 732:1.9503; 257:1.95341;0:2.01467
        # split into 9 parts
        # calibrator.add_param("network/latency-factor", sc.parameter.Linear(0, 100).format("%.2f"))

        # TODO: implement evaluator
        evaluator = CalibrationLossEvaluator(self.simulator, self.ground_truth, self.loss)

        # Define the coordinator for the calibrator, in this case it's a ThreadPool
        coordinator = sc.coordinators.ThreadPool(pool_size=num_threads)

        try:
          start_time = perf_counter()
          calibration, loss = calibrator.calibrate(evaluator, timelimit=time_limit, coordinator=coordinator)
          elapsed = int(perf_counter() - start_time)
          sys.stderr.write(f"Actually ran in {timedelta(seconds=elapsed)}\n")
          print("Calibrated Args: ")
          print(calibration)
          print("----------------")
          print(f"Loss: {loss}")
        except Exception as error:
          sys.stderr.write(str(type(error)))
          sys.stderr.write(f"Error while running experiments: {error}\n")
          sys.exit(1)

        return calibration, loss




