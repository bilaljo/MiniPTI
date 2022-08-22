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
        self.output_phases = [0, 1.83, 3.65]
        self.amplitude = 0
        self.offset = 0

    def set_amplitude(self, intensity):
        self.amplitude = (np.max(intensity, axis=1) - np.min(intensity, axis=1)) / 2

    def set_offset(self, intensity):
        self.offset = (np.max(intensity, axis=1) + np.min(intensity, axis=1)) / 2

    def calculate_interferometric_phase(self, intensity):
        self.amplitude = (np.max(intensity, axis=1) - np.min(intensity, axis=1)) / 2
        self.offset = (np.max(intensity, axis=1) + np.min(intensity, axis=1)) / 2

        def error_function(signal):
            intensity_scaled = 2 * (signal - np.min(intensity, axis=1)) / (np.max(intensity, axis=1) - np.min(intensity, axis=1)) - 1 # (signal - self.offset) / self.amplitude
            return lambda x: np.sum((np.cos(x - self.output_phases) - intensity_scaled) ** 2)

        def first_guess(signal):
            intensity_scaled = 2 * (signal - np.min(intensity, axis=1)) / (np.max(intensity, axis=1) - np.min(intensity, axis=1)) - 1 # (signal - self.offset) / self.amplitude
            phases = [[np.arccos(intensity_scaled[0]), -np.arccos(intensity_scaled[0])],
                      [np.arccos(intensity_scaled[1]) + self.output_phases[1],
                       -np.arccos(intensity_scaled[1]) + self.output_phases[1]],
                      [np.arccos(intensity_scaled[2]) + self.output_phases[2],
                       -np.arccos(intensity_scaled[2]) + self.output_phases[2]]]
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
                self.interferometric_phase[i] = optimize.minimize(fun=error_function(intensity.T[i]),
                                                                  x0=first_guess(intensity.T[i])).x
            self.interferometric_phase[self.interferometric_phase < 0] += 2 * np.pi
        else:
            self.interferometric_phase = optimize.minimize(fun=error_function(intensity), x0=first_guess(intensity)).x
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
            print(self.amplitude)
            weight += self.amplitude[channel] * np.abs(np.sin(self.interferometric_phase - self.output_phases[channel]))
        self.pti_signal = -np.sum(-pti_signal, axis=0) / np.sum(weight, axis=0)
        return self.pti_signal
