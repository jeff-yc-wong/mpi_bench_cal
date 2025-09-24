"""
This module provides a class for handling MPI ground truth data.
"""
from typing import List, Tuple
import pandas as pd


class MPIGroundTruth:
    """
    Class for handling MPI ground truth data.
    """

    def __init__(self, filename: str):
        self.full_df = pd.read_csv(filename)
        self.df = self.full_df.copy(deep=True)

    def set_benchmark_parent(self, benchmark_parent: str):
        """
        Filters the dataset based on the benchmark parent.

        Args:
            benchmark_parent (str): The benchmark parent to filter on. 
                                    If "all", the full dataset is used.

        Returns:
            None
        """
        if not benchmark_parent == "all":
            temp_df = self.df
            self.df = temp_df[temp_df['benchmark_parent'] == benchmark_parent]
        else:
            self.df = self.full_df

    def get_ground_truth(
        self,
        benchmarks: List[str] = None,
        byte_sizes: List[int] = None,
        node_counts: List[int] = None,
        validation: bool = False
    ) -> Tuple[List[Tuple[str, int, int, List[int]]], List[List[float]]]:
        """
        Filters the dataset based on input criteria and returns ground truth data.

        Args:
            benchmark (List[str]): List of benchmarks to filter.
            byte_sizes (List[int]): List of byte sizes to filter.
            node_count (List[int]): List of node counts to filter.
            validation (bool): If True, only includes benchmarks containing 'Stencil'.

        Returns:
            Tuple[List[Tuple[str, int, int, List[int]]], List[List[float]]]:
                - known_points: A list of tuples (benchmark, node_count, processes, bytes).
                - data: A list of lists containing Mbytes/sec values.
        """
        # Filter the dataset
        df = self.get_filtered_df(benchmarks, byte_sizes, node_counts)

        # Extract known points and data
        known_points = self.get_known_points(df, validation)
        data = self.get_data(df, validation)

        return (known_points, data)

    def get_filtered_df(self,
                        benchmarks: List[str] = None,
                        byte_sizes: List[int] = None,
                        node_counts: List[int] = None) -> pd.DataFrame:
        """
        Filters the dataset based on input criteria and returns the filtered DataFrame.

        Args:
            benchmark (List[str]): List of benchmarks to filter.
            byte_sizes (List[int]): List of byte sizes to filter.
            node_count (List[int]): List of node counts to filter.

        Returns:
            pd.DataFrame: Filtered DataFrame.
        """
        df = self.df

        # Filter out rows where "remark" isn't NaN
        df = df[pd.isnull(df["remark"])].reset_index(drop=True)

        benchmarks = tuple(benchmarks)

        # Apply filters based on input arguments
        if benchmarks:
            df = df[df["benchmark"].str.startswith(benchmarks)]
        if byte_sizes:
            df = df[df["bytes"].isin(byte_sizes)]
        if node_counts:
            df = df[df["node_count"].isin(node_counts)]

        return df

    def get_known_points(self, df: pd.DataFrame,
                         validation: bool = False) -> List[Tuple[str, int, int, List[int]]]:
        """
        Extracts known points from a DataFrame.

        Args:
            df (pd.DataFrame): DataFrame containing ground truth data.

        Returns:
            List[Tuple[str, int, int, List[int]]]: 
                A list of tuples (benchmark, node_count, processes, bytes).
        """
        # Prepare scenario DataFrame
        scenario_df = (
            df[["benchmark", "node_count", "processes", "bytes"]]
            .drop_duplicates()
            .assign(bytes=lambda x: x["bytes"].astype(int))
            .sort_values(by=["benchmark", "node_count", "processes", "bytes"])
            .reset_index(drop=True)
            .groupby(["benchmark", "node_count", "processes"])["bytes"]
            .agg(list)
            .reset_index()
        )

        # Apply validation filter if necessary
        if validation:
            scenario_df = scenario_df[scenario_df["benchmark"].str.contains(
                "Stencil")].reset_index(drop=True)

        # Extract known points
        known_points = [
            (row["benchmark"], row["node_count"],
             row["processes"], row["bytes"])
            for _, row in scenario_df.iterrows()
        ]

        return known_points

    def get_data(self, df: pd.DataFrame,
                 validation: bool = False) -> List[List[float]]:
        """
        Extracts data from a DataFrame.

        Args:
            df (pd.DataFrame): DataFrame containing ground truth data.

        Returns:
            List[List[float]]: 
                A list of lists containing Mbytes/sec values.
        """
        # Prepare data DataFrame
        data_df = (
            df[["benchmark", "node_count", "processes", "bytes", "Mbytes/sec"]]
            .sort_values(by=["benchmark", "node_count", "processes", "bytes"])
            .reset_index(drop=True)
            .groupby(["benchmark", "node_count", "processes", "bytes"])["Mbytes/sec"]
            .agg(list)
            .reset_index()
        )

        if validation:
            data_df = data_df[data_df["benchmark"].str.contains(
                "Stencil")].reset_index(drop=True)

        # Extract data
        data = list(data_df["Mbytes/sec"])

        return data


if __name__ == '__main__':
    from pathlib import Path

    file_abs_path = Path(__file__).parent.absolute()
    
    summit_ground_truth = MPIGroundTruth(file_abs_path.parent / "imb-summit.csv")

    summit_ground_truth.set_benchmark_parent("P2P")

    filtered_ground_truth = summit_ground_truth.get_ground_truth(
        benchmarks=["Stencil2D"], node_counts=[128, 256], byte_sizes=[4194304])

    print("Known points:", filtered_ground_truth[0])
    print("Data:", filtered_ground_truth[1])
