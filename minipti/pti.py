import logging
import os
from dataclasses import dataclass

import numpy as np
import pandas as pd
from scipy import signal


@dataclass
class LockIn:
    amplitude = 0  # type: float | np.ndarray
    phase = 0  # type: float | np.ndarray


class Inversion:
    """
    Provided an API for the PTI algorithm described in [1] from Vissler and Bilal et al.
    [1]: Waveguide based passively demodulated photothermal interferometer for light
     absorption measurements of trace substances
    """
    MICRO_RAD = 1e6

    def __init__(self, response_phases=None, sign=1, interferometer=None, settings_path="configs/settings.csv"):
        self.response_phases = response_phases
        self.pti_signal = None  # type: float | np.array
        self.sensitivity = None
        self.decimation_file_delimiter = ","
        self.dc_signals = np.empty(shape=3)
        self.settings_path = settings_path
        self.lock_in = LockIn
        self.init_header = True
        self.sign = sign  # Makes the pti signal positive if it isn't
        self.interferometer = interferometer

    def __repr__(self):
        class_name = self.__class__.__name__
        representation = f"{class_name}(response_phases={self.response_phases}, pti_signal={self.pti_signal}," \
                         f"sensitivity={self.sensitivity}, lock_in={repr(self.lock_in)}"
        return representation

    def __str__(self):
        return f"Interferometric Phase: {self.interferometer.phase}\n" \
               f"Sensitivity: {self.sensitivity}\nPTI signal: {self.pti_signal}"

    def load_response_phase(self):
        settings = pd.read_csv(self.settings_path, index_col="Setting")
        self.response_phases = np.deg2rad(settings.loc["Response Phases [deg]"].to_numpy())

    def calculate_pti_signal(self):
        """
        Implements the algorithm for the interferometric phase from [1], Signal analysis and retrieval of PTI signal,
        equation 18.
        """
        try:
            pti_signal = np.zeros(shape=(len(self.interferometer.phase)))
            weight = np.zeros(shape=(len(self.interferometer.phase)))
        except TypeError:
            pti_signal = 0
            weight = 0
        for channel in range(3):
            try:
                sign = np.ones(shape=len(self.interferometer.phase))
                sign[np.sin(self.interferometer.phase - self.interferometer.output_phases[channel]) < 0] = -1
            except TypeError:
                sign = 1 if np.sin(self.interferometer.phase - self.interferometer.output_phases[channel]) >= 0 else -1
            response_phase = self.response_phases[channel]
            amplitude = self.interferometer.amplitudes[channel]
            demodulated_signal = self.lock_in.amplitude[channel] * np.cos(self.lock_in.phase[channel] - response_phase)
            pti_signal += demodulated_signal * sign * amplitude
            weight += amplitude * np.abs(np.sin(self.interferometer.phase - self.interferometer.output_phases[channel]))
        self.pti_signal = -pti_signal / weight * Inversion.MICRO_RAD

    def calculate_sensitivity(self):
        slopes = 0
        for i in range(3):
            slopes += self.interferometer.amplitudes[i] * np.abs(np.sin(self.interferometer.phase
                                                                        - self.interferometer.output_phases[i]))
        self.sensitivity = slopes / np.sum(self.interferometer.offsets)

    def _calculate_offline(self):
        if not os.path.exists("data"):
            os.mkdir("data")
        data = self.interferometer.read_decimation()
        dc_signals = data[[f"DC CH{i}" for i in range(1, 4)]].to_numpy()
        ac_signals = None
        ac_phases = None
        try:
            ac_signals = np.sqrt(np.array(data[[f"X CH{i}" for i in range(1, 4)]]) ** 2
                                 + np.array(data[[f"Y CH{i}" for i in range(1, 4)]]) ** 2).T
            ac_phases = np.arctan2(np.array(data[[f"Y CH{i}" for i in range(1, 4)]]),
                                   np.array(data[[f"X CH{i}" for i in range(1, 4)]])).T
        except KeyError:
            try:
                ac_signals = data[[f"Lock In Amplitude CH{i}" for i in range(1, 4)]].to_numpy().T
                ac_phases = data[[f"Lock In Phase CH{i}" for i in range(1, 4)]].to_numpy().T
            except KeyError:
                pass
        self.interferometer.calculate_phase(dc_signals)
        self.calculate_sensitivity()
        if ac_signals is not None:
            self.lock_in.amplitude = ac_signals
            self.lock_in.phase = ac_phases
            self.calculate_pti_signal()
        if ac_signals is not None:
            pd.DataFrame({"Interferometric Phase": "rad", "Sensitivity": "1/rad", "PTI Signal": "µrad"},
                         index=["s"]).to_csv("data/PTI_Inversion.csv", index_label="Time")
            pd.DataFrame({"Interferometric Phase": self.interferometer.phase, "Sensitivity": self.sensitivity,
                          "PTI Signal": self.pti_signal}).to_csv(f"data/PTI_Inversion.csv", mode="a", header=False)
        else:
            pd.DataFrame({"Interferometric Phase": "rad", "Sensitivity": "1/rad."}, index=["s"]).to_csv(
                "data/PTI_Inversion.csv", index_label="Time")
            pd.DataFrame({"Interferometric Phase": self.interferometer.phase, "Sensitivity": self.sensitivity}
                         ).to_csv("data/PTI_Inversion.csv", header=False, mode="a", index_label="Time")
        logging.info("PTI Inversion calculated.")

    def __call__(self, live=False):
        if live:
            raise NotImplementedError("Will be avaiable in version 1.1")
        else:
            self._calculate_offline()


class Decimation:
    """
    Provided an API for the PTI decimation described in [1] from Vissler and Bilal et al.
    [1]: Waveguide based passively demodulated photothermal interferometer for light
     absorption measurements of trace substances
    """
    AMPLIFICATION = 10
    MOD_FREQUENCY = 80
    SAMPLES = 50000

    def __init__(self, file_path="binary.bin"):
        self.dc_coupled = np.empty(shape=(3, Decimation.SAMPLES))
        self.ac_coupled = np.empty(shape=(3, Decimation.SAMPLES))
        self.dc_signals = np.empty(shape=3)
        self.lock_in = LockIn()
        self.eof = False
        self.ref = None
        self.file = None
        self.file_path = file_path
        self._time = np.linspace(0, 1, Decimation.SAMPLES)

    def __call__(self):
        self._calculate_dc()
        self._common_mode_noise_reduction()
        self._lock_in_amplifier()

    def __enter__(self):
        self.file = open(file=self.file_path, mode="rb")
        return self

    def __exit__(self, exc_type, exc_value, exc_traceback):
        self.file.close()

    def read_data(self):
        """
        Reads the binary data and save it into numpy arrays.
        """
        if self.file_path is None:
            raise FileNotFoundError(f"Could not open {self.file_path}")
        if not np.frombuffer(self.file.read(4), dtype=np.intc):
            return False
        np.frombuffer(self.file.read(4), dtype=np.intc)
        for channel in range(3):
            self.dc_coupled[channel] = np.frombuffer(self.file.read(Decimation.SAMPLES * 8), dtype=np.float64)
        self.ref = np.frombuffer(self.file.read(Decimation.SAMPLES * 8), dtype=np.float64)
        for channel in range(3):
            self.ac_coupled[channel] = np.frombuffer(self.file.read(Decimation.SAMPLES * 8),
                                                     dtype=np.float64) / Decimation.AMPLIFICATION
        return True

    def _calculate_dc(self):
        """
        Applies a low pass to the DC-coupled signals and decimate it to 1 s values.
        """
        np.mean(self.dc_coupled, axis=1, out=self.dc_signals)

    def _common_mode_noise_reduction(self):
        noise_factor = np.sum(self.ac_coupled, axis=0) / sum(self.dc_signals)
        for channel in range(3):
            self.ac_coupled[channel] = self.ac_coupled[channel] - noise_factor * self.dc_signals[channel]

    def _lock_in_amplifier(self):
        first = np.where(self.ref > (1 / 2 * signal.square(self._time * 2 * np.pi * Decimation.MOD_FREQUENCY)
                                     + 1 / 2))[0][0]
        second = np.where(self.ref < (1 / 2 * signal.square(self._time * 2 * np.pi * Decimation.MOD_FREQUENCY)
                                      + 1 / 2))[0][0]
        phase_shift = max(first, second) / Decimation.SAMPLES
        in_phase = np.sin(2 * np.pi * Decimation.MOD_FREQUENCY * (self._time - phase_shift))
        quadrature = np.cos(2 * np.pi * Decimation.MOD_FREQUENCY * (self._time - phase_shift))
        ac_x = np.mean(self.ac_coupled * in_phase, axis=1)
        ac_y = np.mean(self.ac_coupled * quadrature, axis=1)
        self.lock_in.phase = np.arctan2(ac_y, ac_x)
        self.lock_in.amplitude = np.sqrt(ac_x ** 2 + ac_y ** 2)
