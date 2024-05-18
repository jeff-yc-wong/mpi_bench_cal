#!/usr/bin/env python3
import os
from pathlib import Path
from time import time
import numpy as np
from sklearn.metrics import mean_squared_error as sklearn_mean_squared_error

import simcal as sc
from groundtruth import ground_truth

cwd = Path(os.path.dirname(os.path.realpath(__file__)))  # Get path to THIS folder where the simulator lives

def parse_output(std_out):
    # TODO: parse the output from the IMB executables, maybe as a csv format (maybe also a function to print the csv as a table)
    pass

class SMPISimulator(sc.Simulator):

    def __init__(self, time=0):
        super().__init__()
        self.time = time

    def run(self, env, args):
        # Question: will we be changing the topology of the system
        # TODO: generate new node_config.json to feed into summit_generator
        # args[0]: node parameters (needs to generate a new json)
        # args[1]: topology of the platform (maybe constant)
        cmdargs_platform = [cwd / "Summit" / "summit_generator.py"] + list(args[0]) + list(args[1])
        # TODO: given the platform parameters, run summit_generator.py to generate new .so platform file
        std_out, std_err, exit_code = sc.bash("python3", cmdargs_platform)
        # TODO: take an input of what benchmark program (Ex. IMB-MP1, IMB-NBC) to run and what mode (Ex. PingPong, PingPing)to run it in
        # TODO: run the smpi with the arguments
        # Question: should i wrap smpirun in here or in another python file?
        raise NotImplementedError()
        cmdargs = 
        std_out, std_err, exit_code = sc.bash("smpirun", cmdargs)

        if std_err:
            print(std_out, std_err, exit_code)

        return parse_output(std_out)
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
        ret = self.loss_function(res, self.ground_truth[1])
        print("loss: ", ret)
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

# print(ground_truth_data)
# Defining the loss function
my_loss = sklearn_mean_squared_error



simulator = ExampleSimulator()
scenario1 = Scenario(simulator, ground_truth_data, my_loss)

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
print("final calibration")
print(calibration)
print(loss)
print(time() - start)



