"""
API for PTI Inversion and Decimation.
"""
import logging
import os
from collections.abc import Generator
from dataclasses import dataclass
from datetime import datetime
from typing import Final, Union, NoReturn

import h5py
import numpy as np
import pandas as pd
from overrides import override

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
    MICRO_RAD: Final[float] = 1e6
    LOCK_IN_HEADERS: Final = [([f"X{i}" for i in range(1, 4)], [f"Y{i}" for i in range(1, 4)]),
                              ([f"x{i}" for i in range(1, 4)], [f"y{i}" for i in range(1, 4)]),
                              ([f"Lock In Amplitude CH{i}" for i in range(1, 4)],
                              [f"Lock In Phase CH{i}" for i in range(1, 4)]),
                              ([f"AC CH{i}" for i in range(1, 4)],
                              [f"AC Phase CH{i}" for i in range(1, 4)])]

    def __init__(self, response_phases=None, sign=1, interferometer=None,
                 settings_path=f"{os.path.dirname(__file__)}/configs/settings.csv"):
        self.response_phases: np.ndarray = response_phases
        self.pti_signal: Union[float, np.ndarray] = 0
        self.settings_path: str = settings_path
        self.init_header: bool = True
        self.sign: int = sign  # Makes the pti signal positive if it isn't
        self.interferometer: interferometry.Interferometer = interferometer
        self.destination_folder: str = os.getcwd()
        self.load_response_phase()

    @override
    def __repr__(self) -> str:
        class_name = self.__class__.__name__
        representation = f"{class_name}(response_phases={self.response_phases}," \
                         f" pti_signal={self.pti_signal})"
        return representation

    @override
    def __str__(self) -> str:
        return f"Interferometric Phase: {self.interferometer.phase}\n PTI signal: {self.pti_signal}"

    def load_response_phase(self) -> None:
        settings = pd.read_csv(self.settings_path, index_col="Setting")
        self.response_phases = settings.loc["Response Phases [rad]"].to_numpy()

    def _calculate_sign(self, channel: int) -> int:
        try:
            sign = np.ones(shape=len(self.interferometer.phase))
            sign[np.sin(self.interferometer.phase - self.interferometer.output_phases[channel]) < 0] = -1
        except TypeError:
            sign = 1 if np.sin(self.interferometer.phase - self.interferometer.output_phases[channel]) >= 0 else -1
        return sign

    def calculate_pti_signal(self, lock_in: LockIn) -> None:
        try:
            pti_signal = np.zeros(shape=(len(self.interferometer.phase)))
        except TypeError:
            pti_signal = 0
        for channel in range(3):
            sign = self._calculate_sign(channel)
            response_phase = self.response_phases[channel]
            demodulated_signal = lock_in.amplitude[channel] * np.cos(lock_in.phase[channel] - response_phase)
            pti_signal += demodulated_signal * sign
        total_sensitivity = np.sum(self.interferometer.sensitivity, axis=0)
        self.pti_signal = -pti_signal / total_sensitivity
        self.pti_signal *= Inversion.MICRO_RAD * self.sign

    @staticmethod
    def _get_lock_in_data(data: pd.DataFrame) -> Union[LockIn, NoReturn]:
        for lock_in_header_1, lock_in_header_2 in Inversion.LOCK_IN_HEADERS:
            if set(lock_in_header_1).issubset(set(data.columns)) and set(lock_in_header_2).issubset(set(data.columns)):
                if lock_in_header_1[0].casefold() == "x1":
                    in_phase_component = data[lock_in_header_1].to_numpy().T
                    quadrature_component = data[lock_in_header_2].to_numpy().T
                    return LockIn(np.sqrt(in_phase_component ** 2 + quadrature_component ** 2),
                                  np.arctan2(quadrature_component, in_phase_component))
                else:
                    return LockIn(data[lock_in_header_1].to_numpy().T, data[lock_in_header_2].to_numpy().T)
        raise KeyError("Invalid Keys for Lock In or Lock In Data not existing")

    @staticmethod
    def _get_dc_signals(data: pd.DataFrame) -> Union[np.ndarray, NoReturn]:
        for header in interferometry.Interferometer.DC_HEADERS:
            try:
                return data[header].to_numpy()
            except KeyError:
                continue
        else:
            raise KeyError("Invalid key for DC values given")

    def _calculate_offline(self, file_path: str) -> None:
        data = pd.read_csv(file_path, sep=None, engine="python", skiprows=[1])
        dc_signals = Inversion._get_dc_signals(data)
        self.interferometer.calculate_phase(dc_signals)
        self.interferometer.calculate_sensitivity()
        try:
            lock_in_signals = Inversion._get_lock_in_data(data)
            self.calculate_pti_signal(lock_in_signals)
            pti_measurement = True
        except KeyError:
            pti_measurement = False
        self._save_data(pti_measurement)

    def _save_data(self, pti_measurement: bool) -> None:
        units, output_data = self._prepare_data(pti_measurement)
        pd.DataFrame(units, index=["s"]).to_csv(f"{self.destination_folder}/PTI_Inversion.csv",
                                                index_label="Time")
        pd.DataFrame(output_data).to_csv(f"{self.destination_folder}/PTI_Inversion.csv", index_label="Time",
                                         mode="a",  header=False)
        logging.info("PTI Inversion calculated.")
        logging.info("Saved results in %s", str(self.destination_folder))

    def _prepare_data(self, pti_measurement) -> tuple[dict[str, str], dict[str, Union[np.ndarray, float]]]:
        units: dict[str, str] = {"Interferometric Phase": "rad",
                                 "Sensitivity CH1": "V/rad",
                                 "Sensitivity CH2": "V/rad",
                                 "Sensitivity CH3": "V/rad"}
        output_data = {"Interferometric Phase": self.interferometer.phase}
        for i in range(3):
            output_data[f"Sensitivity CH{i + 1}"] = self.interferometer.sensitivity[i]
        if pti_measurement:
            units["PTI Signal"] = "µrad"
            output_data["PTI Signal"] = self.pti_signal
        return units, output_data

    def _calculate_online(self, lock_in: LockIn, dc_signals: np.ndarray) -> None:
        output_data = {"Time": "H:M:S"}
        if self.init_header:
            output_data["Interferometric Phase"] = "rad"
            for channel in range(1, 4):
                output_data[f"Sensitivity CH{channel}"] = "V/rad"
            output_data["PTI Signal"] = "µrad"
            pd.DataFrame(output_data, index=["Y:M:D"]).to_csv(f"{self.destination_folder}/PTI_Inversion.csv",
                                                              index_label="Date")
            self.init_header = False
        self.interferometer.calculate_phase(dc_signals)
        self.interferometer.calculate_sensitivity()
        self.calculate_pti_signal(lock_in)
        self._save_live_data()

    def _save_live_data(self) -> None:
        now = datetime.now()
        date = str(now.strftime("%Y-%m-%d"))
        time = str(now.strftime("%H:%M:%S"))
        output_data = {"Time": time,
                       "Interferometric Phase": self.interferometer.phase,
                       "Sensitivity CH1": self.interferometer.sensitivity[0],
                       "Sensitivity CH2": self.interferometer.sensitivity[1],
                       "Sensitivity CH3": self.interferometer.sensitivity[2],
                       "PTI Signal": self.pti_signal}
        try:
            pd.DataFrame(output_data, index=[date]).to_csv(f"{self.destination_folder}/PTI_Inversion.csv",
                                                           mode="a", index_label="Date", header=False)
        except PermissionError:
            logging.warning("Could not write data. Missing values are: %s at %s.",
                            str(output_data)[1:-1], date + " " + time)

    def invert(self, lock_in: LockIn = None, dc_signals: np.ndarray = None, live=False, file_path="") -> None:
        if live:
            try:
                self._calculate_online(lock_in, dc_signals)
            except RuntimeWarning:
                logging.error("Could not calculate, intensities are too small")
        else:
            self._calculate_offline(file_path)


@dataclass
class RawData:
    ref: Union[np.ndarray[np.uint16], None]
    dc:  Union[np.ndarray[np.uint16], None]
    ac:  Union[np.ndarray[np.int16], None]


class Decimation:
    """
    Provided an API for the PTI decimation described in [1] from Weingartner et al.

    [1]: Waveguide based passively demodulated photo-thermal
         interferometer for aerosol measurements
    """
    REF_VOLTAGE: float = 3.3  # V
    REF_PERIOD: int = 100  # Samples
    DC_RESOLUTION: int = (1 << 12) - 1  # 12 Bit ADC
    AC_RESOLUTION: int = (1 << (16 - 1)) - 1  # 16 bit ADC with 2 complement
    AMPLIFICATION: int = 100  # Theoretical value given by the hardware

    UNTIL_MICRO_SECONDS = -3

    def __init__(self):

        self._average_period: int = 8000  # Recommended default value
        self.raw_data = RawData(None, None, None)
        self.dc_signals: Union[np.ndarray, None] = None
        self.lock_in: LockIn = LockIn(np.empty(shape=3), np.empty(shape=3))
        self.save_raw_data: bool = False
        self.destination_folder: str = "."
        self.file_path: str = ""
        self.init_header: bool = True
        self.init_raw_data: bool = True
        self._update_lock_in_look_up_table()

    @property
    def average_period(self) -> int:
        return self._average_period

    @average_period.setter
    def average_period(self, average_period: int) -> None:
        self._average_period = average_period
        self._update_lock_in_look_up_table()

    def _update_lock_in_look_up_table(self) -> None:
        self.in_phase: np.ndarray = np.cos(2 * np.pi / Decimation.REF_PERIOD * np.arange(0, self.average_period))
        self.quadrature: np.ndarray = np.sin(2 * np.pi / Decimation.REF_PERIOD * np.arange(0, self.average_period))

    def process_raw_data(self) -> None:
        """
        Reads the binary data and save it into numpy arrays. The data is saved into npy archives in
        debug mode.
        """
        if self.save_raw_data:
            self.save()
        self.raw_data.dc = self.raw_data.dc * Decimation.REF_VOLTAGE / Decimation.DC_RESOLUTION
        self.raw_data.ac = self.raw_data.ac * Decimation.REF_VOLTAGE / (Decimation.AMPLIFICATION
                                                                        * Decimation.AC_RESOLUTION)

    def save(self) -> None:
        with h5py.File(f"{self.destination_folder}/raw_data.hdf5", "a") as h5f:
            now = datetime.now()
            time_stamp = str(now.strftime("%Y-%m-%d %H:%M:%S:%S.%f")[:Decimation.UNTIL_MICRO_SECONDS])
            h5f.create_group(time_stamp)
            h5f[time_stamp]["Ref"] = self.raw_data.ref
            h5f[time_stamp]["AC"] = self.raw_data.ac
            h5f[time_stamp]["DC"] = self.raw_data.dc

    def calculate_dc(self) -> None:
        """
        Applies a low pass to the DC-coupled _signals and decimate it to 1 s values.
        """
        self.dc_signals = np.mean(self.raw_data.dc, axis=1)

    def common_mode_noise_reduction(self) -> None:
        noise_factor = np.sum(self.raw_data.ac, axis=0) / sum(self.dc_signals)
        for channel in range(3):
            self.raw_data.ac[channel] = self.raw_data.ac[channel] - noise_factor * self.dc_signals[channel]

    def lock_in_amplifier(self) -> None:
        ac_x = np.mean(self.raw_data.ac * self.in_phase, axis=1)
        ac_y = np.mean(self.raw_data.ac * self.quadrature, axis=1)
        self.lock_in.phase = np.arctan2(ac_y, ac_x)
        self.lock_in.amplitude = np.sqrt(ac_x ** 2 + ac_y ** 2)

    def _calculate_decimation(self) -> None:
        self.calculate_dc()
        self.common_mode_noise_reduction()
        self.lock_in_amplifier()
        output_data = {}
        now = datetime.now()
        date = str(now.strftime("%Y-%m-%d"))
        time = str(now.strftime("%H:%M:%S"))
        output_data["Time"] = time
        for channel in range(3):
            output_data[f"Lock In Amplitude CH{channel + 1}"] = self.lock_in.amplitude[channel]
            output_data[f"Lock In Phase CH{channel + 1}"] = self.lock_in.phase[channel]
            output_data[f"DC CH{channel + 1}"] = self.dc_signals[channel]
        try:
            pd.DataFrame(output_data, index=[date]).to_csv(f"{self.destination_folder}/Decimation.csv", mode="a",
                                                           index_label="Date", header=False)
        except PermissionError:
            logging.warning("Could not write data. Missing values are: %s at %s.",
                            str(output_data)[1:-1], date + " " + time)

    def get_raw_data(self) -> Generator[None, None, None]:
        with h5py.File(self.file_path, "r") as h5f:
            for sample_package in h5f.values():
                self.raw_data.dc = np.array(sample_package["DC"], dtype=np.uint16).T
                self.raw_data.ac = np.array(sample_package["AC"], dtype=np.int16).T
                yield None

    def decimate(self, live=False) -> None:
        if self.init_header:
            output_data = {"Time": "H:M:S"}
            for channel in range(3):
                output_data[f"Lock In Amplitude CH{channel + 1}"] = "V"
                output_data[f"Lock In Phase CH{channel + 1}"] = "rad"
                output_data[f"DC CH{channel + 1}"] = "V"
            pd.DataFrame(output_data, index=["Y:M:D"]).to_csv(f"{self.destination_folder}/Decimation.csv",
                                                              index_label="Date")
            self.init_header = False
        if live:
            # if self.save_raw_data and self.init_raw_data:
            #    self._save_meta_data()
            self.process_raw_data()
            self._calculate_decimation()
        else:
            get_raw_data: Generator[None, None, None] = self.get_raw_data()
            for _ in get_raw_data:
                self._calculate_decimation()
            logging.info("Finished decimation")
            logging.info("Saved results in %s", str(self.destination_folder))
