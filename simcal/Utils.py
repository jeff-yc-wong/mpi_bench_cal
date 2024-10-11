from typing import List
import numpy as np


def explained_variance_error(x_simulated: List[float], y_real: List[List[float]]) -> str:
    overall_loss = 0

    for i in range(len(y_real)):
        y_real[i] = np.array(y_real[i])
        numerator = np.sum(np.sqrt(list(np.power(x_simulated[i] - y_real[i], 2))))
        denominator = np.sum(np.sqrt(list(np.power(y_real[i] - np.mean(y_real[i]), 2))))

        if denominator == 0:
            denominator = 1

        loss = numerator / denominator

        overall_loss += loss

    return overall_loss / len(y_real)

if __name__ == "__main__":

    simulated = [1, 2, 3, 4, 5]

    real = [[1.0001, 1.0002, 1.00001, 1.00003],
            [2.00002, 2.00003, 2.00004, 2.00005],
            [3.0001, 3.00002],
            [4.0001, 4.00002, 4.00003],
            [5.00001, 5.00002, 5.00003]]

    simulated_off = [5, 4, 3, 2, 1]

    error = explained_variance_error(simulated, real)
    
    error_off = explained_variance_error(simulated_off, real)
    print("Error: ", error)
    print("Error (should be higher): ", error_off)
