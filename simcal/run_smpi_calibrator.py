import argparse
import pandas as pd

from GroundTruth import MPIGroundTruth
from SMPISimulator import SMPISimulator
from SMPISimulatorCalibrator import SMPISimulatorCalibrator


def parse_ground_truth(ground_truth, use_iqm=False):
    data = []
    temp_data = {}
    last_row_value = None

    for _, row in ground_truth.iterrows():
        if last_row_value is None or row["bytes"] < last_row_value:
            if temp_data:
                data.append(temp_data)
                temp_data = {}
        temp_data[int(row["bytes"])] = row["Mbytes/sec"]
        last_row_value = row["bytes"]

    if temp_data:
        data.append(temp_data)

    byte_sizes = sorted({key for sublist in data for key in sublist.keys()})

    mean_msg_speeds = {}

    for byte_size in byte_sizes:
        msg_speeds = sorted(
            [sublist[byte_size] for sublist in data if byte_size in sublist]
        )

        if not use_iqm:
            mean_msg_speeds[byte_size] = round(sum(msg_speeds) / len(msg_speeds), 2)
        else:
            # Calculating the interquartile mean (between 25th quartile and 75th qaurtile)
            quartile_range = len(msg_speeds) // 4
            sub_arr = msg_speeds[quartile_range:-quartile_range]
            mean_msg_speeds[byte_size] = round(sum(sub_arr) / len(sub_arr), 2)

    index_of_non_full_list = [
        i for i, sublist in enumerate(data) if len(sublist) < len(byte_sizes)
    ]

    for index in index_of_non_full_list:
        for byte_size in byte_sizes:
            if byte_size not in data[index]:
                data[index][byte_size] = mean_msg_speeds[byte_size]

    assert all(len(sublist) == len(byte_sizes) for sublist in data)

    data_arr = []

    for i, sublist in enumerate(data):
        # This sorts the dictionary by keys
        data[i] = dict(sorted(sublist.items()))
        data_arr.append(list(data[i].values()))

    assert len(data_arr) == len(data)

    return data_arr


def main():
    # TODO: use argparse to parse cmdline arguments for calibration
    # which should only be time-limit and algorithm and maybe benchmarks (all or singular benchmarks)

    summit_df = MPIGroundTruth("../imb-summit.csv") #NOTE: change

    summit_df.set_benchmark_parent("P2P")

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

    filtered_df = filtered_df[filtered_df["bytes"] == 4194304]

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
    
    #print(f"Known Points: {known_points}")
    #print(f"GroundTruth: {data}")

    smpi_sim = SMPISimulator(
        ground_truth_data, "IMB-P2P", "/home/wongy/calibration/mpi_bench_cal/hostfile.txt", 0.05, 24
    )


    calibrator = SMPISimulatorCalibrator(
        "random", smpi_sim
    )

    calibrator.compute_calibration(10800, 1)




if __name__ == "__main__":
    main()
