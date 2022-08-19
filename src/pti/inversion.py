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
        for channel in range(3):
            if intensity[channel] > self.max_intensities[channel]:
                self.max_intensities[channel] = intensity[channel]
            elif intensity[channel] < self.min_intensities[channel]:
                self.min_intensities[channel] = intensity[channel]

        amplitude = (self.max_intensities - self.min_intensities) / 2
        offset = (self.max_intensities + self.min_intensities) / 2

        def error_function(x, signal):
            return np.sum((amplitude * np.cos(x - self.output_phases) + offset - signal) ** 2)

        def first_guess(signal):
            intensity_scaled = (signal - offset) / amplitude
            phases = [[np.arccos(intensity_scaled[0]), -np.arccos(intensity_scaled[0])],
                      [np.arccos(intensity_scaled[1]) + self.output_phases[1], -np.arccos(intensity_scaled[1]) + self.output_phases[1]],
                      [np.arccos(intensity_scaled[2]) + self.output_phases[2], -np.arccos(intensity_scaled[2]) + self.output_phases[2]]]
            current_phase = None
            current_error = float("inf")
            for phase_triple in itertools.product(phases[0], phases[1], phases[2]):
                if abs(phase_triple[0] - phase_triple[1]) + abs(phase_triple[0] - phase_triple[2]) + abs(
                        phase_triple[1] - phase_triple[2]) < current_error:
                    current_error = abs(phase_triple[0] - phase_triple[1]) + abs(
                        phase_triple[0] - phase_triple[2]) + abs(phase_triple[1] - phase_triple[2])
                    current_phase = phase_triple
            return np.mean(current_phase)

        if intensity.size > 3:  # Vector of intensities.
            self.interferometric_phase = np.zeros(shape=intensity.size // 3)
            for i in range(intensity.size // 3):
                self.interferometric_phase[i] = optimize.minimize(fun=error_function, args=[intensity.T[i]],
                                                                  x0=first_guess(intensity[i])).x
            self.interferometric_phase[self.interferometric_phase < 0] += 2 * np.pi
        else:
            self.interferometric_phase = optimize.minimize(fun=error_function, args=[intensity],
                                                           x0=first_guess(intensity)).x
            if self.interferometric_phase < 0:
                self.interferometric_phase += 2 * np.pi

    def calculate_pti_signal(self, ac_signal: np.array, lock_in_phase: np.array) -> np.array:
        pti_signal = np.zeros(shape=(3, self.interferometric_phase.size))
        weight = np.zeros(shape=(3, self.interferometric_phase.size))
        for channel in range(3):
            sign = 1 if np.sin(self.interferometric_phase - self.output_phases[channel]) > 0 else -1
            response_phase = self.response_phases[channel]
            demodulated_signal = ac_signal[channel] * np.cos(lock_in_phase[channel] - response_phase)
            pti_signal += demodulated_signal * sign
            weight += (self.max_intensities[channel] - self.min_intensities[channel]) / 2 * np.abs(
                np.sin(self.interferometric_phase - self.output_phases[channel]))
        self.pti_signal = -np.sum(-pti_signal, axis=0) / np.sum(weight, axis=0)
        return self.pti_signal
