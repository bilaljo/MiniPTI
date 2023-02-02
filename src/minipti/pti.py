import logging
import os
import tarfile
from datetime import datetime
from dataclasses import dataclass

import numpy as np
import pandas as pd


@dataclass
class LockIn:
    amplitude: np.ndarray
    phase: np.ndarray


class Inversion:
    """
    Provided an API for the PTI algorithm described in [1] from Weingartner et al.

    [1]: Waveguide based passively demodulated photo-thermal
         interferometer for aerosol measurements
    """
    MICRO_RAD = 1e6

    def __init__(self, response_phases=None, sign=1, interferometry=None, settings_path="minipti/configs/settings.csv"):
        super().__init__()
        self.response_phases = response_phases
        self.pti_signal = None  # type: float | np.array
        self.sensitivity = None
        self.decimation_file_delimiter = ","
        self.dc_signals = np.empty(shape=3)
        self.settings_path = settings_path
        self.lock_in = LockIn
        self.init_header = True
        self.sign = sign  # Makes the pti signal positive if it isn't
        self.interferometry = interferometry
        self.load_response_phase()

    def __repr__(self):
        class_name = self.__class__.__name__
        representation = f"{class_name}(response_phases={self.response_phases}, pti_signal={self.pti_signal}," \
                         f"sensitivity={self.sensitivity}, lock_in={repr(self.lock_in)}"
        return representation

    def __str__(self):
        return f"Interferometric Phase: {self.interferometry.phase}\n" \
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
            pti_signal = np.zeros(shape=(len(self.interferometry.phase)))
            weight = np.zeros(shape=(len(self.interferometry.phase)))
        except TypeError:
            pti_signal = 0
            weight = 0
        for channel in range(3):
            try:
                sign = np.ones(shape=len(self.interferometry.phase))
                sign[np.sin(self.interferometry.phase - self.interferometry.output_phases[channel]) < 0] = -1
            except TypeError:
                sign = 1 if np.sin(self.interferometry.phase - self.interferometry.output_phases[channel]) >= 0 else -1
            response_phase = self.response_phases[channel]
            amplitude = self.interferometry.amplitudes[channel]
            demodulated_signal = self.lock_in.amplitude[channel] * np.cos(self.lock_in.phase[channel] - response_phase)
            pti_signal += demodulated_signal * sign * amplitude
            weight += amplitude * np.abs(np.sin(self.interferometry.phase - self.interferometry.output_phases[channel]))
        self.pti_signal = -pti_signal / weight * Inversion.MICRO_RAD

    def calculate_sensitivity(self):
        slopes = 0
        for i in range(3):
            slopes += self.interferometry.amplitudes[i] * np.abs(np.sin(self.interferometry.phase
                                                                        - self.interferometry.output_phases[i]))
        self.sensitivity = slopes / np.sum(self.interferometry.offsets)

    def _calculate_offline(self):
        data = self.interferometry.read_decimation()
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
        self.interferometry.calculate_phase(dc_signals)
        self.calculate_sensitivity()
        if ac_signals is not None:
            self.lock_in.amplitude = ac_signals
            self.lock_in.phase = ac_phases
            self.calculate_pti_signal()
        if ac_signals is not None:
            pd.DataFrame({"Interferometric Phase": "rad", "Sensitivity": "1/rad", "PTI Signal": "µrad"},
                         index=["s"]).to_csv("data/PTI_Inversion.csv", index_label="Time")
            pd.DataFrame({"Interferometric Phase": self.interferometry.phase, "Sensitivity": self.sensitivity,
                          "PTI Signal": self.pti_signal}).to_csv(f"data/PTI_Inversion.csv", mode="a", header=False)
        else:
            pd.DataFrame({"Interferometric Phase": "rad", "Sensitivity": "1/rad."}, index=["s"]).to_csv(
                "data/PTI_Inversion.csv", index_label="Time")
            pd.DataFrame({"Interferometric Phase": self.interferometry.phase, "Sensitivity": self.sensitivity}
                         ).to_csv("data/PTI_Inversion.csv", header=False, mode="a", index_label="Time")
        logging.info("PTI Inversion calculated.")

    def _calculate_online(self):
        output_data = {}
        if self.init_header:
            output_data["Interferometric Phase"] = "rad"
            output_data["Sensitivity"] = "1/rad"
            output_data["PTI Signal"] = "µrad"
            pd.DataFrame(output_data, index=["s"]).to_csv("data/PTI_Inversion.csv", index_label="Time")
            self.init_header = False
        self.interferometry.calculate_phase(self.dc_signals)
        self.calculate_pti_signal()
        self.calculate_sensitivity()
        now = datetime.now()
        time_stamp = str(now.strftime("%Y-%m-%d %H:%M:%S"))
        output_data = {"Interferometric Phase": self.interferometry.phase, "Sensitivity": self.sensitivity,
                       "PTI Signal": self.pti_signal}
        try:
            pd.DataFrame(output_data, index=[time_stamp]).to_csv("data/PTI_Inversion.csv", mode="a", index_label="Time",
                                                                 header=not os.path.exists("data/PTI_Inversion.csv"))
        except PermissionError:
            logging.info(f"Could not write data. Missing values are: {str(output_data)[1:-1]} at {time_stamp}.")

    def __call__(self, live=True):
        if live:
            self._calculate_online()
        else:
            self._calculate_offline()


class Decimation:
    """
    Provided an API for the PTI decimation described in [1] from Weingartner et al.

    The number of samples

    [1]: Waveguide based passively demodulated photo-thermal
         interferometer for aerosol measurements
    """
    REF_VOLTAGE = 3.3  # V
    REF_PERIOD = 100  # Samples
    SAMPLES = 8000
    DC_RESOLUTION = (1 << 12) - 1  # 12 Bit ADC
    AC_RESOLUTION = (1 << 16) // 2  # 16 bit ADC with 2 complement
    AMPLIFICATION = 100  # Theoretical value given by the hardware

    def __init__(self, debug=True):
        self.dc_coupled = np.empty(shape=(3, Decimation.SAMPLES))
        self.ac_coupled = np.empty(shape=(3, Decimation.SAMPLES))
        self.dc_signals = np.empty(shape=3)
        self.lock_in = LockIn(np.empty(shape=3), np.empty(shape=3))
        self.ref = None
        self.debug = debug
        self.number = 0
        self.in_phase = np.cos(2 * np.pi / Decimation.REF_PERIOD * np.arange(0, Decimation.SAMPLES))
        self.quadrature = np.sin(2 * np.pi / Decimation.REF_PERIOD * np.arange(0, Decimation.SAMPLES))
        self.file_path = ""
        self.init_header = True
        self.now = datetime.now()

    def process_raw_data(self):
        """
        Reads the binary data and save it into numpy arrays. The data is saved into npy archives in debug mode.
        """
        if self.debug:
            np.savez(file=f"data/raw_data_{self.number}", ref=self.ref, dc_coupled=self.dc_coupled,
                     ac_coupled=self.ac_coupled)
            self.number += 1
        dc_coupled = self.dc_coupled * Decimation.REF_VOLTAGE / Decimation.DC_RESOLUTION
        ac_coupled = self.ac_coupled / Decimation.AMPLIFICATION * Decimation.REF_VOLTAGE / Decimation.AC_RESOLUTION
        self.dc_coupled = dc_coupled
        self.ac_coupled = ac_coupled

    def get_raw_data(self):
        if self.file_path:
            i = 0
            with tarfile.open(self.file_path, "r") as tar:
                try:
                    tar.extract(f"raw_data_{i}.npz")
                    yield f"raw_data_{i}.npz"
                except KeyError:
                    raise StopIteration

    def calculate_dc(self):
        """
        Applies a low pass to the DC-coupled signals and decimate it to 1 s values.
        """
        np.mean(self.dc_coupled, axis=1, out=self.dc_signals)

    def common_mode_noise_reduction(self):
        noise_factor = np.sum(self.ac_coupled, axis=0) / sum(self.dc_signals)
        for channel in range(3):
            self.ac_coupled[channel] = self.ac_coupled[channel] - noise_factor * self.dc_signals[channel]

    def lock_in_amplifier(self):
        ac_x = np.mean(self.ac_coupled * self.in_phase, axis=1)
        ac_y = np.mean(self.ac_coupled * self.quadrature, axis=1)
        self.lock_in.phase = np.arctan2(ac_y, ac_x)
        self.lock_in.amplitude = np.sqrt(ac_x ** 2 + ac_y ** 2)

    def _calculate_decimation(self):
        self.calculate_dc()
        self.common_mode_noise_reduction()
        self.lock_in_amplifier()
        output_data = {}
        if self.init_header:
            for channel in range(3):
                output_data[f"Lock In Amplitude CH{channel + 1}"] = "V"
                output_data[f"Lock In Phase CH{channel + 1}"] = "deg"
                output_data[f"DC CH{channel + 1}"] = "V"
            pd.DataFrame(output_data, index=["s"]).to_csv("data/Decimation.csv", index_label="Time")
            self.init_header = False
        for channel in range(3):
            output_data[f"Lock In Amplitude CH{channel + 1}"] = self.lock_in.amplitude[channel]
            output_data[f"Lock In Phase CH{channel + 1}"] = np.rad2deg(self.lock_in.phase[channel])
            output_data[f"DC CH{channel + 1}"] = self.dc_signals[channel]
        now = datetime.now()
        time_stamp = str(now.strftime("%Y-%m-%d %H:%M:%S"))
        try:
            pd.DataFrame(output_data, index=[time_stamp]).to_csv("data/Decimation.csv", mode="a", index_label="Time",
                                                                 header=not os.path.exists("data/Decimation.csv"))
        except PermissionError:
            logging.info(f"Could not write data. Missing values are: {str(output_data)[1:-1]} at {time_stamp}.")

    def __call__(self, live=True):
        if live:
            self.process_raw_data()
            self._calculate_decimation()
        else:
            for file in self.get_raw_data():
                with np.load(file) as data:
                    self.dc_coupled = data["dc_coupled"]
                    self.ac_coupled = data["ac_coupled"]
                self._calculate_decimation()
