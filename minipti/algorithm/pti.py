"""
API for PTI Inversion and Decimation.
"""

import logging
import os
from collections.abc import Generator
from dataclasses import dataclass
from datetime import datetime

import h5py
import numpy as np
import pandas as pd
from nptyping import NDArray, UInt16, Int16, Shape

import minipti.hardware
import minipti.algorithm.interferometry as interferometry


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
    LOCK_IN_HEADERS = [([f"X{i}" for i in range(1, 4)], [f"Y{i}" for i in range(1, 4)]),
                       ([f"x{i}" for i in range(1, 4)], [f"y{i}" for i in range(1, 4)]),
                       ([f"Lock in Amplitude {i}" for i in range(1, 4)],
                        [f"Lock in Phase{i}" for i in range(1, 4)]),
                       ([f"AC CH{i}" for i in range(1, 4)],
                        [f"AC Phase CH{i}" for i in range(1, 4)])]

    SYMMETRIC_MINIMUM = 1.154 - 1  # We subtract 1 to shift the optimum to 1

    def __init__(
            self, response_phases=None, sign=1, interferometer=None,
            settings_path=f"{os.path.dirname(__file__)}/configs/settings.csv"
    ):
        super().__init__()
        self.response_phases = response_phases
        self.pti_signal: float | np.ndarray = 0
        self.sensitivity: np.ndarray = np.empty(0)
        self.symmetry: float | np.ndarray = 0
        self.decimation_file_delimiter = ","
        self.dc_signals = np.empty(shape=3)
        self.settings_path = settings_path
        self.lock_in = LockIn(np.empty(shape=3), np.empty(shape=3))
        self.init_header = True
        self.sign = sign  # Makes the pti signal positive if it isn't
        self.interferometer = interferometer
        self.destination_folder = os.getcwd()
        self.load_response_phase()

    def __repr__(self) -> str:
        class_name = self.__class__.__name__
        representation = f"{class_name}(response_phases={self.response_phases}," \
                         f" pti_signal={self.pti_signal}," \
                         f"Symmetry={self.symmetry}, lock_in={repr(self.lock_in)}"
        return representation

    def __str__(self) -> str:
        return f"Interferometric Phase: {self.interferometer.phase}\n" \
               f"Symmetry: {self.symmetry}\nPTI signal: {self.pti_signal}"

    def load_response_phase(self) -> None:
        settings = pd.read_csv(self.settings_path, index_col="Setting")
        self.response_phases = np.deg2rad(settings.loc["Response Phases [deg]"].to_numpy())

    def _calculate_sign(self, channel: int) -> int:
        try:
            sign = np.ones(shape=len(self.interferometer.phase))
            sign[np.sin(self.interferometer.phase -
                        self.interferometer.output_phases[channel]) < 0] = -1
        except TypeError:
            sign = 1 if np.sin(self.interferometer.phase -
                               self.interferometer.output_phases[channel]) >= 0 else -1
        return sign

    def calculate_pti_signal(self) -> None:
        try:
            pti_signal = np.zeros(shape=(len(self.interferometer.phase)))
            weight = np.zeros(shape=(len(self.interferometer.phase)))
        except TypeError:
            pti_signal = 0
            weight = 0
        for channel in range(3):
            sign = self._calculate_sign(channel)
            response_phase = self.response_phases[channel]
            amplitude = self.interferometer.amplitudes[channel]
            demodulated_signal = self.lock_in.amplitude[channel] * np.cos(
                self.lock_in.phase[channel] - response_phase)
            pti_signal += demodulated_signal * sign * amplitude
            weight += amplitude * np.abs(np.sin(self.interferometer.phase
                                                - self.interferometer.output_phases[channel]))
        self.pti_signal = -pti_signal / weight * Inversion.MICRO_RAD

    def calculate_sensitivity(self) -> None:
        try:
            self.sensitivity = np.empty(shape=(3, len(self.interferometer.phase)))
        except TypeError:
            self.sensitivity = [0, 0, 0]
        for channel in range(3):
            amplitude = self.interferometer.amplitudes[channel]
            output_phase = self.interferometer.output_phases[channel]
            self.sensitivity[channel] = amplitude * np.abs(np.sin(self.interferometer.phase
                                                                  - output_phase))
        total_sensitivity = np.sum(self.sensitivity, axis=0)
        self.symmetry = np.max(total_sensitivity) / np.min(total_sensitivity)

    def _calculate_offline(self) -> None:
        data = self.interferometer.read_decimation()
        for header in interferometry.Interferometer.DC_HEADERS:
            try:
                dc_signals = data[header].to_numpy()
                break
            except KeyError:
                continue
        else:
            raise KeyError("Invalid key for DC values given")
        for lock_in_header_1, lock_in_header_2 in Inversion.LOCK_IN_HEADERS:
            try:
                # If it uses the X, Y notation we need to calculate amplitudes and phases first
                if lock_in_header_1[0].casefold == "x1":
                    self.lock_in.amplitude = np.sqrt(data[lock_in_header_1] ** 2
                                                     + data[lock_in_header_1] ** 2).to_numpy().T
                    self.lock_in.phase = np.arctan2(data[lock_in_header_2],
                                                    data[lock_in_header_1]).to_numpy().T
                    pti_measurement = True
                    break
                self.lock_in.amplitude = data[lock_in_header_1].to_numpy().T
                self.lock_in.phase = data[lock_in_header_2].to_numpy().T
                pti_measurement = True
                break
            except KeyError:
                continue
        else:
            pti_measurement = False
        self.interferometer.calculate_phase(dc_signals)
        self.calculate_sensitivity()
        if pti_measurement:
            self.calculate_pti_signal()
        units, output_data = self._prepare_data(pti_measurement)
        pd.DataFrame(units, index=["s"]).to_csv(f"{self.destination_folder}/PTI_Inversion.csv",
                                                index_label="Time")
        pd.DataFrame(output_data).to_csv(
            f"{self.destination_folder}/PTI_Inversion.csv",
            index_label="Time",
            mode="a",
            header=False
        )
        logging.info("PTI Inversion calculated.")

    def _prepare_data(self, pti_measurement) -> tuple[dict[str, str], dict[str, np.ndarray]]:
        units: dict[str, str] = {
            "Interferometric Phase": "rad", "Symmetry": "1",
            "Sensitivity CH1": "V/rad", "Sensitivity CH2": "V/rad",
            "Sensitivity CH3": "V/rad"}
        output_data = {"Interferometric Phase": self.interferometer.phase,
                       "Symmetry": self.symmetry}
        for i in range(3):
            output_data[f"Sensitivity CH{i + 1}"] = self.sensitivity[i]
        if pti_measurement:
            units["PTI Signal"] = "µrad"
            output_data["PTI Signal"] = self.pti_signal
        output_data["Interferometric Phase"] = np.array(output_data["Interferometric Phase"])
        return units, output_data

    def _calculate_online(self) -> None:
        output_data = {}
        if self.init_header:
            output_data["Interferometric Phase"] = "rad"
            for channel in range(1, 4):
                output_data[f"Sensitivity CH{channel}"] = "V/rad"
            output_data["Symmetry"] = "1"
            output_data["PTI Signal"] = "µrad"
            pd.DataFrame(output_data, index=["s"]).to_csv(
                f"{self.destination_folder}/PTI_Inversion.csv", index_label="Time")
            self.init_header = False
        self.interferometer.calculate_phase(self.dc_signals)
        self.calculate_pti_signal()
        self.calculate_sensitivity()
        now = datetime.now()
        time_stamp = str(now.strftime("%Y-%m-%d %H:%M:%S"))
        output_data = {"Interferometric Phase": self.interferometer.phase,
                       "Sensitivity CH1": self.sensitivity[0],
                       "Sensitivity CH2": self.sensitivity[1],
                       "Sensitivity CH3": self.sensitivity[2],
                       "Symmetry": self.symmetry, "PTI Signal": self.pti_signal}
        try:
            pd.DataFrame(output_data, index=[time_stamp]).to_csv(
                f"{self.destination_folder}/PTI_Inversion.csv", mode="a",
                index_label="Time", header=False)
        except PermissionError:
            logging.info("Could not write data. Missing values are: %s at %s.",
                         str(output_data)[1:-1], str(time_stamp))

    def __call__(self, live=True) -> None:
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
    REF_VOLTAGE: float = 3.3  # V
    REF_PERIOD: int = 100  # Samples
    SAMPLES: int = minipti.hardware.motherboard.Driver.NUMBER_OF_SAMPLES
    DC_RESOLUTION: int = (1 << 12) - 1  # 12 Bit ADC
    AC_RESOLUTION: int = (1 << (16 - 1)) - 1  # 16 bit ADC with 2 complement
    AMPLIFICATION: int = 100  # Theoretical value given by the hardware

    UNTIL_MICRO_SECONDS = -3

    def __init__(self):
        self.dc_coupled: NDArray[Shape["3", f"{Decimation.SAMPLES}"], UInt16] | None = None
        self.ac_coupled: NDArray[Shape["3", f"{Decimation.SAMPLES}"], Int16] | None = None
        self.dc_signals: np.ndarray | None = None
        self.lock_in: LockIn = LockIn(np.empty(shape=3), np.empty(shape=3))
        self.ref: NDArray[Shape["1", f"{Decimation.SAMPLES}"], UInt16] | None = None
        self.save_raw_data: bool = False
        self.in_phase: np.ndarray = np.cos(2 * np.pi / Decimation.REF_PERIOD *
                                           np.arange(0, Decimation.SAMPLES))
        self.quadrature: np.ndarray = np.sin(2 * np.pi / Decimation.REF_PERIOD *
                                             np.arange(0, Decimation.SAMPLES))
        self.destination_folder: str = "."
        self.file_path: str = ""
        self.init_header: bool = True

    def process_raw_data(self) -> None:
        """
        Reads the binary data and save it into numpy arrays. The data is saved into npy archives in
        debug mode.
        """
        if self.save_raw_data:
            self.save()
        self.dc_coupled = self.dc_coupled * Decimation.REF_VOLTAGE / Decimation.DC_RESOLUTION
        self.ac_coupled = self.ac_coupled * Decimation.REF_VOLTAGE / (
                    Decimation.AMPLIFICATION * Decimation.AC_RESOLUTION)

    def save(self) -> None:
        with h5py.File(f"{self.destination_folder}/raw_data.h5", "a") as h5f:
            now = datetime.now()
            time_stamp = str(
                now.strftime("%Y-%m-%d %H:%M:%S:%S.%f")[:Decimation.UNTIL_MICRO_SECONDS]
            )
            h5f.create_group(time_stamp)
            h5f[time_stamp]["Ref"] = self.ref
            h5f[time_stamp]["AC"] = self.ac_coupled
            h5f[time_stamp]["DC"] = self.dc_coupled

    def get_raw_data(self) -> Generator[None, None, None]:
        with h5py.File(self.file_path, "r") as h5f:
            for sample_package in h5f.values():
                self.dc_coupled = np.array(sample_package["DC"]).T
                self.ac_coupled = np.array(sample_package["AC"]).T
                yield None

    def calculate_dc(self) -> None:
        """
        Applies a low pass to the DC-coupled signals and decimate it to 1 s values.
        """
        self.dc_signals = np.mean(self.dc_coupled, axis=1)

    def common_mode_noise_reduction(self) -> None:
        noise_factor = np.sum(self.ac_coupled, axis=0) / sum(self.dc_signals)
        for channel in range(3):
            self.ac_coupled[channel] = self.ac_coupled[channel] - noise_factor * self.dc_signals[
                channel]

    def lock_in_amplifier(self) -> None:
        ac_x = np.mean(self.ac_coupled * self.in_phase, axis=1)
        ac_y = np.mean(self.ac_coupled * self.quadrature, axis=1)
        self.lock_in.phase = np.arctan2(ac_y, ac_x)
        self.lock_in.amplitude = np.sqrt(ac_x ** 2 + ac_y ** 2)

    def _calculate_decimation(self) -> None:
        self.calculate_dc()
        self.common_mode_noise_reduction()
        self.lock_in_amplifier()
        output_data = {}
        for channel in range(3):
            output_data[f"Lock In Amplitude CH{channel + 1}"] = self.lock_in.amplitude[channel]
            output_data[f"Lock In Phase CH{channel + 1}"] = np.rad2deg(self.lock_in.phase[channel])
            output_data[f"DC CH{channel + 1}"] = self.dc_signals[channel]
        now = datetime.now()
        time_stamp = str(now.strftime("%Y-%m-%d %H:%M:%S"))
        try:
            pd.DataFrame(output_data, index=[time_stamp]).to_csv(
                f"{self.destination_folder}/Decimation.csv", mode="a",
                index_label="Time", header=False)
        except PermissionError:
            logging.info("Could not write data. Missing values are: %s at %s.",
                         str(output_data)[1:-1], str(time_stamp))

    def __call__(self, live=True) -> None:
        if self.init_header:
            output_data = {}
            for channel in range(3):
                output_data[f"Lock In Amplitude CH{channel + 1}"] = "V"
                output_data[f"Lock In Phase CH{channel + 1}"] = "deg"
                output_data[f"DC CH{channel + 1}"] = "V"
            pd.DataFrame(output_data, index=["s"]).to_csv(
                f"{self.destination_folder}/Decimation.csv", index_label="Time")
            self.init_header = False
        if live:
            self.process_raw_data()
            self._calculate_decimation()
        else:
            for _ in self.get_raw_data():
                self._calculate_decimation()
            logging.info("Finished decimation")
            logging.info("Saved results in %s", str(self.destination_folder))
