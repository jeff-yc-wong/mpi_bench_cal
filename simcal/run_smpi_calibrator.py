import sys
import json
import re
import pprint
import argparse
import pytimeparse
# import logging
from pathlib import Path
# from colorama import Fore, Style

from SMPISimulator import SMPISimulator
from SMPISimulatorCalibrator import SMPISimulatorCalibrator
from mpi_groundtruth import MPIGroundTruth


class CustomJSONEncoder(json.JSONEncoder):
    def __init__(self, *args, **kwargs):
        self.indentation_level = 0  # Initialize the indentation level
        super().__init__(*args, **kwargs)

    def encode(self, obj):
        """Override encode method to track indentation level."""
        if isinstance(obj, list):
            # Increase indentation for arrays
            self.indentation_level += 1
            result = '[' + ', '.join(self.encode(el) for el in obj) + ']'
            self.indentation_level -= 1
            return result
        elif isinstance(obj, dict):
            result = '{}'

            if len(obj) != 0:
                # Increase indentation for objects
                self.indentation_level += 1
                items = [f'{json.dumps(k)}: {self.encode(v)}' for k, v in obj.items()]
                result = '{\n' + ',\n'.join('    ' * self.indentation_level + item for item in items)
                self.indentation_level -= 1
                result += '\n' + '    ' * self.indentation_level + '}'

            return result
        elif isinstance(obj, bool):
            return str(obj)
        else:
            # Default encoding for other types
            return super().encode(obj)  


# Define log level colors
# LOG_COLORS = {
#     "DEBUG": Fore.BLUE,
#     "INFO": Fore.GREEN,
#     "WARNING": Fore.YELLOW,
#     "ERROR": Fore.RED,
#     "CRITICAL": Fore.RED + Style.BRIGHT,
# }

# DATE_COLOR = Fore.CYAN

# class ColorFormatter(logging.Formatter):
#     def formatTime(self, record, datefmt=None):
#         # Get the default formatted time
#         formatted_time = super().formatTime(record, datefmt)
#         # Apply color to the timestamp
#         return f"{DATE_COLOR}{formatted_time}{Style.RESET_ALL}"
   
#     def format(self, record):
#        log_color = LOG_COLORS.get(record.levelname, "")
#        reset = Style.RESET_ALL
#        # Colorize only the level name
#        record.levelname = f"{log_color}{record.levelname}{reset}"
#        return super().format(record)


# class InfoFilter(logging.Filter):
#     def filter(self, rec):
#         return rec.levelno in (logging.DEBUG, logging.INFO)

file_abs_path = Path(__file__).parent.absolute()

def main():
    # Create the parser
    parser = argparse.ArgumentParser(description="Script to run the SMPI calibrator")

    byte_sizes = [0, 1, 2, 4, 8, 16, 32, 64, 128, 256, 512, 1024, 2048, 4096, 8192, 16384, 32768, 65536, 131072, 262144, 524288, 1048576, 2097152, 4194304]

    benchmarks = ["Birandom", "PingPing", "PingPong"]
    
    node_counts = [128]

    # SIMULATOR PARAMETERS
    parser.add_argument("-top", "--topology", default="config/6-racks-no-gpu-no-nvme.json", type=str, help="Topology of the cluster in the form of a config json file")
    parser.add_argument("-sc", "--simple_compute", action='store_true', help="Whether to use simple compute nodes")
    parser.add_argument("-s", "--split", default=None, type=lambda s: [int(item) for item in s.split(",")], help="Comma separated list of splits to use for latency/bandwidth factor")
    parser.add_argument("-lf", "--loss_function", default="average", choices=["max", "average"], type=str, help="The explained variance loss function to use (average, max)")
    parser.add_argument("-la", "--loss_aggregator", default="average_agg", choices=["max_agg", "average_agg"], type=str, help="The explained variance loss aggregator to use (average, max)")
    parser.add_argument("-hf", "--hostfile", type=str, default=file_abs_path / "data/hostfile.txt", help="Path to hostfile")  # Optional argument
    parser.add_argument("-b", "--benchmarks", default=benchmarks, type=lambda s: [item for item in s.split(",")], help="Comma separated list of benchmarks to use for calibration")
    parser.add_argument("-n", "--node_counts", default=node_counts, type=lambda s: [int(item) for item in s.split(",")], help="Comma separated list of node counts to use for calibration")

    # CALIBRATOR PARAMETERS
    parser.add_argument("-a", "--algorithm", type=str, default="random", help="Algorithms to use for calibration (Default: random)")  # Optional argument
    parser.add_argument("-t", "--time_limit", type=str, default="3h", help="Time limit for calibration (Default: 3h)")  # Optional argument
    parser.add_argument("-d", "--debug", action='store_true', help="Enable debug messages")
    parser.add_argument("-p", "--param_file", type=str, default=file_abs_path / "data/params.txt", help="Path to parameter file")
    
    parser.add_argument("byte_sizes", nargs='?', default=byte_sizes, type=lambda s: [int(item) for item in s.split(",")], help="List of byte sizes to calibrate")  # Required
    parser.add_argument("--verbose", action="store_true", help="Enable verbose mode")  # Optional flag

    # Parse the arguments
    args = parser.parse_args()

    hostfile = Path(args.hostfile).resolve()

    if not hostfile.exists():
        print("Error: Hostfile does not exist", file=sys.stderr)
        exit(-1)

    time_limit =  pytimeparse.parse(args.time_limit)
    
    # # Creating the logger's handlers
    # stdout_handler = logging.StreamHandler(sys.stdout)
    # stderr_handler = logging.StreamHandler(sys.stderr)

    # file_handler = logging.FileHandler("result.log")

    # # make it so that the file/stdout only contains info/debug messages
    # info_filter = InfoFilter()
    # stdout_handler.addFilter(info_filter)
    # file_handler.addFilter(info_filter)

    # # make it so that stderr only contains warning/error/critical messages
    # stderr_handler.setLevel(logging.WARNING)

    # # Setting the formatter of each handler
    # color_formatter = ColorFormatter("[%(asctime)s] %(levelname)s: %(message)s (%(filename)s:%(lineno)d)")
    # stdout_handler.setFormatter(color_formatter)
    # stderr_handler.setFormatter(color_formatter)

    # # Configure logging
    # logging.basicConfig(
    #     level=args.debug if logging.DEBUG else logging.INFO,
    #     handlers=[
    #         stdout_handler,
    #         stderr_handler,
    #         file_handler
    #     ]
    # )

    # if args.debug:
    #     logging.debug("DEBUG MODE ENABLED")

    summit_df = MPIGroundTruth(file_abs_path / "data/imb-summit.csv") #NOTE: change

    summit_df.set_benchmark_parent("P2P")

    ground_truth_data = summit_df.get_ground_truth(benchmarks=args.benchmarks, byte_sizes=args.byte_sizes, node_counts=args.node_counts)

    json_obj = {"config": {}, "results": {}}
    
    config_json = {
                    "hostfile": str(hostfile),
                    "time_limit": time_limit,
                    "benchmarks": args.benchmarks,
                    "byte_sizes": args.byte_sizes,
                    "node_count": args.node_counts,
                    "algorithm": args.algorithm,
                    "param_file": str(args.param_file),
                    "split": args.split,
                    "topology": args.topology,
                    "simple_compute": args.simple_compute,
                    "loss_function": args.loss_function,
                    "loss_aggregator": args.loss_aggregator
                   }

    print("-----------------------------------------------------")
    print(f"Known Points: {ground_truth_data[0]}")
    print(f"GroundTruth: {ground_truth_data[1][0:10]}")
    print(f"Hostfile: {hostfile}")
    print(f"Time Limit: {args.time_limit} ({time_limit} seconds)")
    print(f"Benchmarks: {args.benchmarks}")
    print("-----------------------------------------------------")

    json_obj["config"] = config_json
    # json_encoder = CustomJSONEncoder()

    with open("result.txt", "w") as f:
        # print(json_encoder.encode(json_obj))
        f.write(json.dumps(json_obj, cls=CustomJSONEncoder, indent=4))

    smpi_sim = SMPISimulator(
        ground_truth_data, "IMB-P2P", hostfile, 0.05, keep_tmp=False, 
        byte_split=args.split, topology_template=args.topology, simple=args.simple_compute,
        loss_aggregator=args.loss_aggregator, loss_function=args.loss_function
    )

    calibrator = SMPISimulatorCalibrator(
        args.algorithm, smpi_sim, args.param_file
    )
    
    calibration, loss = calibrator.compute_calibration(time_limit, 1)

    for i in calibration:
            calibration[i] = str(calibration[i])

    result_json = {"calibration": calibration, "loss": loss, "best_result": smpi_sim.best_result}

    json_obj["results"] = result_json

    with open("result.txt", "w") as f:
        print("Calibrated Args: ")
        print(calibration)
        print(f"Loss: {loss}")
        print(f"Best Loss (Sim): {smpi_sim.best_loss}")
        print(f"Best Result: {smpi_sim.best_result}")
        print("-----------------------------------------------------")
        f.write(json.dumps(json_obj, cls=CustomJSONEncoder, indent=4))

if __name__ == "__main__":
    main()
