import numpy as np
from phase_scan import PhaseScan


class Inversion(PhaseScan):
    def __init__(self, response_phases: np.array, signals: np.array):
        super.__init__(signals)
        self.response_phases = response_phases
        self.pti = None
        self.interferometric_phases = None

    def set_signals(self, data: np.ndarray):
        self.signals = data

    def __calculate_interferometric_phase(self):
        if self.scaled_signals is None:
            raise ValueError("Signals are not scaled.")
        x_solutions = np.array((2, 3))
        y_solutions = np.array((2, 3))
        x_solutions[0] = self.scaled_signals * np.cos(self.output_phases) + np.sqrt(1 - self.scaled_signals ** 2)\
            * np.sin(self.output_phases)
        x_solutions[1] = self.scaled_signals * np.cos(self.output_phases) - np.sqrt(1 - self.scaled_signals ** 2)\
            * np.sin(self.output_phases)
        y_solutions[0] = self.scaled_signals * np.sin(self.output_phases) + np.sqrt(1 - self.scaled_signals ** 2)\
            * np.cos(self.output_phases)
        y_solutions[1] = self.scaled_signals * np.sin(self.output_phases) - np.sqrt(1 - self.scaled_signals ** 2)\
            * np.cos(self.output_phases)
        x_solutions = x_solutions.T
        y_solutions = y_solutions.T
        x_triple = np.meshgrid(x_solutions[0], x_solutions[1], x_solutions[2])
        y_triple = np.meshgrid(y_solutions[0], y_solutions[1], y_solutions[2])
        x = np.min(np.abs(x_triple[0] - x_triple[1]) + np.abs(x_triple[0] - x_triple[2])
                   + np.abs(x_triple[1] - x_triple[2]))
        y = np.min(np.abs(y_triple[0] - y_triple[1]) + np.abs(y_triple[0] - y_triple[2])
                   + np.abs(y_triple[1] - y_triple[2]))
        return np.arctan2(y, x)

    def get_interferometric_phase(self):
        return np.vectorize(self.__calculate_interferometric_phase)(self.scaled_signals)

    def calculate_pti_signal(self, ac_in_phase: np.array, ac_quadratur: np.array) -> np.array:
        pti_signal = 0
        weight = 0
        self.pti = np.array(np.len(self.scaled_signals, axis=1), 3)
        for channel in range(3):
            sign = 1 if np.sin(self.interferometric_phases - self.response_phases[channel]) >= 0 else -1
            root_mean_square = np.sqrt(ac_in_phase[channel] ** 2 + ac_quadratur[channel] ** 2)
            lock_in_phase = np.arctan2(ac_quadratur[channel], ac_in_phase[channel])
            demoudalted_signal = root_mean_square * np.cos(lock_in_phase - self.response_phases[channel])
            pti_signal += demoudalted_signal * sign
            weight += (self.min_intensities[channel] - self.min_intensities[channel]) / 2 *\
                abs(np.sin(self.interferometric_phases - self.response_phases))
            self.pti[channel] = -pti_signal / weight
        return np.sum(self.pti.T, axis=1)
