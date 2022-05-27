import numpy as np
import networkx as nx


class PhaseScan:
    """
    Implements a passive phase scan. A phase scan means calculating the output phases and can be done if there are
    enough elements for the algorithm. Enoug means that every phase-bucket has at least one occoured.
    """
    def __init__(self, signals: np.array):
        self.signals = signals
        self.scaled_signals = None

    output_phases = None

    min_intensities = None

    max_intensities = None

    swapp_channels = False     

    def set_min(self):
        PhaseScan.min_intensities = np.min(self.signals, axis=1)

    def set_max(self):
        PhaseScan.max_intensities = np.max(self.signals, axis=1)

    def scale_data(self):
        self.scaled_signals = 2 * (self.signals.T - PhaseScan.min_intensities) \
                              / (PhaseScan.max_intensities - PhaseScan.min_intensities) - 1

    def set_channel_order(self):
        index_ch2 = []
        index_ch3 = []
        for i in range(len(self.scaled_signals.T[0]) - 1):
            if self.scaled_signals[i + 1][1] < 0 < self.scaled_signals[i][1]:
                index_ch2.append(i)
            if self.scaled_signals[i + 1][2] < 0 < self.scaled_signals[i][2]:
                index_ch3.append(i)
        PhaseScan.swapp_channels = sum(index_ch2) / len(index_ch2) > sum(index_ch3) / len(index_ch3)

    def calulcate_output_phases(self):
        self.scaled_signals = self.scaled_signals.T
        output_phases_1 = np.concatenate([np.arccos(self.scaled_signals[0]) + np.arccos(self.scaled_signals[1]),
                          np.arccos(self.scaled_signals[0]) - np.arccos(self.scaled_signals[1]),
                          -np.arccos(self.scaled_signals[0]) + np.arccos(self.scaled_signals[1]),
                          -np.arccos(self.scaled_signals[0]) - np.arccos(self.scaled_signals[1])])
        output_phases_2 = np.concatenate([np.arccos(self.scaled_signals[0]) + np.arccos(self.scaled_signals[2]),
                          np.arccos(self.scaled_signals[0]) - np.arccos(self.scaled_signals[2]),
                          -np.arccos(self.scaled_signals[0]) + np.arccos(self.scaled_signals[2]),
                          -np.arccos(self.scaled_signals[0]) - np.arccos(self.scaled_signals[2])])
        self.scaled_signals = self.scaled_signals.T
        output_phases_1[np.where(output_phases_1 < 0)] += 2 * np.pi
        output_phases_2[np.where(output_phases_2 < 0)] += 2 * np.pi
        bins, phases = np.histogram(output_phases_1, bins=int(np.sqrt(output_phases_1.shape[0])), range=(0, np.pi))
        output_phase_1 = phases[np.where(bins == np.max(bins))][0]
        bins, phases = np.histogram(output_phases_2, bins=int(np.sqrt(output_phases_2.shape[0])), range=(np.pi, 2 * np.pi))
        output_phase_2 = phases[np.where(bins == np.max(bins))][0]
        if PhaseScan.swapp_channels:
            PhaseScan.output_phases = np.array([0, output_phase_2, output_phase_1])
        else:
            PhaseScan.output_phases = np.array([0, output_phase_2, output_phase_1])

    @staticmethod
    def get_output_phases():
        return PhaseScan.output_phases
