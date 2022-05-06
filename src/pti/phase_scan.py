import numpy as np


class PhaseScan:
    def __init__(self, signals: np.array):
        self.signals = signals
        self.scaled_signals = None
        self.output_phases = None
        self.min_intensities = None
        self.max_intensities = None

    def set_min(self):
        self.min_intensities = np.min(self.signals, axis=1)

    def set_max(self):
        self.max_intensities = np.max(self.signals, axis=1)

    def scale_data(self):
        self.scaled_signals = 2 * (self.signals - self.min_intensities) \
                              / (self.max_intensities - self.min_intensities) - 1

    def calulcate_output_phases(self):
        output_phase_1 = np.concatenate([np.arccos(self.scaled_signals[0]) + np.arccos(self.scaled_signals[1]),
                          np.arccos(self.scaled_signals[0]) - np.arccos(self.scaled_signals[1]),
                          -np.arccos(self.scaled_signals[0]) + np.arccos(self.scaled_signals[1]),
                          -np.arccos(self.scaled_signals[0]) - np.arccos(self.scaled_signals[1])])
        output_phase_2 = np.concatenate([np.arccos(self.scaled_signals[0]) + np.arccos(self.scaled_signals[2]),
                          np.arccos(self.scaled_signals[0]) - np.arccos(self.scaled_signals[2]),
                          -np.arccos(self.scaled_signals[0]) + np.arccos(self.scaled_signals[2]),
                          -np.arccos(self.scaled_signals[0]) - np.arccos(self.scaled_signals[2])])
        output_phases = np.array([output_phase_1, output_phase_2])
        np.where(output_phases < 0, output_phases + 2 * np.pi, output_phases)
