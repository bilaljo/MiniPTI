import numpy as np
from scipy import signal


class Decimation:
    """
    Provided an API for the PTI decimation described in [1] from Weingartner et al.

    The number of samples

    [1]: Waveguide based passively demodulated photothermal
         interferometer for aerosol measurements
    """
    def __init__(self, samples=50000, mod_frequency=80, amplification=10):
        self.samples = samples
        self.mod_frequency = mod_frequency
        self.dc = np.empty(shape=(3, self.samples))
        self.ac = np.empty(shape=(3, self.samples))
        self.dc_down_sampled = np.empty(shape=3)
        self.time = np.linspace(0, 1, self.samples)
        self.amplification = amplification  # The amplification is given by the hardware setup.
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
        self.ref = np.frombuffer(self.file.read(self.samples * 8), dtype=np.float64)
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
            self.ac[channel] = self.ac[channel] - noise_factor * self.dc_down_sampled[channel]

    def lock_in_amplifier(self):
        first = np.where(self.ref > (1 / 2 * signal.square(self.time * 2 * np.pi * 80) + 1 / 2))[0][0]
        second = np.where(self.ref < (1 / 2 * signal.square(self.time * 2 * np.pi * 80) + 1 / 2))[0][0]
        phase_shift = max(first, second) / self.samples
        in_phase = np.sin(2 * np.pi * 80 * (self.time - phase_shift))
        quadrature = np.cos(2 * np.pi * 80 * (self.time - phase_shift))
        np.mean(self.ac * in_phase, axis=1, out=self.ac_x)
        np.mean(self.ac * quadrature, axis=1, out=self.ac_y)

    def get_lock_in_values(self):
        return np.sqrt(self.ac_x ** 2 + self.ac_y ** 2), np.arctan2(self.ac_y, self.ac_x)
