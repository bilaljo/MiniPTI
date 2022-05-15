import numpy as np
import itertools
from pti.phase_scan import PhaseScan


class Inversion(PhaseScan):
    def __init__(self, response_phases: np.array, signals: np.array):
        super().__init__(signals)
        self.response_phases = response_phases
        self.pti = None
        self.interferometric_phases = None

    def set_signals(self, data: np.ndarray):
        self.signals = data

    def __calculate_interferometric_phase(self):
        if self.scaled_signals is None:
            raise ValueError("Signals are not scaled.")
        phases = []
        for signal in self.scaled_signals:
            x_solutions = np.array([signal * np.cos(PhaseScan.output_phases) + np.sqrt(1 - signal ** 2)
                                    * np.sin(PhaseScan.output_phases), signal * np.cos(PhaseScan.output_phases)
                                    - np.sqrt(1 - signal ** 2) * np.sin(PhaseScan.output_phases)]).T
            y_solutions = np.array([signal * np.sin(PhaseScan.output_phases) + np.sqrt(1 - signal ** 2)
                                    * np.cos(PhaseScan.output_phases), signal * np.sin(PhaseScan.output_phases)
                                    - np.sqrt(1 - signal ** 2) * np.cos(PhaseScan.output_phases)]).T
            x_triple = itertools.product(x_solutions[0], x_solutions[1], x_solutions[2])
            y_triple = itertools.product(y_solutions[0], y_solutions[1], y_solutions[2])
            current_error_x = float("Inf")
            current_error_y = float("Inf")
            current_triple_x = None
            current_triple_y = None
            for x, y in zip(x_triple, y_triple):
                if abs(x[0] - x[1]) + abs(x[0] - x[2]) + abs(x[1] - x[2]) < current_error_x:
                    current_error_x = abs(x[0] - x[1]) + abs(x[0] - x[2]) + abs(x[1] - x[2])
                    current_triple_x = x
                if abs(y[0] - y[1]) + abs(y[0] - y[2]) + abs(y[1] - y[2]) < current_error_y:
                    current_error_y = abs(y[0] - y[1]) + abs(y[0] - y[2]) + abs(y[1] - y[2])
                    current_triple_y = y
            phases.append(np.arctan2(sum(current_triple_y) / 3, sum(current_triple_x) / 3))  # 3 channels.
        self.interferometric_phases = phases
        return phases

    def get_interferometric_phase(self):
        return self.__calculate_interferometric_phase()

    def calculate_pti_signal(self, root_mean_square: np.array, lock_in_phase: np.array) -> np.array:
        pti_signal = 0
        weight = 0
        for channel in range(3):
            sign = np.sin(self.interferometric_phases - self.response_phases[channel]) /\
                   np.abs(np.sin(self.interferometric_phases - self.response_phases[channel]))
            demoudalted_signal = root_mean_square[channel] * np.cos(lock_in_phase - self.response_phases[channel])
            pti_signal += demoudalted_signal * sign
            weight += (PhaseScan.max_intensities[channel] - PhaseScan.min_intensities[channel]) / 2 *\
                np.abs(np.sin(self.interferometric_phases - PhaseScan.output_phases[channel]))
        self.pti = np.sum(-pti_signal / weight, axis=0)
        return self.pti
