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
    def __init__(self, algorithm: str, simulator: SMPISimulator):
        self.algorithm = algorithm
        self.simulator = simulator

    def compute_calibration(self, time_limit: float, num_threads: int):
        if self.algorithm == "grid":
            calibrator = sc.calibrators.Grid()
        elif self.algorithm == "random":
            calibrator = sc.calibrators.Random()
        elif self.algorithm == "gradient":
            calibrator = sc.calibrators.GradientDescent(0.01, 1)
        elif self.algorithm == "bo":
            calibrator = sc.calibrators.ScikitOptimizer(1000)
        else:
            raise Exception(f"Unknown calibration algorithm {self.algorithm}")
    
        
        # Adding platform params
        calibrator.add_param("cpu_speed", sc.parameter.Linear(20, 100).format("%.2fGf"))
        calibrator.add_param("pcie_bw", sc.parameter.Linear(16, 160).format("%.2fGBps"))
        calibrator.add_param("pcie_lat", sc.parameter.Linear(1, 30).format("%.2fns"))
        calibrator.add_param("xbus_bw", sc.parameter.Linear(20, 80).format("%.2fGBps"))
        calibrator.add_param("xbus_lat", sc.parameter.Linear(1, 30).format("%.2fns"))

        calibrator.add_param("latency", sc.parameter.Linear(1e-9, 1e-8).format("%.10f"))
        calibrator.add_param("bandwidth", sc.parameter.Linear(1e9, 100e9).format("%.2f"))
        calibrator.add_param("limiter_bw", sc.parameter.Linear(100, 10000).format("%.2fGbps"))

        print(calibrator._ordered_params)
        print(calibrator._categorical_params)


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
          print("----------------")
          sys.stderr.write(f"Actually ran in {timedelta(seconds=elapsed)}\n")
          for i in calibration:
            calibration[i] = str(calibration[i])
          with open("result.txt", "w") as f:
            print("Calibrated Args: ")
            print(calibration)
            print(f"Loss: {loss}")
            print("----------------")
            f.write("Calibrated Args: \n")
            f.write(str(calibration))
            f.write("\n")
            f.write(f"Loss: {loss}")
            f.write("\n")
            f.write("----------------\n")
            f.write(f"Best Result: {self.simulator.best_result}")
            f.write("\n")
        except Exception as error:
          sys.stderr.write(str(type(error)))
          sys.stderr.write(f"Error while running experiments: {error}\n")
          sys.exit(1)

        return calibration, loss
