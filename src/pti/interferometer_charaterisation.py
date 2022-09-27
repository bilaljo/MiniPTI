"""
Implements a passive phase scan. A phase scan means calculating the output phases and can be done if there are
enough elements for the algorithm. Enoug means that every phase-bucket has at least one occoured.
"""

import numpy as np
from scipy import optimize


class InterferometerCharaterisation:
    def __init__(self, signals=None, step_size=None):
        self.signals = signals
        self.phases = None
        self.step_size = step_size
        self.occured_phases = np.full(step_size, True)
        self.enough_values = False
        self.output_phases = np.array([0, 2 * np.pi / 3, 4 * np.pi / 3])
        self.offset = None
        self.amplitude = None

    def set_amplitude(self):
        self.amplitude = (np.max(self.signals, axis=1) - np.min(self.signals, axis=1)) / 2

    def set_offset(self):
        self.offset = (np.max(self.signals, axis=1) + np.min(self.signals, axis=1)) / 2

    def set_signals(self, signal):
        self.signals = signal

    def set_phases(self, phases):
        self.phases = phases

    def add_phase(self, phase):
        k = int(self.step_size * phase / (2 * np.pi))
        self.occured_phases[k] = True

    def check_enough_values(self):
        self.enough_values = np.all(self.occured_phases)

    def characterise_interferometer(self):
        """
        Calculates with the least squares method the output phases and min and max intensities for every channel.
        If no min/max values and output phases are given (either none or nan) the function try to estimate them
        best-possible.
        """

        def best_fit(measured, output_phase):
            if output_phase:
                return lambda x: np.sum((x[0] * np.cos(self.phases - x[2]) + x[1] - measured) ** 2)
            else:  # Without searching for output phases the problem is reduced by one dimension
                return lambda x: np.sum((x[0] * np.cos(self.phases) + x[1] - measured) ** 2)

        res = optimize.minimize(fun=best_fit(measured=self.signals[0], output_phase=False),
                                x0=np.array([self.amplitude[0], self.offset[0]])).x
        self.amplitude[0], self.offset[0] = res[0], res[1]

        res = optimize.minimize(fun=best_fit(measured=self.signals[1], output_phase=True),
                                x0=np.array([self.amplitude[1], self.offset[1], self.output_phases[1]])).x
        self.amplitude[1], self.offset[1], self.output_phases[1] = res[0], res[1], res[2]

        res = optimize.minimize(fun=best_fit(measured=self.signals[2], output_phase=True),
                                x0=np.array([self.amplitude[2], self.offset[2], self.output_phases[2]])).x
        self.amplitude[2], self.offset[2], self.output_phases[2] = res[0], res[1], res[2]
