import numpy as np


class PhaseScan:
    def __init__(self, signals: np.array):
        self.signals = signals
        self.scaled_signals = None

    output_phases = None

    min_intensities = None

    max_intensities = None

    def set_min(self):
        PhaseScan.min_intensities = np.min(self.signals, axis=1)

    def set_max(self):
        PhaseScan.max_intensities = np.max(self.signals, axis=1)

    def scale_data(self):
        self.scaled_signals = 2 * (self.signals - PhaseScan.min_intensities) \
                              / (PhaseScan.max_intensities - PhaseScan.min_intensities) - 1

    def calulcate_output_phases(self):
        output_phases_1 = np.concatenate([np.arccos(self.scaled_signals[0]) + np.arccos(self.scaled_signals[1]),
                          np.arccos(self.scaled_signals[0]) - np.arccos(self.scaled_signals[1]),
                          -np.arccos(self.scaled_signals[0]) + np.arccos(self.scaled_signals[1]),
                          -np.arccos(self.scaled_signals[0]) - np.arccos(self.scaled_signals[1])])
        output_phases_2 = np.concatenate([np.arccos(self.scaled_signals[0]) + np.arccos(self.scaled_signals[2]),
                          np.arccos(self.scaled_signals[0]) - np.arccos(self.scaled_signals[2]),
                          -np.arccos(self.scaled_signals[0]) + np.arccos(self.scaled_signals[2]),
                          -np.arccos(self.scaled_signals[0]) - np.arccos(self.scaled_signals[2])])
        np.where(output_phases_1 < 0, output_phases_1 + 2 * np.pi, output_phases_1)
        np.where(output_phases_2 < 0, output_phases_2 + 2 * np.pi, output_phases_2)
        bins, phases = np.histogram(output_phases_1, bins=np.sqrt(output_phases_1.shape[0]), range=(0, np.pi))
        output_phase_1 = phases[np.where(bins == np.max(bins))][0]
        bins, phases = np.histogram(output_phases_2, bins=np.sqrt(output_phases_2.shape[0]), range=(np.pi, 2 * np.pi))
        output_phase_2 = phases[np.where(bins == np.max(bins))][0]
        PhaseScan.output_phases = np.array([0, output_phase_1, output_phase_2])

    @staticmethod
    def get_output_phases():
        return PhaseScan.output_phases
