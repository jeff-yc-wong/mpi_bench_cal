import argparse
import pandas as pd
import pytimeparse

from GroundTruth import MPIGroundTruth
from SMPISimulator import SMPISimulator
from SMPISimulatorCalibrator import SMPISimulatorCalibrator

def main():    
    # Create the parser
    parser = argparse.ArgumentParser(description="Example script using argparse")

    # Add arguments
    # byte_sizes is a list of integers separated by commas
    parser.add_argument("byte_sizes", type=lambda s: [int(item) for item in s.split(",")], help="List of byte sizes to calibrate")  # Required
    parser.add_argument("--verbose", action="store_true", help="Enable verbose mode")  # Optional flag
    parser.add_argument("-a", "--algorithm", type=str, default="random", help="Algorithms to use for calibration (Default: random)")  # Optional argument
    parser.add_argument("-t", "--time_limit", type=str, default="3h", help="Time limit for calibration (Default: 3h)")  # Optional argument

    # Parse the arguments
    args = parser.parse_args()

    time_limit =  pytimeparse.parse(args.time_limit)

    summit_df = MPIGroundTruth("../imb-summit.csv") #NOTE: change

    summit_df.set_benchmark_parent("P2P")


    # TODO: clean up data filtering

    filtered_df = summit_df.get_ground_truth(
        node_count=128,
        metrics=[
            "benchmark",
            "node_count",
            "processes",
            "repetitions",
            "bytes",
            "Mbytes/sec",
            "remark",
        ]
    )
    
    # remove rows where remark isn't NaN
    filtered_df = filtered_df[pd.isnull(filtered_df["remark"])].reset_index(drop=True)

    filtered_df = filtered_df[filtered_df["benchmark"].isin(["PingPing", "PingPong", "Birandom"])]

    # filter by byte sizes
    filtered_df = filtered_df[filtered_df["bytes"].isin(args.byte_sizes)]

    scenario_df = filtered_df[["benchmark", "node_count", "processes", "bytes"]].drop_duplicates().reset_index(drop=True)
    scenario_df = scenario_df.sort_values(by=["benchmark", "node_count", "processes", "bytes"]).reset_index(drop=True)
    scenario_df["bytes"] = scenario_df["bytes"].astype(int)
    scenario_df = scenario_df.groupby(['benchmark', 'node_count', 'processes'])['bytes'].agg(list).reset_index()

    # check for stencil benchmarks
    is_stencil = scenario_df["benchmark"].str.contains("Stencil")

    # get test set of ground truth data that only contains non-stencil benchmarks
    test_df = scenario_df[~is_stencil].reset_index(drop=True)
    # get validation set of ground truth data that only contains stencil benchmarks
    validation_df = scenario_df[is_stencil].reset_index(drop=True)

    data_df = filtered_df[["benchmark", "node_count", "processes", "bytes", "Mbytes/sec"]].sort_values(by=["benchmark", "node_count", "processes", "bytes"]).reset_index(drop=True)
    data_df = data_df.groupby(['benchmark', 'node_count', 'processes', 'bytes'])['Mbytes/sec'].agg(list).reset_index()

    
    is_stencil = data_df["benchmark"].str.contains("Stencil")
    test_data_df = data_df[~is_stencil].reset_index(drop=True)
    validation_data_df = data_df[is_stencil].reset_index(drop=True)

    assert scenario_df["bytes"].apply(len).sum() == len(data_df["Mbytes/sec"])
    assert test_df["bytes"].apply(len).sum() == len(test_data_df["Mbytes/sec"])
    assert validation_df["bytes"].apply(len).sum() == len(validation_data_df["Mbytes/sec"])



    known_points = []
    for _, row in test_df.iterrows():
        known_points.append((row['benchmark'], row['node_count'], row['processes'], row['bytes']))

    data = list(test_data_df["Mbytes/sec"])

    ground_truth_data = (known_points, data)
    
    print(f"Known Points: {known_points}")
    print(f"GroundTruth: {data}")

    smpi_sim = SMPISimulator(
        ground_truth_data, "IMB-P2P", "../hostfile.txt", 0.05, 24
    )


    calibrator = SMPISimulatorCalibrator(
        args.algorithm, smpi_sim
    )

    calibrator.compute_calibration(time_limit, 1)

if __name__ == "__main__":
    main()
