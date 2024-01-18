"""
API for characterisation and phases of an interferometer.
"""
import logging
import os
import threading
import typing
from collections import defaultdict
from collections.abc import Generator
from dataclasses import dataclass
from datetime import datetime
from typing import Final, Union

import numpy as np
import pandas as pd
from scipy import optimize, linalg

import minipti
from minipti.algorithm import _utilities


class _Locks(typing.NamedTuple):
    output_phases: threading.Lock = threading.Lock()
    amplitudes: threading.Lock = threading.Lock()
    offsets: threading.Lock = threading.Lock()
    characteristic_parameter: threading.Lock = threading.Lock()


@dataclass
class Symmetry:
    absolute: Union[float, np.ndarray] = 100
    relative: Union[float, np.ndarray] = 100


@dataclass
class CharacteristicParameter:
    amplitudes: np.ndarray[float]
    offsets: np.ndarray[float]
    output_phases: np.ndarray[float]


class CharacterizationError(Exception):
    pass


@dataclass(frozen=True)
class Algorithm:
    lsq: bool
    ellipse: bool


@dataclass(frozen=True)
class InterferometerSettings:
    algorithm: Algorithm


class Interferometer:
    """
    Provides the API for calculating the interferometric phase based on its characteristic values.
    """
    DC_HEADERS: Final[list] = [[f"PD{i}" for i in range(1, 4)],
                               [f"DC CH{i}" for i in range(1, 4)]]

    OPTIMAL_SYMMETRY: Final[float] = 86.58  # %

    CONFIGURATION: Final[InterferometerSettings] = _utilities.load_configuration(
        InterferometerSettings,
        "interferometry",
        "interferometer"
    )

    def __init__(self, settings_path=f"{os.path.dirname(__file__)}/configs/settings.csv", interferometer_dimension=3,
                 decimation_filepath="data/Decimation.csv"):
        self.settings_path = settings_path
        self.decimation_filepath = decimation_filepath
        self.phase: Union[float, np.ndarray] = 0
        self._characteristic_parameter = CharacteristicParameter(amplitudes=np.zeros(interferometer_dimension),
                                                                 offsets=np.zeros(interferometer_dimension),
                                                                 output_phases=np.array([0,
                                                                                         2 * np.pi / 3,
                                                                                         4 * np.pi / 3]))
        self.symmetry = Symmetry()
        self._locks = _Locks()
        self.sensitivity: np.ndarray = np.empty(shape=interferometer_dimension)
        self.destination_folder: str = os.getcwd()
        self.init_online: bool = True
        self.intensities: Union[None, np.ndarray] = None
        self.dimension = interferometer_dimension
        self.output_data_frame = pd.DataFrame()

    def load_settings(self) -> None:
        """
        Read the characteristic values (amplitude, offset and output phase).
        """
        settings = pd.read_csv(self.settings_path, index_col="Setting")
        self.output_phases = np.deg2rad(settings.loc["Output Phases [deg]"].to_numpy())
        self.amplitudes = settings.loc["Amplitude [V]"].to_numpy()
        self.offsets = settings.loc["Offset [V]"].to_numpy()

    def __eq__(self, other) -> bool:
        return self.amplitudes == other.amplitudes and self.offsets == other.amplitudes and \
            self.output_phases == other.output_phases

    def __repr__(self) -> str:
        class_name = self.__class__.__name__
        representation = f"{class_name}(setting_path={self.settings_path}," \
                         f" decimation_path={self.decimation_filepath}\n"
        representation += f"phae={self.phase}, output_phases={self.output_phases}," \
                          f" amplitudes={self.amplitudes}\n"
        representation += f"offsets={self.offsets}) phases={self.phase}"
        return representation

    def __str__(self) -> str:
        output_phase_str = "Output Phases [deg]:\n"
        amplitude_str = "Amplitudes [V]:\n"
        offset_str = "Offsets [V]:\n"
        for i in range(self.dimension - 1):
            output_phase_str += f"CH {i + 1}: {np.round(np.rad2deg(self.output_phases[i]), 2)}, "
            amplitude_str += f"CH {i + 1}: {np.round(self.amplitudes[i], 2)}, "
            offset_str += f"CH {i + 1}: {np.round(self.offsets[i], 2)}, "
        i = self.dimension - 1
        output_phase_str += f"CH{i}: {np.round(np.rad2deg(self.output_phases[i]), 2)}"
        amplitude_str += f"CH{i}: {np.round(self.amplitudes[i], 2)}"
        offset_str += f"CH{i}: {np.round(self.offsets[i], 2)}"
        return amplitude_str + "\n" + offset_str + "\n" + output_phase_str

    @property
    def characteristic_parameter(self) -> CharacteristicParameter:
        with self._locks.characteristic_parameter:
            return self._characteristic_parameter

    @characteristic_parameter.setter
    def characteristic_parameter(self, new_parameter: CharacteristicParameter) -> None:
        with self._locks.characteristic_parameter:
            self._characteristic_parameter = new_parameter

    @property
    def amplitudes(self) -> np.ndarray:
        with self._locks.amplitudes:
            amplitudes = self._characteristic_parameter.amplitudes
        return amplitudes

    @amplitudes.setter
    def amplitudes(self, amplitudes: np.ndarray):
        with self._locks.amplitudes:
            self._characteristic_parameter.amplitudes = amplitudes

    @property
    def offsets(self) -> np.ndarray:
        with self._locks.offsets:
            offsets = self._characteristic_parameter.offsets
        return offsets

    @offsets.setter
    def offsets(self, offsets: np.ndarray):
        with self._locks.offsets:
            self._characteristic_parameter.offsets = offsets

    @property
    def output_phases(self) -> np.ndarray:
        with self._locks.output_phases:
            output_phase = self._characteristic_parameter.output_phases
        return output_phase

    @output_phases.setter
    def output_phases(self, output_phases: np.ndarray):
        with self._locks.output_phases:
            self._characteristic_parameter.output_phases = output_phases

    def calculate_amplitudes(self, intensity: Union[np.ndarray, None] = None):
        """
        The amplitude of perfect sine wave can be calculated according to A = (I_max - I_min) / 2.
        This function is only used as approximation.
        """
        if intensity is None:
            intensity = self.intensities
        if intensity.shape[0] == self.dimension:
            self.amplitudes = (np.max(intensity, axis=1) - np.min(intensity, axis=1)) / 2
        else:
            self.amplitudes = (np.max(intensity, axis=0) - np.min(intensity, axis=0)) / 2

    def calculate_offsets(self, intensity: Union[np.ndarray, None] = None):
        """
        The offset of perfect sine wave can be calculated according to B = (I_max + I_min) / 2.
        This function is only used as approximation.
        """
        if intensity is None:
            intensity = self.intensities
        if intensity.shape[0] == self.dimension:
            self.offsets = (np.max(intensity, axis=1) + np.min(intensity, axis=1)) / 2
        else:
            self.offsets = (np.max(intensity, axis=0) + np.min(intensity, axis=0)) / 2

    def _error_function(self, intensity: np.ndarray) -> typing.Callable:
        intensity_scaled = (intensity - self.offsets) / self.amplitudes

        def error(phase: np.ndarray):
            try:
                return np.cos(phase - self.output_phases) - intensity_scaled
            except TypeError:
                return np.cos(np.array(phase) - np.array(self.output_phases)) - intensity_scaled

        return error

    def _error_function_df(self, phase: np.ndarray) -> np.ndarray:
        try:
            return -np.sin(phase - self.output_phases).reshape((self.dimension, 1))
        except AttributeError:
            return -np.sin(np.array(phase) - np.array(self.output_phases)).reshape((self.dimension, 1))

    def _calculate_phase(self, intensity: np.ndarray) -> np.ndarray:
        x0 = optimize.brute(func=lambda x: np.sum(self._error_function(intensity)(x) ** 2),
                            ranges=(slice(0, 2 * np.pi, 0.1),))[0]
        res = optimize.least_squares(
            fun=self._error_function(intensity),
            x0=x0,
            loss="soft_l1",
            jac=self._error_function_df,
            tr_solver="exact"
        ).x
        return res % (2 * np.pi)

    def _hefs(self) -> None:
        """
        Impelements the HEFS algorithm which is a vetorisized phase retrieval algorithm based on
        https://opg.optica.org/josaa/fulltext.cfm?uri=josaa-34-1-87&id=356050
        """
        D = self.intensities - np.mean(self.intensities, axis=0)
        D = D.T
        _, _, V = np.linalg.svd(D)
        x, y = V[0], V[1]
        b = np.max(np.abs(V))
        N = len(x)
        chi = np.array([x ** 2, 2 * x * y, y ** 2, 2 * b * x, 2 * b * y, b ** 2 * np.ones(shape=x.shape)])
        X = np.mean(x)
        Y = np.mean(y)
        X2 = np.mean(chi[0])
        XY = np.mean(chi[1]) / 2
        Y2 = np.mean(chi[2])
        W = np.array([
            [6 * X2, 6 * XY, X2 + Y2, 6 * b * X, 2 * b * Y, b ** 2],
            [6 * XY, 4 * (X2 + Y2), 6 * XY, 4 * b * Y, 4 * b * X, 0],
            [X2 + Y2, 6 * XY, 6 * Y2, 2 * b * X, 6 * b * Y, b ** 2],
            [6 * b * X, 4 * b * Y, 2 * b * X, 4 * b ** 2, 0, 0],
            [2 * b * Y, 4 * b * X, 6 * b * Y, 0, 4 * b ** 2, 0],
            [b ** 2, 0, b ** 2, 0, 0, 0]
        ])
        X = 1 / N * chi @ chi.T
        w, v = linalg.eigh(W, X)
        a = v[:, np.argmax(np.abs(w))]
        X_head = V[0] - b * (a[2] * a[3] - a[1] * a[4]) / (a[1] ** 2 - a[0] * a[2])
        Y_head = V[1] - b * (a[0] * a[4] - a[1] * a[3]) / (a[1] ** 2 - a[0] * a[2])
        k = 4 * a[1] ** 2 + (a[0] - a[2]) ** 2
        t = (a[0] - a[2] + k) / (2 * a[1])
        real = np.sqrt(np.abs(a[0] + a[2] + k)) * (Y_head + t * X_head)
        compl = np.sqrt(np.abs(a[0] + a[2] - k)) * (X_head - t * Y_head)
        z = real + compl * 1.j
        self.phase = 2 * np.pi - np.angle(z) % (2 * np.pi)

    def calculate_phase(self, fast=False) -> None:
        """
        Calculated the interferometric phase with the defined characteristic parameters.
        """
        if self.intensities.size // self.dimension == 1:  # Only one Sample of 3 Values
            self.phase = self._calculate_phase(self.intensities)[0]
        else:
            if fast:
                self._hefs()
            else:
                phase = []
                for i in range(self.intensities.size // self.dimension):
                    phase.append(self._calculate_phase(self.intensities[i])[0])
                self.phase = np.array(phase)

    def calculate_sensitivity(self) -> None:
        try:
            self.sensitivity = np.empty(shape=(self.dimension, len(self.phase)))
        except TypeError:
            self.sensitivity = [0, 0, 0]
        for channel in range(self.dimension):
            amplitude = self.amplitudes[channel]
            output_phase = self.output_phases[channel]
            self.sensitivity[channel] = amplitude * np.abs(np.sin(self.phase - output_phase))

    def _prepare_data(self) -> tuple[dict[str, str], dict[str, Union[np.ndarray, float]]]:
        units: dict[str, str] = {"Interferometric Phase": "rad",
                                 "Sensitivity CH1": "V/rad",
                                 "Sensitivity CH2": "V/rad",
                                 "Sensitivity CH3": "V/rad"}
        output_data = {"Interferometric Phase": self.phase}
        for i in range(self.dimension):
            output_data[f"Sensitivity CH{i + 1}"] = self.sensitivity[i]
        return units, output_data

    def _calculate_online(self) -> None:
        output_data = {"Time": "H:M:S"}
        if self.init_online:
            output_data["Interferometric Phase"] = "rad"
            for channel in range(1, 4):
                output_data[f"Sensitivity CH{channel}"] = "V/rad"
            pd.DataFrame(output_data, index=["Y:M:D"]).to_csv(
                f"{self.destination_folder}/{minipti.path_prefix}_Interferometer.csv",
                index_label="Date"
            )
            self._init_live_data_frame()
            self.init_online = False
        self.calculate_phase()
        self.calculate_sensitivity()
        self._save_live_data()

    def _save_data(self) -> None:
        units, output_data = self._prepare_data()
        pd.DataFrame(units, index=["s"]).to_csv(
            f"{self.destination_folder}/Offline_Interferometer.csv",
            index_label="Time")
        pd.DataFrame(output_data).to_csv(
            f"{self.destination_folder}/Offline__Interferometer.csv",
            index_label="Time",
            mode="a",
            header=False
        )
        logging.info("Interferometer Data calculated.")
        logging.info("Saved results in %s", str(self.destination_folder))

    def _init_live_data_frame(self) -> None:
        output_data = {"Time": None, "Interferometric Phase": None}
        for channel in range(3):
            output_data[f"Sensitivity CH{channel + 1}"] = None
        self.output_data_frame = pd.DataFrame(output_data, index=[None])

    def _save_live_data(self) -> None:
        now = datetime.now()
        date = str(now.strftime("%Y-%m-%d"))
        current_time = str(now.strftime("%H:%M:%S"))
        self.output_data_frame["Time"] = current_time
        self.output_data_frame.index = [date]
        self.output_data_frame["Interferometric Phase"] = self.phase
        for channel in range(3):
            self.output_data_frame[f"Sensitivity CH{channel + 1}"] = self.sensitivity[channel]
        try:
            self.output_data_frame.to_csv(
                f"{self.destination_folder}/{minipti.path_prefix}_Interferometer.csv",
                mode="a",
                index_label="Date", header=False)
        except PermissionError:
            logging.warning("Could not write data. Missing values are: %s at %s.",
                            str(self.output_data_frame)[1:-1], date + " " + current_time)

    def _get_dc_signals(self, file_path: str) -> None:
        data = pd.read_csv(file_path, sep=None, engine="python", skiprows=[1])
        for header in Interferometer.DC_HEADERS:
            try:
                self.intensities = data[header].to_numpy()
                break
            except KeyError:
                continue
        else:
            raise KeyError("Invalid key for DC values given")

    def _calculate_offline(self, file_path: str) -> None:
        if file_path:
            self._get_dc_signals(file_path)
        self.calculate_phase()
        self.calculate_sensitivity()
        self._save_data()

    def run(self, live=False, file_path="") -> None:
        if live:
            self._calculate_online()
        else:
            self._calculate_offline(file_path)


@dataclass(frozen=True)
class CharacterizationSettings:
    use_default_settings: bool
    keep_settings: bool
    number_of_steps: int


class Characterization:
    """
    Provided an API for the characterization_live of an interferometer as described in [1].
    [1]:
    """
    CONFIGURATION: Final[CharacterizationSettings] = _utilities.load_configuration(
        CharacterizationSettings,
        "interferometry",
        "characterization"
    )
    STEP_SIZE: Final = CONFIGURATION.number_of_steps

    def __init__(self, interferometer=Interferometer(), use_configuration=CONFIGURATION.use_default_settings,
                 use_parameters=CONFIGURATION.keep_settings):
        self.interferometer = interferometer
        self.tracking_phase = []
        self._occurred_phases = np.full(Characterization.STEP_SIZE, 0)
        self.use_configuration = use_configuration
        self.use_parameters = use_parameters
        self.time_stamp = 0
        self.event = threading.Event()
        self.destination_folder = os.getcwd()
        self.init_headers = True
        self._progess = 0
        self.progress_observer = []
        self.path_prefix = ""

    def __repr__(self) -> str:
        class_name = self.__class__.__name__
        representation = f"{class_name}(use_settings={self.use_configuration}," \
                         f"destination_folder={self.destination_folder}," \
                         f" init_headers={self.init_headers}, tracking_phase={np.array(self.tracking_phase)}" \
                         f" time_stamp={self.time_stamp}, interferometer={self.interferometer})"
        return representation

    @property
    def progress(self) -> int:
        return self._progess

    @progress.setter
    def progress(self, progress: int) -> None:
        self._progess += progress
        for observer in self.progress_observer:
            observer(self._progess)

    @property
    def enough_values(self) -> bool:
        return np.all(self._occurred_phases)

    def calculate_symmetry(self) -> None:
        sensitivity = np.empty(shape=(3, len(self.interferometer.phase)))
        for i in range(3):
            amplitude = self.interferometer.amplitudes[i]
            output_phase = self.interferometer.output_phases[i]
            sensitivity[i] = amplitude * np.abs(np.sin(np.array(self.interferometer.phase) - output_phase))
        total_sensitivity = np.sum(sensitivity, axis=0)
        absolute_symmetry = np.min(total_sensitivity) / np.max(total_sensitivity) * 100
        relative_symmetry = absolute_symmetry / Interferometer.OPTIMAL_SYMMETRY * 100
        self.interferometer.absolute_symmetry = absolute_symmetry
        self.interferometer.relative_symmetry = relative_symmetry

    def characterise(self, live=False, file_path="") -> None:
        """
        Characterises the interferometer either live (with data from the motherboard) or offline.
        Args:
            live (bool): Decides if running live with motherboard connected or offline with already measured data.
            file_path (str): File path to the DC data
        """
        if self.init_headers:
            units = {}
            # The output data has no headers and relies on this order
            for channel in range(1, 4):
                units[f"Output Phase CH{channel}"] = "deg"
                units[f"Amplitude CH{channel}"] = "V"
                units[f"Offset CH{channel}"] = "V"
            units["Symmetry"] = "%"
            units["Relative Symmetry"] = "%"
            if live:
                dest_file_path = f"{minipti.path_prefix}_Characterisation.csv"
            else:
                dest_file_path = "Offline_Characterisation.csv"
            pd.DataFrame(units, index=["s"]).to_csv(
                dest_file_path,
                index_label="Time Stamp"
            )
            self.init_headers = False
        if live:
            self._calculate_online()
        else:
            try:
                self._calculate_offline(file_path)
                self.init_headers = True
            except CharacterizationError:
                logging.warning("Not enough values for characterisation")

    def add_phase(self, phase: float) -> None:
        """
        Adds a phase to list of occurred phase and mark its corresponding index in the occurred
        array. Note that the occured phase counter increases only if the phase is relevant.
        A phase is relevant if it lies in the first (n-1)/n of the circle.
        Args:
            phase (float): The occurred interferometric phase in rad.
        """
        self.time_stamp += 1
        if phase > 2 * np.pi:
            phase %= 2 * np.pi  # Phase is out of range
        k = int(Characterization.STEP_SIZE * phase / (2 * np.pi))
        self._occurred_phases[k] = 1

    def clear(self) -> None:
        """
        Resets the characterisation buffers.
        """
        self._occurred_phases = np.full(Characterization.STEP_SIZE, 0)
        self.event.clear()

    def _load_settings(self) -> None:
        settings = pd.read_csv(self.interferometer.settings_path, index_col="Setting")
        self.interferometer.output_phases = np.deg2rad(settings.loc["Output Phases [deg]"]).to_numpy()
        self.interferometer.amplitudes = settings.loc["Amplitude [V]"].to_numpy()
        self.interferometer.offsets = settings.loc["Offset [V]"].to_numpy()
        self.use_parameters = True

    def _estimate_settings(self, dc_signals: np.ndarray) -> None:
        self.interferometer.calculate_offsets(dc_signals)
        self.interferometer.calculate_amplitudes(dc_signals)
        self.interferometer.output_phases = np.array([0, 2 * np.pi / 3, 4 * np.pi / 3])
        self.use_parameters = False

    def process(self, dc_signals: np.ndarray) -> Generator[int, None, None]:
        last_index: int = 0
        data_length: int = dc_signals.size // self.interferometer.dimension
        unknown_parameters = False
        self._estimate_settings(dc_signals)
        self.interferometer.intensities = dc_signals
        self._characterise()
        for i in range(data_length):
            self.interferometer.intensities = dc_signals[i]
            self.interferometer.calculate_phase()
            self.add_phase(self.interferometer.phase)
            if self.enough_values:
                self.interferometer.intensities = dc_signals[last_index:i + 1]
                self._characterise()
                self.calculate_symmetry()
                last_index = i + 1
                self.clear()
                yield i
        self.clear()
        if last_index == 0 and not unknown_parameters:
            raise CharacterizationError("Not enough values for characterisation")

    def _characterise_interferometer(
            self,
            update_amplitude_offsets=True,
            guess=False
            ) -> None:
        """
        Calculates with the least squares method the output phases and min and max intensities for
        every channel. If no min/max values and output phases are given (either none or nan) the
        function try to estimate them best-possible.
        """
        output_phases = []
        amplitudes = []
        offsets = []
        results = []

        def add_values(result):
            output_phases.append((np.arctan2(result[2], result[1])) % (2 * np.pi))
            amplitudes.append(np.sqrt(result[1] ** 2 + result[2] ** 2))
            offsets.append(result[0])

        cosine_values = np.cos(self.interferometer.phase)
        sine_values = np.sin(self.interferometer.phase)
        parameters = np.array([np.ones(cosine_values.shape), cosine_values, sine_values]).T

        if guess:
            results, _, _, _ = linalg.lstsq(parameters, self.interferometer.intensities.T[0],
                                            check_finite=False)
            output_phase = np.arctan2(results[2], results[1]) % (2 * np.pi)
            # We shift the phase so that channel 1 has phase shift 0
            self.interferometer.phase = self.interferometer.phase - output_phase
            cosine_values = np.cos(self.interferometer.phase)
            sine_values = np.sin(self.interferometer.phase)
            parameters = np.array([np.ones(cosine_values.shape), cosine_values, sine_values]).T

        else:
            results, _, _, _ = linalg.lstsq(np.array([np.ones(cosine_values.shape), cosine_values]).T,
                                            self.interferometer.intensities.T[0], check_finite=False)
        amplitudes.append(results[0])
        offsets.append(results[1])
        output_phases.append(0)

        for i in range(1, self.interferometer.dimension):
            results, _, _, _ = linalg.lstsq(
                parameters,
                self.interferometer.intensities.T[i],
                check_finite=False)
            add_values(results)

        self.interferometer.output_phases = output_phases
        if update_amplitude_offsets:
            self.interferometer.amplitudes = amplitudes
            self.interferometer.offsets = offsets

    def _characterise(self) -> None:
        try:
            self.interferometer.calculate_phase(fast=True)
        except np.linalg.LinAlgError:
            # TODO: Figure out why this is happening
            self.interferometer.calculate_phase(fast=False)
        self._characterise_interferometer(update_amplitude_offsets=False, guess=True)
        logging.info("First guess:\n%s", str(self.interferometer))
        self.interferometer.calculate_phase(fast=False)
        self._characterise_interferometer()
        logging.info("Final values:\n%s", str(self.interferometer))

    def _add_characterised_data(self, output_data: defaultdict) -> None:
        for channel in range(3):
            output_phase_deg = np.rad2deg(self.interferometer.output_phases[channel])
            output_data[f"Output Phase CH{channel + 1}"].append(output_phase_deg)
            output_data[f"Amplitude CH{channel + 1}"].append(
                self.interferometer.amplitudes[channel]
            )
            output_data[f"Offset CH{channel + 1}"].append(
                self.interferometer.offsets[channel]
            )
        output_data["Symmetry"].append(self.interferometer.symmetry.absolute)
        output_data["Relative Symmetry"].append(self.interferometer.symmetry.relative)

    def _calculate_offline(self, file_path: str):
        output_data = defaultdict(list)
        time_stamps = []
        data = pd.read_csv(file_path, sep=None, engine="python", skiprows=[1])
        for header in Interferometer.DC_HEADERS:
            try:
                dc_signals = data[header].to_numpy()
                break
            except KeyError:
                continue
        else:
            raise KeyError("Invalid key for DC values given")
        process_characterisation = self.process(dc_signals)
        for i in process_characterisation:
            time_stamps.append(i)
            self._add_characterised_data(output_data)
        pd.DataFrame(output_data, index=time_stamps).to_csv(
            f"{self.destination_folder}/Offline_Characterisation.csv",
            mode="a",
            index_label="Time Stamp",
            header=False
        )
        logging.info("Characterization finished")
        logging.info("Saved data into %s", self.destination_folder)

    def _calculate_online(self) -> None:
        self.event.wait()
        self._characterise()
        characterised_data = {}
        for i in range(3):
            characterised_data[f"Output Phase CH{1 + i}"] = np.rad2deg(self.interferometer.output_phases[i])
            characterised_data[f"Amplitude CH{1 + i}"] = self.interferometer.amplitudes[i]
            characterised_data[f"Offset CH{1 + i}"] = self.interferometer.offsets[i]
        file_destination: str = f"{self.destination_folder}/{minipti.path_prefix}_Characterisation.csv"
        pd.DataFrame(characterised_data, index=[self.time_stamp]).to_csv(
            file_destination,
            mode="a",
            header=False,
            index_label="Time Stamp"
        )
        self.clear()
