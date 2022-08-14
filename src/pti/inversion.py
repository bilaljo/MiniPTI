import itertools
import numpy as np
from scipy import optimize


class Inversion:
    """
    Implements the algorithm for PTI Inversion and calculating the interferometric phase.
    """

    def __init__(self, response_phases=None):
        self.response_phases = response_phases
        self.pti_signal = None
        self.interferometric_phase = np.empty(1)
        self.output_phases = None
        self.min_intensities = None
        self.max_intensities = None

    def calculate_interferometric_phase(self, intensity):
        self.max_intensities = np.max(intensity, axis=0)
        self.min_intensities = np.min(intensity, axis=0)
        scaled_intensity = 2 * (intensity - self.min_intensities) / (self.max_intensities - self.min_intensities) - 1

        def error_function(signal):
            return lambda x: (np.cos(x) - signal[0]) ** 2 + (
                              np.cos(x - self.output_phases[1]) - signal[1]) ** 2 + (
                             np.cos(x - self.output_phases[2]) - signal[2]) ** 2

        if intensity.size > 3:  # Vector of intensities.
            self.interferometric_phase = np.zeros(shape=intensity.size // 3)
            for i in range(intensity.size // 3):
                phases = [
                    [np.arccos(scaled_intensity[i][0]),
                     -np.arccos(scaled_intensity[i][0])],
                    [np.arccos(scaled_intensity[i][1]) + 1.81288881,
                     -np.arccos(scaled_intensity[i][1]) + 1.81288881],
                    [np.arccos(scaled_intensity[i][2]) + 3.75085711,
                     -np.arccos(scaled_intensity[i][2]) + 3.75085711],
                ]
                current_phase = None
                current_error = float("inf")
                for phase_triple in itertools.product(phases[0], phases[1], phases[2]):
                    if abs(phase_triple[0] - phase_triple[1]) + abs(phase_triple[0] - phase_triple[2]) + abs(phase_triple[1] - phase_triple[2]) < current_error:
                        current_error = abs(phase_triple[0] - phase_triple[1]) + abs(phase_triple[0] - phase_triple[2]) + abs(phase_triple[1] - phase_triple[2])
                        current_phase = phase_triple
                current_phase = np.mean(current_phase)
                self.interferometric_phase[i] = optimize.minimize(fun=error_function(scaled_intensity[i]), x0=current_phase).x
            self.interferometric_phase[self.interferometric_phase < 0] += 2 * np.pi
        else:
            self.interferometric_phase = optimize.fminbound(error_function(scaled_intensity), x1=0, x2=2 * np.pi)
            if self.interferometric_phase < 0:
                self.interferometric_phase += 2 * np.pi

    def calculate_pti_signal(self, ac_signal: np.array, lock_in_phase: np.array) -> np.array:
        pti_signal = np.zeros(shape=(3, self.interferometric_phase.size))
        weight = np.zeros(shape=(3, self.interferometric_phase.size))
        for channel in range(3):
            sign = np.sin(self.interferometric_phase - self.output_phases[channel]) / np.abs(
                np.sin(self.interferometric_phase - self.output_phases[channel]))
            response_phase = self.response_phases[channel]
            demodulated_signal = ac_signal[channel] * np.cos(lock_in_phase[channel] - response_phase)
            pti_signal += demodulated_signal * sign
            weight += (self.max_intensities[channel] - self.min_intensities[channel]) / 2 * np.abs(
                np.sin(self.interferometric_phase - self.output_phases[channel]))
        self.pti_signal = -np.sum(-pti_signal, axis=0) / np.sum(weight, axis=0)
        return self.pti_signal
