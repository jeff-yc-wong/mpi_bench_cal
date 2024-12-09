import sys
import argparse
import pandas as pd
import pytimeparse
import logging
from pathlib import Path
from colorama import Fore, Style

from GroundTruth import MPIGroundTruth
from SMPISimulator import SMPISimulator
from SMPISimulatorCalibrator import SMPISimulatorCalibrator


# Define log level colors
LOG_COLORS = {
    "DEBUG": Fore.BLUE,
    "INFO": Fore.GREEN,
    "WARNING": Fore.YELLOW,
    "ERROR": Fore.RED,
    "CRITICAL": Fore.RED + Style.BRIGHT,
}

DATE_COLOR = Fore.CYAN

class ColorFormatter(logging.Formatter):
    def formatTime(self, record, datefmt=None):
        # Get the default formatted time
        formatted_time = super().formatTime(record, datefmt)
        # Apply color to the timestamp
        return f"{DATE_COLOR}{formatted_time}{Style.RESET_ALL}"
   
    def format(self, record):
       log_color = LOG_COLORS.get(record.levelname, "")
       reset = Style.RESET_ALL
       # Colorize only the level name
       record.levelname = f"{log_color}{record.levelname}{reset}"
       return super().format(record)


class InfoFilter(logging.Filter):
    def filter(self, rec):
        return rec.levelno in (logging.DEBUG, logging.INFO)

file_abs_path = Path(__file__).parent.absolute()

def main():
    # Create the parser
    parser = argparse.ArgumentParser(description="Example script using argparse")

    byte_sizes = [0, 1, 2, 4, 8, 16, 32, 64, 128, 256, 512, 1024, 2048, 4096, 8192, 16384, 32768, 65536, 131072, 262144, 524288, 1048576, 2097152, 4194304]

    benchmarks = ["Birandom", "PingPing", "PingPong"]

    # byte_sizes is a list of integers separated by commas
    parser.add_argument("byte_sizes", nargs='?', default=byte_sizes, type=lambda s: [int(item) for item in s.split(",")], help="List of byte sizes to calibrate")  # Required
    parser.add_argument("--verbose", action="store_true", help="Enable verbose mode")  # Optional flag
    parser.add_argument("-a", "--algorithm", type=str, default="random", help="Algorithms to use for calibration (Default: random)")  # Optional argument
    parser.add_argument("-t", "--time_limit", type=str, default="3h", help="Time limit for calibration (Default: 3h)")  # Optional argument
    parser.add_argument("-hf", "--hostfile", type=str, default=file_abs_path / "data/hostfile.txt", help="Path to hostfile")  # Optional argument
    parser.add_argument("-b", "--benchmarks", default=benchmarks, type=lambda s: [item for item in s.split(",")], help="Comma separated list of benchmarks to use for calibration")
    parser.add_argument("-d", "--debug", action='store_true', help="Enable debug messages")

    # Parse the arguments
    args = parser.parse_args()

    hostfile = Path(args.hostfile).resolve()

    if not hostfile.exists():
        print("Error: Hostfile does not exist", file=sys.stderr)
        exit(-1)

    time_limit =  pytimeparse.parse(args.time_limit)
    
    # Creating the logger's handlers
    stdout_handler = logging.StreamHandler(sys.stdout)
    stderr_handler = logging.StreamHandler(sys.stderr)

    file_handler = logging.FileHandler("result.log")

    # make it so that the file/stdout only contains info/debug messages
    info_filter = InfoFilter()
    stdout_handler.addFilter(info_filter)
    file_handler.addFilter(info_filter)

    # make it so that stderr only contains warning/error/critical messages
    stderr_handler.setLevel(logging.WARNING)

    # Setting the formatter of each handler
    color_formatter = ColorFormatter("[%(asctime)s] %(levelname)s: %(message)s (%(filename)s:%(lineno)d)")
    stdout_handler.setFormatter(color_formatter)
    stderr_handler.setFormatter(color_formatter)

    # Configure logging
    logging.basicConfig(
        level=args.debug if logging.DEBUG else logging.INFO,
        handlers=[
            stdout_handler,
            stderr_handler,
            file_handler
        ]
    )

    if args.debug:
        logging.debug("DEBUG MODE ENABLED")

    summit_df = MPIGroundTruth(file_abs_path / "data/imb-summit.csv") #NOTE: change

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

    filtered_df = filtered_df[filtered_df["benchmark"].isin(args.benchmarks)]

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
    print(f"GroundTruth: {data[0:10]}")
    print(f"Hostfile: {hostfile}")
    print(f"Time Limit: {args.time_limit} ({time_limit} seconds)")
    print("-----------------------------------------------------")
    smpi_sim = SMPISimulator(
        ground_truth_data, "IMB-P2P", hostfile, 0.05, 24
    )


    calibrator = SMPISimulatorCalibrator(
        args.algorithm, smpi_sim
    )

    calibrator.compute_calibration(time_limit, 1)

if __name__ == "__main__":
    main()
