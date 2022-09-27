import itertools
import logging

import numpy as np
from scipy import optimize


class Inversion:
    """
    Provided an API for the PTI algorithm described in [1] from Weingartner et al.

    [1]: Waveguide based passively demodulated photothermal
         interferometer for aerosol measurements
    """
    def __init__(self, response_phases=None):
        self.response_phases = response_phases
        self.pti_signal = None
        self.interferometric_phase = []
        self.output_phases = [0, 1.83, 3.65]
        self.amplitude = []
        self.offset = []
        self.max = []
        self.min = []

    def calculate_amplitude(self, intensity):
        self.amplitude = (np.max(intensity, axis=0) - np.min(intensity, axis=0)) / 2
        print(np.max(intensity, axis=0))

    def calculate_offset(self, intensity):
        self.offset = (np.max(intensity, axis=0) + np.min(intensity, axis=0)) / 2

    def __calculate_interferometric_phase(self, intensity):
        # If any value is to large the scaling won't work and would result in an intensity less -1 or bigger 1.
        # In this case we cut off the overshoot
        intensity_scaled = (intensity - self.offset) / self.amplitude
        if (intensity_scaled < -1).any():
            intensity_scaled[intensity_scaled < -1] = -1
        elif (intensity_scaled > 1).any():
            intensity_scaled[intensity_scaled > 1] = 1
        np.rad2deg(self.output_phases)
        # Calculates the first guess
        phases = [[np.arccos(intensity_scaled[0]), - np.arccos(intensity_scaled[0])],
                  [np.arccos(intensity_scaled[1]) + self.output_phases[1],
                   -np.arccos(intensity_scaled[1]) + self.output_phases[1]],
                  [np.arccos(intensity_scaled[2]) + self.output_phases[2],
                   -np.arccos(intensity_scaled[2]) + self.output_phases[2]]]
        current_phase = None
        current_error = float("inf")
        for phase_triple in itertools.product(phases[0], phases[1], phases[2]):
            error = abs(phase_triple[0] - phase_triple[1]) + abs(phase_triple[0] - phase_triple[2]) + abs(
                phase_triple[1] - phase_triple[2])
            if error < current_error:
                current_error = error
                current_phase = phase_triple
        first_guess = np.mean(current_phase)
        res = optimize.minimize(fun=lambda x: np.sum((np.cos(x - self.output_phases) - intensity_scaled) ** 2),
                                x0=first_guess)
        logging.info(res)
        res = res.x if res.x > 0 else res.x + 2 * np.pi
        return res[0]

    def calculate_interferometric_phase(self, intensities):
        self.interferometric_phase = np.array(list(map(self.__calculate_interferometric_phase, intensities)))

    """
    Implements the algorithm for the interferometric phase from [1], Signal analysis and retrieval of PTI signal,
    equation 18.
    """
    def calculate_pti_signal(self, ac_signal: np.array, lock_in_phase: np.array) -> np.array:
        pti_signal = np.zeros(shape=(3, self.interferometric_phase.size))
        weight = np.zeros(shape=(3, self.interferometric_phase.size))
        print(self.interferometric_phase)
        for channel in range(3):
            sign = np.sin(self.interferometric_phase - self.output_phases[channel]) / np.abs(
                np.sin(self.interferometric_phase - self.output_phases[channel]))
            response_phase = self.response_phases[channel]
            demodulated_signal = ac_signal[channel] * np.cos(lock_in_phase[channel] - response_phase)
            pti_signal += demodulated_signal * sign
            weight += self.amplitude[channel] * np.abs(np.sin(self.interferometric_phase - self.output_phases[channel]))
        self.pti_signal = -np.sum(-pti_signal, axis=0) / np.sum(weight, axis=0)
        return self.pti_signal
