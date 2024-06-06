#!/bin/bash

check_args() {
  if [ "$#" -ne 3 ]; then
    echo "Error: Exactly 3 arguments are required."
    echo "Usage: $0 <executable_name> <benchmark> <num_process>"
    exit 1
  fi
}

check_args "$@"

executable_name=$1
benchmark=$2
num_process=$3

smpirun -np $num_process -hostfile hostfile.txt -platform ./Summit-6-racks-no-gpu-no-nvme.so bin/$executable_name $benchmark
