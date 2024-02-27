"""
API for PTI Inversion and Decimation.
"""
import itertools
import logging
import os
from collections.abc import Generator
from dataclasses import dataclass
from datetime import datetime
from typing import Final

import h5py
import numpy as np
import pandas as pd

import minipti
import minipti.algorithm.interferometry as interferometry
from minipti.algorithm import _utilities


@dataclass
class LockIn:
    amplitude: np.ndarray
    phase: np.ndarray


@dataclass
class RawData:
    ref: np.ndarray[np.uint16] | None
    dc: np.ndarray[np.uint16] | None
    ac: np.ndarray[np.int16] | None


@dataclass(frozen=True)
class DecimationSettings:
    amplification: float
    ref_voltage: float
    dc_resolution: int
    ac_resolution: int


class Decimation:
    """
    Provided an API for the PTI decimation described in [1] from Weingartner et al.

    [1]: Waveguide based passively demodulated photo-thermal
         interferometer for aerosol measurements
    """
    REF_VOLTAGE: Final = 3.3  # V
    SAMPLE_PERIOD: Final = 8e3
    REF_PERIOD: Final = 100  # Samples

    def __init__(self):

        self._average_period: int = 8000  # Recommended default value
        self.raw_data = RawData(None, None, None)
        self.dc_signals: np.ndarray | None = None
        self.lock_in: LockIn = LockIn(np.empty(shape=3), np.empty(shape=3))
        self.save_raw_data: bool = False
        self.destination_folder: str = "."
        self.file_path: str = ""
        self.init_header: bool = True
        self.use_common_mode_noise_reduction = False
        self.configuration = _utilities.load_configuration(DecimationSettings, "pti", "decimation")
        self._index = itertools.count()
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
        self.raw_data.dc = self.raw_data.dc * Decimation.REF_VOLTAGE / self.configuration.dc_resolution
        self.raw_data.ac = self.raw_data.ac * Decimation.REF_VOLTAGE / (self.configuration.amplification
                                                                        * self.configuration.ac_resolution)

    def save(self) -> None:
        with h5py.File(f"{self.destination_folder}/{minipti.path_prefix}_raw_data.hdf5", "a") as h5f:
            i = next(self._index)
            now = datetime.now()
            h5f.create_group(str(i))
            h5f[i]["Time"] = str(now.strftime(r"%Y-%m-%d %H:%M:%S"))
            h5f[i]["Ref"] = self.raw_data.ref
            h5f[i]["AC"] = self.raw_data.ac
            h5f[i]["DC"] = self.raw_data.dc

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
        self.lock_in.phase = np.arctan2(ac_y, ac_x) % (2 * np.pi)
        self.lock_in.amplitude = np.sqrt(ac_x ** 2 + ac_y ** 2)

    def _calculate_decimation(self) -> None:
        self.calculate_dc()
        if False:# self.use_common_mode_noise_reduction:
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
            pd.DataFrame(output_data, index=[date]).to_csv(
                f"{self.destination_folder}/{minipti.path_prefix}_Decimation.csv",
                mode="a",
                index_label="Date",
                header=False
            )
        except PermissionError:
            logging.warning("Could not write data. Missing values are: %s at %s.",
                            str(output_data)[1:-1], date + " " + time)

    def get_raw_data(self) -> Generator[None, None, None]:
        with h5py.File(self.file_path, "r") as h5f:
            for sample_package in h5f.values():
                self.raw_data.dc = np.array(sample_package["DC"], dtype=np.uint16)
                self.raw_data.ac = np.array(sample_package["AC"], dtype=np.int16)
                self.average_period = self.raw_data.ac.shape[1]
                yield None

    def run(self, live=False) -> None:
        if self.init_header:
            output_data = {"Time": "H:M:S"}
            for channel in range(3):
                output_data[f"Lock In Amplitude CH{channel + 1}"] = "V"
                output_data[f"Lock In Phase CH{channel + 1}"] = "rad"
                output_data[f"DC CH{channel + 1}"] = "V"
            pd.DataFrame(output_data, index=["Y:M:D"]).to_csv(
                f"{self.destination_folder}/{minipti.path_prefix}_Decimation.csv",
                index_label="Date"
            )
            self.init_header = False
        if live:
            if self.save_raw_data:
                self.save()
            self.process_raw_data()
            self._calculate_decimation()
        else:
            get_raw_data: Generator[None, None, None] = self.get_raw_data()
            for _ in get_raw_data:
                self.process_raw_data()
                self._calculate_decimation()
            logging.info("Finished decimation")
            logging.info("Saved results in %s", str(self.destination_folder))


@dataclass(frozen=True)
class InversionSettings:
    resolution: float
    sign: int


class Inversion:
    """
    Provided an API for the PTI algorithm described in [1] from Weingartner et al.

    [1]: Waveguide based passively demodulated photo-thermal
         interferometer for aerosol measurements
    """
    LOCK_IN_HEADERS: Final = [([f"X{i}" for i in range(1, 4)], [f"Y{i}" for i in range(1, 4)]),
                              ([f"x{i}" for i in range(1, 4)], [f"y{i}" for i in range(1, 4)]),
                              ([f"Lock In Amplitude CH{i}" for i in range(1, 4)],
                               [f"Lock In Phase CH{i}" for i in range(1, 4)]),
                              ([f"AC CH{i}" for i in range(1, 4)],
                               [f"AC Phase CH{i}" for i in range(1, 4)])]

    CONFIGURATION: Final[InversionSettings] = _utilities.load_configuration(
        InversionSettings,
        "pti",
        "inversion"
    )

    def __init__(self, response_phases=None, interferometer=None, decimation=Decimation(),
                 settings_path=f"{minipti.MODULE_PATH}/algorithm/configs/settings.csv"):
        self.response_phases: np.ndarray = response_phases
        self.pti_signal: float | np.ndarray = 0
        self.settings_path: str = settings_path
        self.init_header: bool = True
        self.interferometer: interferometry.Interferometer = interferometer
        self.decimation = decimation
        self.destination_folder: str = os.getcwd()
        self.load_response_phase()

    def __repr__(self) -> str:
        class_name = self.__class__.__name__
        representation = f"{class_name}(response_phases={self.response_phases}," \
                         f" pti_signal={self.pti_signal})"
        return representation

    def __str__(self) -> str:
        return f"Interferometric Phase: {self.interferometer.phase}\n PTI signal: {self.pti_signal}"

    def calculate_response_phase(self, file_path: str) -> None:
        self._get_lock_in_data(file_path)
        variances = [np.mean(np.var(self.decimation.lock_in.phase.T[i:i + 100], axis=0))
                     for i in range(self.decimation.lock_in.phase.size // 3 - 100)]
        self.response_phases = self.decimation.lock_in.phase.T[np.argmin(variances)] % (2 * np.pi)
        self.response_phases[self.response_phases > np.pi] -= np.pi
        logging.info(f"Calculated Response Phases {self.response_phases}  with standard deviation "
                     f"{np.sqrt(min(variances)):.2E} rad")

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

    def calculate_pti_signal(self) -> None:
        try:
            pti_signal = np.zeros(shape=(len(self.interferometer.phase)))
        except TypeError:
            pti_signal = 0
        for channel in range(3):
            sign = self._calculate_sign(channel)
            response_phase = self.response_phases[channel]
            demodulated_signal = self.decimation.lock_in.amplitude[channel] * np.cos(
                self.decimation.lock_in.phase[channel] - response_phase)
            pti_signal += demodulated_signal * sign
        total_sensitivity = np.sum(self.interferometer.sensitivity, axis=0)
        self.pti_signal = -pti_signal / total_sensitivity
        self.pti_signal *= Inversion.CONFIGURATION.resolution * Inversion.CONFIGURATION.sign

    def _get_lock_in_data(self, file_path: str) -> None:
        data = pd.read_csv(file_path, sep=None, engine="python", skiprows=[1])
        for lock_in_header_1, lock_in_header_2 in Inversion.LOCK_IN_HEADERS:
            if set(lock_in_header_1).issubset(set(data.columns)) and set(lock_in_header_2).issubset(set(data.columns)):
                if lock_in_header_1[0].casefold() == "x1":
                    in_phase_component = data[lock_in_header_1].to_numpy().T
                    quadrature_component = data[lock_in_header_2].to_numpy().T
                    self.decimation.lock_in = LockIn(np.sqrt(in_phase_component ** 2 + quadrature_component ** 2),
                                                     np.arctan2(quadrature_component, in_phase_component) % (2 * np.pi))
                    break
                else:
                    self.decimation.lock_in = LockIn(data[lock_in_header_1].to_numpy().T,
                                                     data[lock_in_header_2].to_numpy().T)
                    break
        else:
            raise KeyError("Invalid Keys for Lock In or Lock In Data not existing")

    def _calculate_offline(self, file_path: str) -> None:
        if file_path:
            self._get_lock_in_data(file_path)
        self.interferometer.run(file_path=file_path)
        self.calculate_pti_signal()
        self._save_data()

    def _save_data(self) -> None:
        units: dict[str, str] = {"PTI Signal": "µrad"}
        output_data = {"PTI Signal": self.pti_signal}
        pd.DataFrame(units, index=["s"]).to_csv(
            f"{self.destination_folder}/Offline_PTI_Inversion.csv",
            index_label="Time")
        pd.DataFrame(output_data).to_csv(
            f"{self.destination_folder}/Offline_PTI_Inversion.csv", index_label="Time",
            mode="a", header=False
        )
        logging.info("PTI Inversion calculated.")
        logging.info("Saved results in %s", str(self.destination_folder))

    def _calculate_online(self) -> None:
        output_data = {"Time": "H:M:S"}
        if self.init_header:
            output_data["PTI Signal"] = "µrad"
            pd.DataFrame(output_data, index=["Y:M:D"]).to_csv(
                f"{self.destination_folder}/{minipti.path_prefix}_PTI_Inversion.csv",
                index_label="Date"
            )
            self.init_header = False
        self.calculate_pti_signal()
        self._save_live_data()

    def _save_live_data(self) -> None:
        now = datetime.now()
        date = str(now.strftime("%Y-%m-%d"))
        time = str(now.strftime("%H:%M:%S"))
        output_data = {"Time": time, "PTI Signal": self.pti_signal}
        try:
            pd.DataFrame(output_data, index=[date]).to_csv(
                f"{self.destination_folder}/{minipti.path_prefix}_PTI_Inversion.csv",
                mode="a",
                index_label="Date",
                header=False
            )
        except PermissionError:
            logging.warning(
                "Could not write data. Missing values are: %s at %s.",
                str(output_data)[1:-1], date + " " + time
            )

    def run(self, live=False, file_path="") -> None:
        if live:
            try:
                self._calculate_online()
            except RuntimeWarning:
                logging.error("Could not calculate, intensities are too small")
        else:
            self._calculate_offline(file_path)
