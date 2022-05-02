import numpy as np
from pti import Inversion

class PhaseScan(Inversion):
    def __init__(self, response_phase, save_time):
        super.__init__(response_phase, save_time)

    def scale_data(self):
        super.scaled_values = 2 * (self.dc_values - self.min) / (self.max - self.min) - 1

    @staticmethod
    def make_positive(elemenmt):
        return elemenmt if elemenmt > 0 else elemenmt + 2 * np.pi

    def calculate_output_phases(self):
        output_phases = np.array([
            [np.arccos(self.scaled_values[0]) + np.arccos(self.scaled_values[1]),
             np.arccos(self.scaled_values[0]) - np.arccos(self.scaled_values[1]),
             -np.arccos(self.scaled_values[0]) + np.arccos(self.scaled_values[1]),
             -np.arccos(self.scaled_values[0]) - np.arccos(self.scaled_values[1])],
            [np.arccos(self.scaled_values[0]) + np.arccos(self.scaled_values[2]),
             np.arccos(self.scaled_values[0]) - np.arccos(self.scaled_values[2]),
             -np.arccos(self.scaled_values[0]) + np.arccos(self.scaled_values[2]),
             -np.arccos(self.scaled_values[0]) - np.arccos(self.scaled_values[2])]
        ])
        output_phases[0] = output_phases[0][np.where(output_phases[0] <= np.pi)]
        output_phases[1] = output_phases[1][np.where(output_phases[1] > np.pi)]
