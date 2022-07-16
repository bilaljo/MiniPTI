import numpy as np
from scipy.optimize import minimize

from pti.phase_scan import PhaseScan


class Inversion(PhaseScan):
    """
    Implements the algorithm for PTI Inversion and calculating the interfeometric phase.
    """

    response_phases = None

    def __init__(self, signals=None):
        super().__init__(signals)
        self.pti = None
        self.interferometric_phases = None

    def set_signals(self, data: np.ndarray):
        self.signals = data

    def calculate_interferometric_phase(self):
        if self.scaled_signals is None:
            raise ValueError("Signals are not scaled.")

        def error_function(intensity):
            return lambda x: (np.cos(x) - intensity[0]) ** 2 + (
                    np.cos(x - PhaseScan.output_phases[1]) - intensity[1]) ** 2 + (
                                     np.cos(x - PhaseScan.output_phases[2]) - intensity[2]) ** 2

        phases = []
        bnds_1 = ((0, np.pi),)
        bnds_2 = ((np.pi, 2 * np.pi),)
        for signal in self.scaled_signals:
            phi_1 = minimize(error_function(signal), x0=np.array([np.arccos(signal[0])]), bounds=bnds_1).x[0]
            phi_2 = minimize(error_function(signal), x0=np.array([2 * np.pi - np.arccos(signal[0])]),
                             bounds=bnds_2).x[0]
            if abs(error_function(signal)(phi_1)) < abs(error_function(signal)(phi_2)):
                phases.append(phi_1)
            else:
                phases.append(phi_2)
        self.interferometric_phases = np.array(phases)

    def calculate_pti_signal(self, ac_signal: np.array, lock_in_phase: np.array) -> np.array:
        pti_signal = np.zeros(shape=self.scaled_signals.shape).T
        weight = np.zeros(shape=self.scaled_signals.shape).T
        for channel in range(3):
            sign = np.sin(self.interferometric_phases - PhaseScan.output_phases[channel]) / np.abs(
                np.sin(self.interferometric_phases - PhaseScan.output_phases[channel]))
            reponse_phase = self.response_phases[f"Detector {1 + channel}"]
            demoudalted_signal = ac_signal[channel] * np.cos(lock_in_phase - reponse_phase)
            pti_signal += demoudalted_signal * sign
            weight += (PhaseScan.max_intensities[channel] - PhaseScan.min_intensities[channel]) / 2 * np.abs(
                np.sin(self.interferometric_phases - PhaseScan.output_phases[channel]))
        self.pti = np.sum(-pti_signal, axis=0) / np.sum(weight, axis=0)
        return self.pti
