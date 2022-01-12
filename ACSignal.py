import numpy as np


class ACSignal:
    def __init__(self, phase, intensity_ac: np.array):
        self.phase = phase
        self.lissajous = self.LissajousFigure()
        self.intensity = intensity_ac

    def get_lissajous_figure(self, scaled_signals: np.array):
        """
        This function creates the lissajous figure with the given phases.
        :arg scaled_signals: array
        """
        for i in range(len(self.phase)):
            self.lissajous.x += scaled_signals[i] * np.cos(self.phase[i])
            self.lissajous.y += scaled_signals[i] * np.sin(self.phase[i])

    def correct_phases(self):
        """
        This function corrects the phases for the best match to a circle.
        :return:
        """
        pass

    def reconstruct_phase(self):
        return np.pi / 2 + np.arctan2(self.lissajous.x, self.lissajous.y)

    class LissajousFigure:
        def __init__(self):
            self.x = 0
            self.y = 0

    def scale_intensity(self, intensity_dc):
        return 2 / (max(intensity_dc) - min(intensity_dc)) * self.intensity
