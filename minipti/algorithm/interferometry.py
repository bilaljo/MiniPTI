"""
API for characterisation and phases of an interferometer.
"""
from collections.abc import Generator
import itertools
import logging
import os
import threading
import typing
from dataclasses import dataclass
from typing import Final, Union
from collections import defaultdict

import numpy as np
import pandas as pd
from scipy import optimize, linalg


class _Locks(typing.NamedTuple):
    output_phases: threading.Lock() = threading.Lock()
    amplitudes: threading.Lock() = threading.Lock()
    offsets: threading.Lock() = threading.Lock()
    characterisitc_parameter: threading.Lock() = threading.Lock()


@dataclass
class Symmetry:
    absolute: Union[float, np.ndarray] = 100
    relative: Union[float, np.ndarray] = 100


@dataclass
class CharateristicParameter:
    amplitudes: np.ndarray[float]
    offsets: np.ndarray[float]
    output_phases: np.ndarray[float]


class Interferometer:
    """
    Provides the API for calculating the interferometric phase based on its characteristic values.
    """
    CHANNELS: Final[int] = 3

    DC_HEADERS: Final[list] = [[f"PD{i}" for i in range(1, 4)],
                               [f"DC CH{i}" for i in range(1, 4)]]

    OPTIMAL_SYMMETRY: Final[float] = 86.58  # %

    def __init__(self, settings_path=f"{os.path.dirname(__file__)}/configs/settings.csv",
                 decimation_filepath="data/Decimation.csv"):
        self.settings_path = settings_path
        self.decimation_filepath = decimation_filepath
        self.phase: float | np.ndarray = 0
        self._characteristic_parameter = CharateristicParameter(amplitudes=np.zeros(3), offsets=np.zeros(3),
                                                                output_phases=np.array([0,
                                                                                        2 * np.pi / 3,
                                                                                        4 * np.pi / 3]))
        self.symmetry = Symmetry()
        self._locks = _Locks()
        self.sensitivity: np.ndarray = np.empty(shape=3)

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
        for i in range(2):
            output_phase_str += f"CH {i + 1}: {np.round(np.rad2deg(self.output_phases[i]), 2)}, "
            amplitude_str += f"CH {i + 1}: {np.round(self.amplitudes[i], 2)}, "
            offset_str += f"CH {i + 1}: {np.round(self.offsets[i], 2)}, "
        output_phase_str += f"CH3: {np.round(np.rad2deg(self.output_phases[2]), 2)}"
        amplitude_str += f"CH3: {np.round(self.amplitudes[2], 2)}"
        offset_str += f"CH3: {np.round(self.offsets[2], 2)}"
        return amplitude_str + "\n" + offset_str + "\n" + output_phase_str

    @property
    def characteristic_parameter(self) -> CharateristicParameter:
        with self._locks.characterisitc_parameter:
            return self._characteristic_parameter

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

    def calculate_amplitudes(self, intensity: np.ndarray):
        """
        The amplitude of perfect sine wave can be calculated according to A = (I_max - I_min) / 2.
        This function is only used as approximation.
        """
        if intensity.shape[0] == 3:
            self.amplitudes = (np.max(intensity, axis=1) - np.min(intensity, axis=1)) / 2
        else:
            self.amplitudes = (np.max(intensity, axis=0) - np.min(intensity, axis=0)) / 2

    def calculate_offsets(self, intensity: np.ndarray):
        """
        The offset of perfect sine wave can be calculated according to B = (I_max + I_min) / 2.
        This function is only used as approximation.
        """
        if intensity.shape[0] == 3:
            self.offsets = (np.max(intensity, axis=1) + np.min(intensity, axis=1)) / 2
        else:
            self.offsets = (np.max(intensity, axis=0) + np.min(intensity, axis=0)) / 2

    def _error_function(self, intensity: np.ndarray):
        intensity_scaled = (intensity - self.offsets) / self.amplitudes

        def error(phase: np.ndarray):
            try:
                return np.cos(phase - self.output_phases) - intensity_scaled
            except TypeError:
                return np.cos(np.array(phase) - np.array(self.output_phases)) - intensity_scaled

        return error

    def _error_function_df(self, phase: np.ndarray):
        try:
            return -np.sin(phase - self.output_phases).reshape((3, 1))
        except AttributeError:
            return -np.sin(np.array(phase) - np.array(self.output_phases)).reshape((3, 1))

    def _calculate_phase(self, intensity: np.ndarray):
        res = optimize.least_squares(fun=self._error_function(intensity), method="lm", x0=np.array(0),
                                     tr_solver="exact",  jac=self._error_function_df).x
        return res % (2 * np.pi)

    def calculate_phase(self, intensities: np.ndarray):
        """
        Calculated the interferometric phase with the defined characteristic parameters.
        """
        if intensities.size // Interferometer.CHANNELS == 1:  # Only one Sample of 3 Values
            self.phase = self._calculate_phase(intensities)[0]
        else:
            if intensities.shape[1] == 3:
                self.phase = np.fromiter(map(self._calculate_phase, intensities), dtype=float)
            else:
                self.phase = np.fromiter(map(self._calculate_phase, intensities.T), dtype=float)

    def calculate_sensitivity(self) -> None:
        try:
            self.sensitivity = np.empty(shape=(3, len(self.phase)))
        except TypeError:
            self.sensitivity = [0, 0, 0]
        for channel in range(3):
            amplitude = self.amplitudes[channel]
            output_phase = self.output_phases[channel]
            self.sensitivity[channel] = amplitude * np.abs(np.sin(self.phase - output_phase))


@dataclass
class InterferometryData:
    dc_signals: Union[np.ndarray, None] = None
    phases: Union[np.ndarray, None] = None


class Characterization:
    """
    Provided an API for the characterization_live of an interferometer as described in [1].
    [1]:
    """
    MAX_ITERATIONS: Final[int] = 30
    STEP_SIZE: Final[int] = 100

    def __init__(self, interferometer=Interferometer(), use_configuration=True, use_parameters=True):
        self.interferometer = interferometer
        self.tracking_phase = []
        self._occurred_phases = np.full(Characterization.STEP_SIZE, False)
        self.use_configuration = use_configuration
        self.use_parameters = use_parameters
        self.time_stamp = 0
        self.event = threading.Event()
        self.destination_folder = os.getcwd()
        self.init_headers = True
        self.interferometry_data = InterferometryData()

    def __repr__(self) -> str:
        class_name = self.__class__.__name__
        representation = f"{class_name}(use_settings={self.use_configuration}," \
                         f"destination_folder={self.destination_folder}, phases={np.array(self.phases)}," \
                         f" init_headers={self.init_headers}, tracking_phase={np.array(self.tracking_phase)}" \
                         f" time_stamp={self.time_stamp}, interferometer={self.interferometer})"
        return representation

    @property
    def enough_values(self) -> bool:
        return np.all(self._occurred_phases)

    @property
    def occurred_phases(self) -> np.ndarray:
        return self._occurred_phases

    def calculate_symmetry(self) -> None:
        sensitivity = np.empty(shape=(3, len(self.phases)))
        for i in range(3):
            amplitude = self.interferometer.amplitudes[i]
            output_phase = self.interferometer.output_phases[i]
            sensitivity[i] = amplitude * np.abs(np.sin(np.array(self.phases) - output_phase))
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
            # units["Symmetry"] = "%"
            # units["Relative Symmetry"] = "%"
            pd.DataFrame(units, index=["s"]).to_csv(f"{self.destination_folder}/Characterisation.csv",
                                                    index_label="Time Stamp")
            self.init_headers = False
        if live:
            self._calculate_online()
        else:
            self._calculate_offline(file_path)
            self.init_headers = True

    def add_phase(self, phase: float) -> None:
        """
        Adds a phase to list of occurred phase and mark its corresponding index in the occurred
        array.
        Args:
            phase (float): The occurred interferometric phase in rad.
        """
        self.time_stamp += 1
        if phase > 2 * np.pi:
            phase %= 2 * np.pi  # Phase is out of range
        self.tracking_phase.append(phase)
        k = int(Characterization.STEP_SIZE * phase / (2 * np.pi))
        self._occurred_phases[k] = True

    def clear(self) -> None:
        """
        Resets the characterisation buffers.
        """
        self.tracking_phase = []
        self.interferometry_data.dc_signals = []
        self._occurred_phases = np.full(Characterization.STEP_SIZE, False)
        self.event.clear()

    def _load_settings(self) -> None:
        settings = pd.read_csv(self.interferometer.settings_path, index_col="Setting")
        self.interferometer.output_phases = np.deg2rad(settings.loc["Output Phases [deg]"])
        self.interferometer.amplitudes = settings.loc["Amplitude [V]"]
        self.interferometer.offsets = settings.loc["Offset [V]"]
        self.use_parameters = True

    def _estimate_settings(self, dc_signals: np.ndarray) -> None:
        self.interferometer.calculate_offsets(dc_signals)
        self.interferometer.calculate_amplitudes(dc_signals)
        self.interferometer.output_phases = np.array([0, 2 * np.pi / 3, 4 * np.pi / 3])
        self.use_parameters = False

    def process_characterisation(self, dc_signals: np.ndarray) -> Generator[int, None, None]:
        last_index: int = 0
        data_length: int = dc_signals.size // Interferometer.CHANNELS
        if self.use_configuration:
            self._load_settings()
        else:
            self._estimate_settings(dc_signals)
        for i in range(data_length):
            self.interferometer.calculate_phase(dc_signals[i])
            self.add_phase(self.interferometer.phase)
            if self.enough_values:
                self.interferometry_data.dc_signals = dc_signals[last_index:i + 1]
                self.interferometry_data.phases = self.tracking_phase
                if not self.use_parameters:
                    self._iterate_characterization()
                    self.use_parameters = True  # For next time these values can be used now
                else:
                    self._characterise_interferometer()
                self.calculate_symmetry()
                last_index = i + 1
                self.clear()
                yield i
        if last_index == 0:
            raise ValueError("Not enough values for characterisation")

    def _characterise_interferometer(self) -> None:
        """
        Calculates with the least squares method the output phases and min and max intensities for
        every channel. If no min/max values and output phases are given (either none or nan) the
        function try to estimate them best-possible.
        """
        output_phases = []
        amplitudes = []
        offsets = []

        def add_values(result):
            output_phases.append((np.arctan2(result[1], result[0])) % (2 * np.pi))
            amplitudes.append(np.sqrt(result[0] ** 2 + result[1] ** 2))
            offsets.append(result[2])

        cosine_values = np.cos(self.interferometry_data.phases)
        sine_values = np.sin(self.interferometry_data.phases)
        results, _, _, _ = linalg.lstsq(np.array([cosine_values, np.ones(len(cosine_values))]).T,
                                        self.interferometry_data.dc_signals.T[0], check_finite=False)
        amplitudes.append(results[0])
        offsets.append(results[1])
        output_phases.append(0)

        parameters = np.array([cosine_values, sine_values, np.ones(len(sine_values))]).T

        for i in range(1, Interferometer.CHANNELS):
            results, _, _, _ = linalg.lstsq(parameters, self.interferometry_data.dc_signals.T[i], check_finite=False)
            add_values(results)

        self.interferometer.output_phases = output_phases
        self.interferometer.amplitudes = amplitudes
        self.interferometer.offsets = offsets

    def _iterate_characterization(self) -> None:
        logging.info("Start iteration ...")
        for _ in itertools.repeat(None, Characterization.MAX_ITERATIONS):
            self.interferometer.calculate_phase(np.array(self.interferometry_data.dc_signals))
            self.phases = self.interferometer.phase
            self._characterise_interferometer()
            logging.info("Current estimation:\n%s", str(self.interferometer))
        logging.info("Final values:\n%s", str(self.interferometer))

    def _add_characterised_data(self, output_data: defaultdict) -> None:
        for channel in range(3):
            output_phase_deg = np.rad2deg(self.interferometer.output_phases[channel])
            output_data[f"Output Phase CH{channel + 1}"].append(output_phase_deg)
            output_data[f"Amplitude CH{channel + 1}"].append(self.interferometer.amplitudes[channel])
            output_data[f"Offset CH{channel + 1}"].append(self.interferometer.offsets[channel])
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
        process_characterisation = self.process_characterisation(dc_signals)
        try:
            for i in process_characterisation:
                time_stamps.append(i)
            self._add_characterised_data(output_data)
        except ValueError:
            logging.warning("Not enough values for characterization")
        else:
            pd.DataFrame(output_data, index=time_stamps).to_csv(f"{self.destination_folder}/Characterisation.csv",
                                                                mode="a", index_label="Time Stamp", header=False)
            logging.info("Characterization finished")
            logging.info("Saved data into %s", self.destination_folder)

    def _calculate_online(self) -> None:
        self.event.wait()
        self._characterise_interferometer()
        characterised_data = {}
        for i in range(3):
            characterised_data[f"Output Phase CH{1 + i}"] = np.rad2deg(self.interferometer.output_phases[i])
            characterised_data[f"Amplitude CH{1 + i}"] = self.interferometer.amplitudes[i]
            characterised_data[f"Offset CH{1 + i}"] = self.interferometer.offsets[i]
        file_destination: str = f"{self.destination_folder}/Characterisation.csv"
        pd.DataFrame(characterised_data, index=[self.time_stamp]).to_csv(file_destination, mode="a", header=False,
                                                                         index_label="Time Stamp")
        self.clear()
