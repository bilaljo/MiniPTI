import numpy as np


class Inversion:
    def __init__(self, response_phases, signals):
        self.response_phases = response_phases
        self.signals = signals
        self.scaled_signals = None
        self.max_intensities = None
        self.min_intensities = None
        self.pti = None
        self.interferometric_phases = None

    def set_signals(self, data: np.ndarray):
        self.signals = data

    def set_min(self):
        self.min_intensities = np.min(self.signals, axis=1)

    def set_max(self):
        self.max_intensities = np.max(self.signals, axis=1)

    def scale_data(self):
        self.scaled_signals = 2 * (self.signals - self.min_intensities)\
            / (self.max_intensities - self.min_intensities) - 1

    def calculate_interferometric_phase(self):
        if self.scaled_signals is None:
            raise ValueError("Signals are not scaled.")
        x_solutions = np.array((3, np.len(self.scaled_signals, axis=1)))
        y_solutions = np.array((3, np.len(self.scaled_signals, axis=1)))
        for channel in range(3):
            x_solutions[channel] = self.scaled_signals[channel] * np.cos(self.response_phases[channel])
            + np.sqrt(1 - self.scaled_signals[channel] ** 2) * np.sin(self.response_phases[channel])
            x_solutions[channel + 3] = self.scaled_signals[channel] * np.cos(self.response_phases[channel])
            - np.sqrt(1 - self.scaled_signals[channel] ** 2) * np.sin(self.response_phases[channel])
            y_solutions[channel] = self.scaled_signals[channel] * np.sin(self.response_phases[channel])
            - np.sqrt(1 - self.scaled_signals[channel] ** 2) * np.cos(self.response_phases[channel])
            y_solutions[channel + 3] = self.scaled_signals[channel] * np.sin(self.response_phases[channel])
            + np.sqrt(1 - self.scaled_signals[channel] ** 2) * np.cos(self.response_phases[channel])
        for i in range(len(x_solutions)):
            current_error_x = 6
            current_error_y = 6
            indices_x = None
            indices_y = None
            for j in range(6):
                for k in range(j + 1, 6):
                    for l in range(k + 1, 6):
                        error_x = abs(x_solutions[j][i] - x_solutions[k][i])\
                                  + abs(x_solutions[j][i] - x_solutions[l][i])\
                                  + abs(x_solutions[l][i] - x_solutions[k][i])
                        error_y = abs(y_solutions[j][i] - y_solutions[k][i])\
                                  + abs(y_solutions[j][i] - y_solutions[l][i])\
                                  + abs(y_solutions[l][i] - y_solutions[k][i])
                        if current_error_x > error_x:
                            indices_x = (j, k, l)
                            current_error_x = error_x
                        if current_error_y > error_y:
                            indices_y = (j, k, l)
                            current_error_y = error_y
            x_solutions.append(np.mean([x_solutions[indices_x[0]][i], x_solutions[indices_x[1]][i],
                                        x_solutions[indices_x[2]][i]]))
            y_solutions.append(np.mean([y_solutions[indices_y[0]][i], y_solutions[indices_y[1]][i],
                                        x_solutions[indices_y[2]][i]]))

    def calculate_pti_signal(self, ac_in_phase, ac_quadratur, interferometric_phase):
        pti_signal = 0
        weight = 0
        self.pti = np.array(np.len(self.scaled_signals, axis=1), 3)
        for channel in range(3):
            sign = 1 if np.sin(interferometric_phase - self.response_phases[channel]) >= 0 else -1
            root_mean_square = np.sqrt(ac_in_phase[channel] ** 2 + ac_quadratur[channel] ** 2)
            lock_in_phase = np.arctan2(ac_quadratur[channel], ac_in_phase[channel])
            demoudalted_signal = root_mean_square * np.cos(lock_in_phase - self.response_phases[channel])
            pti_signal += demoudalted_signal * sign
            weight += (self.min_intensities[channel] - self.min_intensities[channel]) / 2 *\
                abs(np.sin(interferometric_phase - self.response_phases))
            self.pti[channel] = -pti_signal / weight
        return np.sum(self.pti.T, axis=1)
