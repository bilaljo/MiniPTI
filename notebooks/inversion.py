import numpy as np
import itertools
from phase_scan import PhaseScan


class Inversion(PhaseScan):
    """
    Implements the algorithm for PTI Inversion and calculating the interfeometric phase.
    Attributes:
        response_phases: dict
        The respone phases of the system are obtained by calbiration measurements.
    """
    def __init__(self, signals: np.array, response_phases=None):
        super().__init__(signals)
        self.response_phases = response_phases
        self.pti = None
        self.interferometric_phases = None
    
    min_intensities = PhaseScan.min_intensities

    max_intensities = PhaseScan.max_intensities
    
        
    def set_min(self):
        Inversion.min_intensities = np.min(self.signals, axis=0)

    def set_max(self):
        Inversion.max_intensities = np.max(self.signals, axis=0)
        
    def scale_data(self):
        if Inversion.min_intensities is None:
            Inversion.min_intensities = PhaseScan.min_intensities
            Inversion.max_intensities = PhaseScan.max_intensities
        self.scaled_signals = 2 * (self.signals - Inversion.min_intensities) / (Inversion.max_intensities - Inversion.min_intensities) - 1

    def set_signals(self, data: np.ndarray):
        self.signals = data

    def __calculate_interferometric_phase(self):
        if self.scaled_signals is None:
            raise ValueError("Signals are not scaled.")
        phases = []
        for signal in self.scaled_signals:
            output_phases = PhaseScan.output_phases
            if PhaseScan.swapp_channels:
                signal[2], signal[1] = signal[1], signal[2]
            x_solutions = np.array([signal * np.cos(output_phases) + np.sqrt(1 - signal ** 2) * np.sin(output_phases), signal * np.cos(output_phases)
                                    - np.sqrt(1 - signal ** 2) * np.sin(output_phases)]).T
            y_solutions = np.array([signal * np.sin(output_phases) + np.sqrt(1 - signal ** 2)* np.cos(output_phases), signal * np.sin(output_phases)
                                    - np.sqrt(1 - signal ** 2) * np.cos(output_phases)]).T
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
        phases = np.array(phases)
        phases[np.where(phases < 0)] += 2 * np.pi
        self.interferometric_phases = phases
        return phases

    def get_interferometric_phase(self):
        return self.__calculate_interferometric_phase()

    def calculate_pti_signal(self, root_mean_square: np.array, lock_in_phase: np.array) -> np.array:
        pti_signal = np.zeros(shape=self.scaled_signals.shape).T
        weight = np.zeros(shape=self.scaled_signals.shape).T
        for channel in range(3):
            if PhaseScan.swapp_channels:
                if channel == 1:
                    channel = 2
                elif channel == 2:
                    channel = 1
            sign = np.sin(self.interferometric_phases - PhaseScan.output_phases[channel]) /\
                   np.abs(np.sin(self.interferometric_phases - PhaseScan.output_phases[channel]))
            reponse_phase = self.response_phases[f"Detector {1 + channel}"]
            demoudalted_signal = root_mean_square[channel] * np.cos(lock_in_phase - reponse_phase)
            pti_signal += demoudalted_signal * sign
            weight += (PhaseScan.max_intensities[channel] - PhaseScan.min_intensities[channel]) / 2 *\
                np.abs(np.sin(self.interferometric_phases - PhaseScan.output_phases[channel]))
        self.pti = np.sum(-pti_signal, axis=0) / np.sum(weight, axis=0)
        return self.pti
