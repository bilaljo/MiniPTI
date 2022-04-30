import numpy as np


class PTI:
    def __int__(self, response_phases, save_time):
        self.response_phases = response_phases
        self.scaled_signals = []
        self.max_intensities = []
        self.min_intensities = []
        self.pti = []
        self.interferometric_phases = []

    def scale_signals(self, signals):
        for channel in range(3):
            self.scaled_signals.append(2 * (signals[channel] - self.min_intensities[channel])
                                       / (self.min_intensities[channel] - self.min_intensities[channel]) - 1)

    def calculate_interferometric_phase(self):
        x_solutions = []
        y_solutions = []
        for i in range(3):
            x_solutions.append(self.scaled_signals[i] * np.cos(self.response_phases[i])
                               + np.sqrt(1 - self.scaled_signals[i] ** 2) * np.sin(self.response_phases[i]))
            x_solutions.append(self.scaled_signals[i] * np.cos(self.response_phases[i])
                               - np.sqrt(1 - self.scaled_signals[i] ** 2) * np.sin(self.response_phases[i]))
            y_solutions.append(self.scaled_signals[i] * np.sin(self.response_phases[i])
                               - np.sqrt(1 - self.scaled_signals[i] ** 2) * np.cos(self.response_phases[i]))
            y_solutions.append(self.scaled_signals[i] * np.sin(self.response_phases[i])
                               + np.sqrt(1 - self.scaled_signals[i] ** 2) * np.cos(self.response_phases[i]))
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
        for channel in range(3):
            sign = 1 if np.sin(interferometric_phase - self.response_phases[channel]) >= 0 else -1
            root_mean_square = np.sqrt(ac_in_phase[channel] ** 2 + ac_quadratur[channel] ** 2)
            sys = np.arctan2(ac_quadratur[channel], ac_in_phase[channel])
            dms = root_mean_square * np.cos(sys - self.response_phases[channel])
            pti_signal += dms * sign
            weight += (self.min_intensities[channel] - self.min_intensities[channel]) / 2\
                      * abs(np.sin(interferometric_phase - self.response_phases))
            self.pti.append(-pti_signal / weight)
