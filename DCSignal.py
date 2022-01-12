import numpy as np


class DCSignal:
    """
    This class represents the calculation of a DC signal of the PTI, which corresponds to the current phase of the
    interferometer.
    The intensity corresponds to the intensity of a detector of the PTI.
    """
    def __init__(self, intensity_dc: np.array):
        self.intensity = intensity_dc
        self.scaled_intensity = np.array()

    def scale_intensity(self):
        """
        This function normalises the measured DC-signals. In the result they are between -1 and 1.
        """
        max_intensity, min_intensity = max(self.intensity), min(self.intensity)
        self.scaled_intensity = 2 * (self.intensity - min_intensity) / (max_intensity - min_intensity) - 1
