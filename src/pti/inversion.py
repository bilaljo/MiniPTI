import numpy as np
from scipy import optimize


class Inversion:
    """
    Implements the algorithm for PTI Inversion and calculating the interfeometric phase.
    """

    def __init__(self, response_phases=None):
        self.response_phases = response_phases
        self.pti = None
        self.interferometric_phase = np.empty(1)
        self.output_phases = None
        self.min_intensities = None
        self.max_intensities = None

    def calculate_interferometric_phase(self, intensity):
        scaled_intensity = 2 * (intensity - self.min_intensities) / (self.max_intensities - self.min_intensities) - 1

        def error_function(signal):
            return lambda x: (np.cos(x) - signal[0]) ** 2 + (
                    np.cos(x - self.output_phases[1]) - signal[1]) ** 2 + (
                                     np.cos(x - self.output_phases[2]) - signal[2]) ** 2

        if intensity.size > 3:
            self.interferometric_phase = np.zeros(shape=intensity.size // 3)
            for i in range(intensity.size // 3):
                self.interferometric_phase[i] = optimize.fminbound(error_function(scaled_intensity[i]),
                                                                   x1=0, x2=2 * np.pi)
        else:
            self.interferometric_phase = optimize.fminbound(error_function(scaled_intensity), x1=0, x2=2 * np.pi)

    def calculate_pti_signal(self, ac_signal: np.array, lock_in_phase: np.array) -> np.array:
        pti_signal = np.zeros(shape=(3, self.interferometric_phase.size))
        weight = np.zeros(shape=(3, self.interferometric_phase.size))
        for channel in range(3):
            sign = np.sin(self.interferometric_phase - self.output_phases[channel]) / np.abs(
                np.sin(self.interferometric_phase - self.output_phases[channel]))
            reponse_phase = self.response_phases[channel]
            demoudalted_signal = ac_signal[channel] * np.cos(lock_in_phase[channel] - reponse_phase)
            pti_signal += demoudalted_signal * sign
            weight += (self.max_intensities[channel] - self.min_intensities[channel]) / 2 * np.abs(
                np.sin(self.interferometric_phase - self.output_phases[channel]))
        self.pti = -np.sum(-pti_signal, axis=0) / np.sum(weight, axis=0)
        return self.pti
