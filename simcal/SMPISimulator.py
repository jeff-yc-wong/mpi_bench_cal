import simcal as sc
from typing import List, Callable, Any

class SMPISimulator(sc.Simulator):
    
    def __init__(self):
        super().__init__()
        pass

    def run(self, env: sc.Environment, args: tuple[str, dict[str, sc.parameters.Value]]) -> Any:
        
        # TODO: rebuild .so file for Summit definition with the arguments for calibrations (make sure to add those
                                                                                            # arguments to the
                                                                                            # calibrator)
        
        # TODO: execute smpirun with the new Summit platform file and the smpi-arguments (also from calibration)

        pass