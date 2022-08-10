import numpy as np
from scipy import optimize


class PhaseScan:
    """
    Implements a passive phase scan. A phase scan means calculating the output phases and can be done if there are
    enough elements for the algorithm. Enoug means that every phase-bucket has at least one occoured.
    """

    def __init__(self, signals=None, step_size=None):
        self.signals = signals
        self.phases = None
        self.scaled_signals = None
        self.step_size = step_size
        self.descritized_phase = [2 * np.pi / step_size * i for i in range(1, step_size + 1)]
        self.occured_phases = [False for i in range(1, step_size + 1)]
        self.last_index = 0
        self.enough_values = False
        self.output_phases = np.empty(3)
        self.min_intensities = np.empty(3)
        self.max_intensities = np.empty(3)

    min_intensities = None

    max_intensities = None

    def set_signals(self, signal):
        self.signals = signal

    def set_phases(self, phases):
        self.phases = phases

    def set_min(self):
        PhaseScan.min_intensities = np.min(self.signals, axis=1)

    def set_max(self):
        PhaseScan.max_intensities = np.max(self.signals, axis=1)

    def scale_data(self):
        self.scaled_signals = 2 * (self.signals.T - PhaseScan.min_intensities) / (
                PhaseScan.max_intensities - PhaseScan.min_intensities) - 1

    def add_phase(self, phase):
        k = int(self.step_size * phase / (2 * np.pi))
        self.occured_phases[k] = True

    def check_enough_values(self):
        self.enough_values = np.all(self.occured_phases)

    def calulcate_output_phases(self):
        if self.scaled_signals is None:
            raise ValueError("Signals are not scaled")

        def best_fit(measured, output_phase):
            if output_phase:
                return lambda x: np.sum((measured -
                                         ((x[0] - x[1]) / 2 * np.cos(self.phases - x[2]) + (x[0] + x[1]) / 2)) ** 2)
            else:  # Without searching for output phases the problem is reduced by one dimension
                return lambda x: np.sum((measured - ((x[0] - x[1]) / 2 * np.cos(self.phases) + (x[0] + x[1]) / 2)) ** 2)

        res = optimize.minimize(fun=best_fit(measured=self.scaled_signals[0], output_phase=False),
                                x0=np.array([0, 0])).x
        self.min_intensities[0], self.max_intensities[0] = res[0], res[1]

        res = optimize.minimize(fun=best_fit(measured=self.scaled_signals[1], output_phase=True),
                                x0=np.array([0, 0, 0])).x
        self.min_intensities[1], self.max_intensities[1], self.output_phases[1] = res[0], res[1], res[2]

        res = optimize.minimize(fun=best_fit(measured=self.scaled_signals[2], output_phase=True),
                                x0=np.array([0, 0, 0])).x
        self.min_intensities[2], self.max_intensities[2], self.output_phases[2] = res[0], res[1], res[2]
