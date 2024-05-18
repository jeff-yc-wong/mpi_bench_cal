#!/usr/bin/env python3
"""
ground truth is the underlying 4 dimensional function that should be good for hill climbing
The global minima should be ~f(5.0565,7.45987,2.281,1.187)=3.747108839074933
good ranges are x(0,5], y (0,8] ,z(0,10) and w(0,10)
there is an optional 5th parameter if you want to add an artificial delay to the simulation
"""
from math import sin, log
from sys import argv
from time import sleep

def ground_truth(x, y, z, w):
    return (0.1 * (x - 1) * (x - 2) * (x - 3) * (x - 6)
            - 0.01 * (y + 1) * (y - 3) * (y - 4) * (y - 5) * (y - 8) * (y - 5) * (-log(y))
            + 10 * sin(2 * z) / (z + 1)
            + 5 * sin(3 * w + 1) / (w + 1)
            + 20
            )


if __name__ == "__main__":
    x = float(argv[1])
    y = float(argv[2])
    z = float(argv[3])
    w = float(argv[4])
    print(f"f({x}, {y}, {z}, {w})=")
    if len(argv) > 5:
        sleep(float(argv[5]))
    print(str(
        ground_truth(x, y, z, w)
    ))
