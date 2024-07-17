import argparse

from GroundTruth import MPIGroundTruth


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
        # This sorts the dictory by keys
        data[i] = dict(sorted(sublist.items()))
        data_arr.append(list(data[i].values()))

    assert len(data_arr) == len(data)

    return data_arr


def main():
    # TODO: use argparse to parse cmdline arguments for calibration
    # which should only be time-limit and algorithm and maybe benchmarks (all or singular benchmarks)

    summit_df = MPIGroundTruth("../imb-summit.csv")

    summit_df.set_benchmark_parent("P2P")

    filtered_df = summit_df.get_ground_truth(
        metrics=[
            "benchmark",
            "node_count",
            "processes",
            "bytes",
            "Mbytes/sec",
            "repetitions",
            "remark",
        ]
    )

    unique_df = filtered_df[["benchmark", "node_count", "processes"]].drop_duplicates()

    birandom_df = filtered_df[filtered_df["benchmark"] == "Birandom"].reset_index(
        drop=True
    )

    is_stencil = unique_df["benchmark"].str.contains("Stencil")
    test_df = unique_df[~is_stencil].reset_index(drop=True)
    validation_df = unique_df[is_stencil].reset_index(drop=True)

    print("Scenarios:")
    print(test_df)

    known_points = []
    for _, row in test_df.iterrows():
        df = summit_df.get_ground_truth(benchmark=row["benchmark"], node_count=row["node_count"], processes=row["processes"])
        known_points.append(((row["benchmark"], row["node_count"], row["processes"]), parse_ground_truth(df)))

    # assert all([len(sublist) == 24 for scenario in known_points for runs in scenario[1] for sublist in runs])

    for scenario in known_points[0:1]:
        for runs in scenario[1]:
            print(runs)
    # print("Validation points")
    # print(validation_points)

    # known_points = []

    # for _, row in test_df.iterrows():
    #     known_points.append((row['benchmark'], row['node_count'], row['processes']))

    # data = []

    # for x in known_points:
    #     data_df = filtered_df[(filtered_df['benchmark'] == x[0]) & (filtered_df['node_count'] == x[1]) & (filtered_df['processes'] == x[2])]
    #     point_data = []
    #     for _, row in data_df.iterrows():
    #         point_data.append((x, row['bytes'], row['Mbytes/sec'], row['repetitions']))

    #     data.append(point_data)

    # print(len(data), len(known_points))


if __name__ == "__main__":
    main()
