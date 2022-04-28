from scipy import signal as sig
import numpy as np



class Decimation:
    def __init__(self, file_name):
        self.dc = []
        self.ac = []
        self.dc_down_sampled = []
        self.ref = None
        self.file_name = file_name
        self.first_read = True
        self.samples = 50000
        self.in_phase = np.sin(np.linspace(0, 2 * np.pi, self.samples) / 624 - 60)
        self.quadratur = np.cos(np.linspace(0, 2 * np.pi, self.samples) / 624 - 60)
        self.amplification = 1000
        self.ac_x = []
        self.ac_y = []
        self.file = None

    def read_data(self):
        self.ac = []
        self.dc = []
        if self.first_read:
            self.file = open(self.file_name, "rb")
            # TODO: Obsolet
            self.file.read(30)
            self.first_read = False
        np.frombuffer(self.file.read(4), dtype=np.intc)
        np.frombuffer(self.file.read(4), dtype=np.intc)
        for channel in range(3):
            self.dc.append(np.frombuffer(self.file.read(self.samples * 8), dtype=np.float64))
        self.ref = np.frombuffer(self.file.read(self.samples * 8), dtype=np.float64)
        for channel in range(3):
            self.ac.append(np.frombuffer(self.file.read(self.samples * 8), dtype=np.float64) / self.amplification)

    @staticmethod
    def low_pass(data, fs, order, fc):
        nyq = 0.5 * fs  # Calculate the Nyquist frequency.
        cut = fc / nyq  # Calculate the cutoff frequency (-3 dB).
        lp_b, lp_a = sig.butter(order, cut, btype='lowpass')  # Design and apply the low-pass filter.
        lp_data = list(sig.filtfilt(lp_b, lp_a, data))  # Apply forward-backward filter with linear phase.
        return lp_data

    def calucalte_dc(self):
        self.dc_down_sampled = []
        for channel in range(3):
            dc_down_sampled = self.dc[channel]
            dc_down_sampled = self.low_pass(dc_down_sampled, fs=50e3, order=2, fc=0.01)
            for i in range(4):
                dc_down_sampled = sig.decimate(dc_down_sampled, 10)
            #dc_down_sampled = sig.decimate(dc_down_sampled, 5)
            self.dc_down_sampled.append(np.mean(dc_down_sampled))

    def common_mode_noise_reduction(self):
        total_dc = sum(self.dc)
        noise = sum(self.ac)
        for channel in range(3):
            self.ac[channel] = self.ac[channel] - self.dc[channel] / total_dc * noise

    def lock_in_amplifier(self):
        self.ac_x = []
        self.ac_y = []
        for channel in range(3):
            in_phase = self.ac[channel] * self.in_phase
            quadratur = self.ac[channel] * self.quadratur
            in_phase_down_sampled = self.low_pass(data=in_phase, fs=50e3, order=2, fc=1)
            quadratur_down_sampled = self.low_pass(data=quadratur, fs=50e3, order=2, fc=1)
            for i in range(4):
                in_phase_down_sampled = sig.decimate(in_phase_down_sampled, 10)
                quadratur_down_sampled = sig.decimate(quadratur_down_sampled, 10)
            self.ac_x.append(np.mean(in_phase_down_sampled))
            self.ac_y.append(np.mean(quadratur_down_sampled))
