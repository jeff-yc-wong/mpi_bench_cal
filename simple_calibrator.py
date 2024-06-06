#!/usr/bin/env python3
import os
from pathlib import Path
from time import time

from sklearn.metrics import mean_squared_error as sklearn_mean_squared_error

import simcal as sc
from groundtruth import ground_truth

simple_sim = Path(os.path.dirname(os.path.realpath(__file__)))  # Get path to THIS folder where the simulator lives


class ExampleSimulator(sc.Simulator):

    def __init__(self, time=0):
        super().__init__()
        self.time = time

    def run(self, env, args):
        cmdargs = [simple_sim / "simple_simulator.py"] + list(args[0]) + list(args[1]) + [self.time]
        std_out, std_err, exit_code = sc.bash("python3", cmdargs, )
        if std_err:
            print(std_out, std_err, exit_code)
        return float(std_out.strip().split("\n")[-1])


class Scenario:
    def __init__(self, simulator, ground_truth, loss):
        self.simulator = simulator
        self.ground_truth = ground_truth
        self.loss_function = loss

    def __call__(self, calibration, stop_time):
        unpacked = (calibration["a"], calibration["b"], calibration["c"], calibration["d"])
        res = []
        # Run simulator for all known ground truth points
        print(calibration)
        for x in self.ground_truth[0]:
            res.append(self.simulator((x, unpacked), stoptime=stop_time))
        print("Simulation Data:", len(res))
        print("Groundtruth Data:", len(self.ground_truth[1]))
        ret = self.loss_function(res, self.ground_truth[1])
        print(ret)
        return ret


# make some fake evaluation scenarios for the example
known_points = []
for x in (1.39904, 254441, 5.05656):
    for y in (1.1558, 3.384, 40395, 7.36):
        for z in (0.637, 2.281, 3.876, 5.459, 7.038):
            for w in (0.448, 1.527, 2.587, 3.641, 4.693, 5.743):
                known_points.append((x, y, z, w))

# get ground truth data the fake scenarios
data = []
for x in known_points:
    data.append(ground_truth(*x))
ground_truth_data = [known_points, data]

loss = sklearn_mean_squared_error

simulator = ExampleSimulator()
scenario1 = Scenario(simulator, ground_truth_data, loss)

# prepare the calibrator and setup the arguments to calibrate with their ranges
# calibrator = sc.calibrators.Grid()
# calibrator = sc.calibrators.Random()
calibrator = sc.calibrators.GradientDescent(0.01, 1)

calibrator.add_param("a", sc.parameter.Linear(0, 20).format("%.2f"))
calibrator.add_param("b", sc.parameter.Linear(0, 8).format("%.2f"))
calibrator.add_param("c", sc.parameter.Linear(0, 10).format("%.2f"))
calibrator.add_param("d", sc.parameter.Linear(0, 6).format("%.2f"))

coordinator = sc.coordinators.ThreadPool(pool_size=4)  # Making a coordinator is optional, and only needed if you
# wish to run multiple simulations at once, possibly using multiple cpu cores or multiple compute nodes
start = time()
calibration, loss = calibrator.calibrate(scenario1, timelimit=10, coordinator=coordinator)
print("final calibration?")
print(calibration)
print(loss)
print(time() - start)
