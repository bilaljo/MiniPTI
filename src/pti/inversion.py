import numpy as np
from scipy import optimize

from pti.phase_scan import PhaseScan


class Inversion:
    """
    Implements the algorithm for PTI Inversion and calculating the interfeometric phase.
    """
    def __init__(self, signals=None, response_phases=None):
        self.signals = signals
        self.scaled_signals = None
        self.response_phases = response_phases
        self.pti = None
        self.interferometric_phases = None
        self.output_phases = None
        self.min_intensities = None
        self.max_intensities = None

    def set_signals(self, signals):
        self.signals = signals

    def scale_signal(self):
        self.scaled_signals = 2 * (self.signals.T - self.min_intensities) / (
                self.max_intensities - self.min_intensities) - 1

    def calculate_interferometric_phase(self):
        if self.scaled_signals is None:
            raise ValueError("Signals are not scaled.")

        def error_function(intensity):
            return lambda x: (np.cos(x) - intensity[0]) ** 2 + (
                    np.cos(x - self.output_phases[1]) - intensity[1]) ** 2 + (
                                     np.cos(x - self.output_phases[2]) - intensity[2]) ** 2

        def error_function_df(intensity):
            output_phase = [self.output_phases[1], self.output_phases[2]]
            return lambda x: -2 * (-intensity[0] + np.cos(x)) * np.sin(x) + 2 * (
                                   -intensity[1] + np.cos(output_phase[1] - x)) * np.sin(output_phase[1] - x) + 2 * (
                                   -intensity[2] + np.cos(output_phase[2] - x)) * np.sin(output_phase[2] - x)

        phases = []
        for signal in self.scaled_signals:
            phases.append(optimize.fminbound(error_function(signal), x1=0, x2=2*np.pi))
        self.interferometric_phases = np.array(phases)

    def calculate_pti_signal(self, ac_signal: np.array, lock_in_phase: np.array) -> np.array:
        pti_signal = np.zeros(shape=self.scaled_signals.shape).T
        weight = np.zeros(shape=self.scaled_signals.shape).T
        for channel in range(3):
            sign = np.sin(self.interferometric_phases - self.output_phases[channel]) / np.abs(
                np.sin(self.interferometric_phases - self.output_phases[channel]))
            reponse_phase = self.response_phases[channel]
            demoudalted_signal = ac_signal[channel] * np.cos(lock_in_phase[channel] - reponse_phase)
            pti_signal += demoudalted_signal * sign
            weight += (self.max_intensities[channel] - self.min_intensities[channel]) / 2 * np.abs(
                np.sin(self.interferometric_phases - self.output_phases[channel]))
        self.pti = -np.sum(-pti_signal, axis=0) / np.sum(weight, axis=0)
        return self.pti
