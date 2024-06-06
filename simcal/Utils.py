from typing import List
import numpy as np

def explained_variance_error(x_simulated: List[float], y_real: List[float]):
    # convert python list into numpy array for faster computation of error
    x_simulated = np.array(x_simulated)
    y_real = np.array(y_real)

    return np.sum(np.sqrt(np.power(x_simulated - y_real, 2))) / np.sum(np.sqrt(np.power(y_real - np.mean(y_real), 2)))
