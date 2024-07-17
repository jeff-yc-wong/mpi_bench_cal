import pandas as pd
from typing import List


class MPIGroundTruth:
    def __init__(self, filename: str):
        self.full_df = pd.read_csv(filename)
        self.df = self.full_df.copy(deep=True)

    def set_benchmark_parent(self, benchmark_parent: str):
        if not benchmark_parent == "all":
            temp_df = self.df
            self.df = temp_df[temp_df['benchmark_parent'] == benchmark_parent]
        else:
            self.df = self.full_df

    def get_ground_truth(self, benchmark: str = None, node_count: int = None, processes: int = None, metrics: List = None):
        df = self.df
        conditions = []
        if benchmark is not None:
            conditions.append(df['benchmark'] == benchmark)
        if node_count is not None:
            conditions.append(df['node_count'] == node_count)
        if processes is not None:
            conditions.append(df['processes'] == processes)

        
        if conditions:
            combined_conditions = conditions[0]
            for condition in conditions[1:]:
                combined_conditions &= condition

            filtered_df = df[combined_conditions]
        else:
            filtered_df = df

        if metrics is not None:
            return filtered_df[metrics]
        
        return filtered_df
    
    def get_scenarios(self, node_count: int = None):
        if node_count is not None:
            return self.df[self.df['node_count'] == node_count].drop_duplicates(subset=['benchmark', 'processes'])[["benchmark", "node_count", "processes"]].reset_index(drop=True)
        return self.df.drop_duplicates(subset=['benchmark', 'node_count', 'processes'])[["benchmark", "node_count", "processes"]].reset_index(drop=True)


def main():
    pass

if __name__ == '__main__':
    summit_ground_truth = MPIGroundTruth("../imb-summit.csv")

    summit_ground_truth.set_benchmark_parent("P2P")

    filtered_ground_truth = summit_ground_truth.get_ground_truth(node_count=128, metrics=["benchmark", "node_count", "processes", "Mbytes/sec", "bytes", "repetitions"])

    print(filtered_ground_truth[filtered_ground_truth["benchmark"] == "PingPing"])
