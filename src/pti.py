import logging
from dataclasses import dataclass

import numpy as np
import pandas as pd
from scipy import signal

from interferometry import Interferometer


@dataclass
class LockIn:
    amplitude = 0  # type: float | np.ndarray
    phase = 0  # type: float | np.ndarray


class Inversion:
    """
    Provided an API for the PTI algorithm described in [1] from Weingartner et al.

    [1]: Waveguide based passively demodulated photo-thermal
         interferometer for aerosol measurements
    """
    MICRO_RAD = 1e6

    def __init__(self, response_phases=None, sign=1, interferometer=Interferometer()):
        self.response_phases = response_phases
        self.pti_signal = None  # type: float | np.array
        self.sensitivity = None
        self.decimation_file_delimiter = ","
        self.dc_signals = np.empty(shape=3)
        self.settings_path = "configs/settings.csv"
        self.lock_in = LockIn
        self.init_header = True
        self.sign = sign  # Makes the pti signal positive if it isn't
        self.interferometer = interferometer
        self.load_response_phase()

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

    def __call__(self, mode):
        match mode:
            case "offline":
                self._calculate_offline()
            case _:
                raise TypeError(f"Mode {mode} is an invalid mode.")


class Decimation:
    """
    Provided an API for the PTI decimation described in [1] from Weingartner et al.

    [1]: Waveguide based passively demodulated photothermal
         interferometer for aerosol measurements
    """

    def __init__(self, samples=50000, mod_frequency=80, amplification=10, file_path="binary.bin"):
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
        self.file_path = file_path

    def __call__(self):
        self._calculate_dc()
        self._common_mode_noise_reduction()
        self._lock_in_amplifier()

    def __enter__(self):
        self.file = open(file=self.file_path, mode="rb")

    def __exit__(self):
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
            self.dc[channel] = np.frombuffer(self.file.read(self.samples * 8), dtype=np.float64)
        self.ref = np.frombuffer(self.file.read(self.samples * 8), dtype=np.float64)
        for channel in range(3):
            self.ac[channel] = np.frombuffer(self.file.read(self.samples * 8), dtype=np.float64) / self.amplification
        return True

    def _calculate_dc(self):
        """
        Applies a low pass to the DC-coupled signals and decimate it to 1 s values.
        """
        np.mean(self.dc, axis=1, out=self.dc_down_sampled)

    def _common_mode_noise_reduction(self):
        noise_factor = np.sum(self.ac, axis=0) / sum(self.dc_down_sampled)
        for channel in range(3):
            self.ac[channel] = self.ac[channel] - noise_factor * self.dc_down_sampled[channel]

    def _lock_in_amplifier(self):
        first = np.where(self.ref > (1 / 2 * signal.square(self.time * 2 * np.pi * self.mod_frequency) + 1 / 2))[0][0]
        second = np.where(self.ref < (1 / 2 * signal.square(self.time * 2 * np.pi * self.mod_frequency) + 1 / 2))[0][0]
        phase_shift = max(first, second) / self.samples
        in_phase = np.sin(2 * np.pi * self.mod_frequency * (self.time - phase_shift))
        quadrature = np.cos(2 * np.pi * self.mod_frequency * (self.time - phase_shift))
        np.mean(self.ac * in_phase, axis=1, out=self.ac_x)
        np.mean(self.ac * quadrature, axis=1, out=self.ac_y)

    def polar_lock_in(self):
        return np.sqrt(self.ac_x ** 2 + self.ac_y ** 2), np.arctan2(self.ac_y, self.ac_x)
