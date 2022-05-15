import numpy as np


class Decimation:
    """
    Provides the methods for an software based Lock-In-Amplififer and decimation.

    This class parses binary data with a definined encoding: the first 3 x 50,000 Doubles
    represent DC-coupled signals. The next 50.000 Doubles represent the measured reference
    signal. The last 3 x 50,000 Doubles represent the measured AC-coupled signals.
    The reference for the Lock-In-Amplifier is to assumed to have a stable frequency at
    80 Hz.
    The sample frequency is at 50 kHz. With 1 s decimation intervall this results in
    50,000 samples.

    Attributes:
        samples: int
            The number of samples.
        dc: np.array
            The DC-coupled signals for each channel.
        ac: np.array
            The AC-coupled signals for each channel.
        dc_down_sampled: np.array
            The decimated DC-coupled signals for each channel.j
        in_phase: np.array
            The sine-reference for the Lock-In-Amplifier.
        quadratur: np.array
            The cosine-reference for the Lock-In-Amplifier.
        ac_x: np.array
            The In-Phase-Component for each Detector after Lock-In-Amplifier.
        ac_y: np.array
            The Quadratur-Component for each Detector after Lock-In-Amplifier.
        file: _io.TextIOWrapper
            The binary file with the measurements.
    """
    def __init__(self, file_name):
        self.samples = 50000
        self.dc = np.empty(shape=(3, self.samples))
        self.ac = np.empty(shape=(3, self.samples))
        self.dc_down_sampled = np.empty(shape=3)
        time = np.linspace(0, 1, self.samples) + 67.5  # The reference has a time shift.
        self.in_phase = np.sin(2 * np.pi * time * 80)
        self.quadratur = np.cos(2 * np.pi * time * 80)
        self.amplification = 1000  # The amplification is definied by the hardware setup.
        self.ac_x = np.empty(shape=3)
        self.ac_y = np.empty(shape=3)
        self.eof = False
        self.file = open(file_name, "rb")

    def read_data(self):
        """
        Reads the binary data and save it into numpy arrays.
        """
        if not np.frombuffer(self.file.read(4), dtype=np.intc):
            self.eof = True
            return
        np.frombuffer(self.file.read(4), dtype=np.intc)
        for channel in range(3):
            self.dc[channel] = np.frombuffer(self.file.read(self.samples * 8), dtype=np.float64)
        np.frombuffer(self.file.read(self.samples * 8), dtype=np.float64)
        for channel in range(3):
            self.ac[channel] = np.frombuffer(self.file.read(self.samples * 8), dtype=np.float64) / self.amplification

    def calucalte_dc(self):
        """
        Applies a low pass to the DC-coupled signals and decimate it to 1 s values.
        """
        self.dc_down_sampled = np.mean(self.dc, axis=1)

    def common_mode_noise_reduction(self):
        total_dc = sum(self.dc_down_sampled)
        noise = np.sum(self.ac, axis=0)
        for channel in range(3):
            self.ac[channel] = self.ac[channel] - (total_dc + noise) / total_dc * self.dc_down_sampled[channel]

    def lock_in_amplifier(self):
        np.mean(self.ac * self.in_phase, axis=1, out=self.ac_x)
        np.mean(self.ac * self.quadratur, axis=1, out=self.ac_y)

    def get_lock_in_values(self):
        return np.sqrt(self.ac_x ** 2 + self.ac_y ** 2), np.arctan2(self.ac_y, self.ac_x)
