import numpy as np
import scipy


class LockInAmplifier:
    """
    This class implements a software based Lock-In-Amplifier. The basic idea is the following:
        1. We multiply the reference signal with a measured signal
        2. We use a digital low pass get rid of all high frequencies
    Actually our desired signal is at exactly 0 Hz but because of noise the resulting signal can only be near 0 Hz.
    Hence, we do use the signal which is most nearly to 0 Hz.
    """
    def __init__(self, reference_signal: np.array, measured_signal: np.array):
        self.reference_signal = reference_signal
        self.measured_signal = measured_signal

    def multiply_signals(self):
        return self.reference_signal * self.measured_signal

