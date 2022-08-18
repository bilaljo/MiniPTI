import numpy as np


class Decimation:
    """
    Provides the methods for a software based Lock-In-Amplifier and decimation.

    This class parses binary data with a fixed encoding: the first 3 x 50,000 Doubles
    represent DC-coupled signals. The next 50.000 Doubles represent the measured reference
    signal. The last 3 x 50,000 Doubles represent the measured AC-coupled signals.
    The reference for the Lock-In-Amplifier is assumed to have a stable frequency at
    80 Hz.
    The sample frequency is at 50 kHz. With 1 s decimation interval this results in
    50,000 samples.
    """

    def __init__(self):
        self.samples = 50000
        self.dc = np.empty(shape=(3, self.samples))
        self.ac = np.empty(shape=(3, self.samples))
        self.dc_down_sampled = np.empty(shape=3)
        time = np.linspace(0, 1, self.samples) + 0.00133
        self.in_phase = np.sin(2 * np.pi * time * 80)
        self.quadrature = np.cos(2 * np.pi * time * 80)
        self.amplification = 10  # The amplification is given by the hardware setup.
        self.ac_x = np.empty(shape=3)
        self.ac_y = np.empty(shape=3)
        self.eof = False
        self.ref = None
        self.file = None

    def read_data(self):
        """
        Reads the binary data and save it into numpy arrays.
        """
        if self.file is None:
            raise FileNotFoundError
        if not np.frombuffer(self.file.read(4), dtype=np.intc):
            self.eof = True
            return
        np.frombuffer(self.file.read(4), dtype=np.intc)
        for channel in range(3):
            self.dc[channel] = np.frombuffer(self.file.read(self.samples * 8), dtype=np.float64)
        np.frombuffer(self.file.read(self.samples * 8), dtype=np.float64)
        for channel in range(3):
            self.ac[channel] = np.frombuffer(self.file.read(self.samples * 8), dtype=np.float64) / self.amplification

    def calculate_dc(self):
        """
        Applies a low pass to the DC-coupled signals and decimate it to 1 s values.
        """
        np.mean(self.dc, axis=1, out=self.dc_down_sampled)

    def common_mode_noise_reduction(self):
        noise_factor = np.sum(self.ac, axis=0) / sum(self.dc_down_sampled)
        for channel in range(3):
            self.ac[channel] = self.ac[channel] - noise_factor

    def lock_in_amplifier(self):
        np.mean(self.ac * self.in_phase, axis=1, out=self.ac_x)
        np.mean(self.ac * self.quadrature, axis=1, out=self.ac_y)

    def get_lock_in_values(self):
        return np.sqrt(self.ac_x ** 2 + self.ac_y ** 2), np.arctan2(self.ac_y, self.ac_x)
