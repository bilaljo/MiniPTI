"""
API for characterisation and phases of an interferometer.
"""

import csv
import itertools
import logging
import os
import threading
import typing
from typing import Union, Generator, Iterable
from collections import defaultdict

import numpy as np
import pandas as pd
from scipy import optimize, linalg


class _Locks(typing.NamedTuple):
    output_phases = threading.Lock()
    amplitudes = threading.Lock()
    offsets = threading.Lock()


class Interferometer:
    """
    Provides the API for calculating the interferometric phase based on its characteristic values.
    """
    DC_HEADERS = [[f"PD{i}" for i in range(1, 4)],
                  [f"DC CH{i}" for i in range(1, 4)]]

    OPTIMAL_SYMMETRY = 86.58

    def __init__(self, settings_path=f"{os.path.dirname(__file__)}/configs/settings.csv",
                 decimation_filepath="data/Decimation.csv", output_phases=np.empty(shape=3),
                 amplitudes=np.empty(shape=3), offsets=np.empty(shape=3)):
        self.settings_path = settings_path
        self.decimation_filepath = decimation_filepath
        self.phase: Union[float, np.ndarray] = 0
        self._output_phases = output_phases
        self._amplitudes = amplitudes
        self._offsets = offsets
        self.absolute_symmetry: Union[float, np.ndarray] = 100
        self.relative_symmetry: Union[float, np.ndarray] = 100
        self._locks = _Locks()

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
            output_phase_str += f"CH {i + 1}: {round(np.rad2deg(self.output_phases[i]), 2)},"
            amplitude_str += f"CH {i + 1}: {round(self.amplitudes[i], 2)},"
            offset_str += f"CH {i + 1}: {round(self.offsets[i], 2)},"
        output_phase_str += f"CH3: {round(np.rad2deg(self.output_phases[2]), 2)}, "
        amplitude_str += f"CH3: {round(self.amplitudes[2], 2)},"
        offset_str += f"CH3: {round(self.offsets[2], 2)},"
        return amplitude_str + "\n" + offset_str + "\n" + output_phase_str

    @property
    def amplitudes(self) -> np.ndarray:
        with self._locks.amplitudes:
            amplitudes = self._amplitudes
        return amplitudes

    @amplitudes.setter
    def amplitudes(self, amplitudes: np.ndarray):
        with self._locks.amplitudes:
            self._amplitudes = amplitudes

    @property
    def offsets(self) -> np.ndarray:
        with self._locks.offsets:
            offsets = self._offsets
        return offsets

    @offsets.setter
    def offsets(self, offsets: np.ndarray):
        with self._locks.offsets:
            self._offsets = offsets

    @property
    def output_phases(self) -> np.ndarray:
        with self._locks.output_phases:
            output_phase = self._output_phases
        return output_phase

    @output_phases.setter
    def output_phases(self, output_phases: np.ndarray):
        with self._locks.output_phases:
            self._output_phases = output_phases

    def read_decimation(self) -> Union[pd.DataFrame, None]:
        try:
            with open(self.decimation_filepath, "r", encoding="UTF-8") as csv_file:
                dc_delimiter = str(csv.Sniffer().sniff(csv_file.readline()).delimiter)
        except FileNotFoundError:
            logging.error("Could not find %s", self.decimation_filepath)
            return None
        return pd.read_csv(self.decimation_filepath, delimiter=dc_delimiter, skiprows=[1])

    def calculate_amplitudes(self, intensity: np.ndarray):
        """
        The amplitude of perfect sine wave can be calculated according to A = (I_max - I_min) / 2.
        This function is only used as approximation.
        """
        if intensity.shape[1] == 3:
            self.amplitudes = (np.max(intensity, axis=0) - np.min(intensity, axis=0)) / 2
        else:
            self.amplitudes = (np.max(intensity, axis=1) - np.min(intensity, axis=1)) / 2

    def calculate_offsets(self, intensity: np.ndarray):
        """
        The offset of perfect sine wave can be calculated according to B = (I_max + I_min) / 2.
        This function is only used as approximation.
        """
        if intensity.shape[1] == 3:
            self.offsets = (np.max(intensity, axis=0) + np.min(intensity, axis=0)) / 2
        else:
            self.offsets = (np.max(intensity, axis=1) + np.min(intensity, axis=1)) / 2

    def _error_function(self, intensity: np.ndarray):
        intensity_scaled = (intensity - self.offsets) / self.amplitudes

        def error(phase: Iterable):
            try:
                return np.cos(phase - self.output_phases) - intensity_scaled
            except TypeError:
                return np.cos(np.array(phase) - np.array(self.output_phases)) - intensity_scaled

        return error

    def _error_function_df(self, phase: Iterable):
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
        if len(intensities) == 3:  # Only one Sample of 3 Values
            self.phase = self._calculate_phase(intensities)[0]
        else:
            self.phase = np.fromiter(map(self._calculate_phase, intensities), dtype=float)


class Characterization:
    """
    Provided an API for the characterization_live of an interferometer as described in [1].
    [1]:
    """
    MAX_ITERATIONS = 30
    STEP_SIZE = 100
    _CHANNELS = 3

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
        self._signals = np.empty(1)
        self.phases = []

    def __repr__(self) -> str:
        class_name = self.__class__.__name__
        representation = f"{class_name}(signals={self._signals}, use_settings={self.use_configuration}," \
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

    def characterise(self, live=False) -> None:
        """
        Characterises the interferometer either live (with data from the motherboard) or offline.
        Args:
            live (bool): Decides if running live with motherboard connected or offline with already measured data.
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
            pd.DataFrame(units, index=["s"]).to_csv(f"{self.destination_folder}/Characterisation.csv",
                                                    index_label="Time Stamp")
            self.init_headers = False
        if live:
            self._calculate_online()
        else:
            self._calculate_offline()
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
        self._signals = []
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

    def process_characterisation(self, dc_signals: np.ndarray, function: typing.Callable):
        process_characterisation: Generator[int, None, int] = self._process_characterisation(dc_signals)
        while True:
            try:
                i = next(process_characterisation)
                if self.enough_values:
                    function(i)
            except StopIteration as e:
                if e.value == 0:
                    raise ValueError("Not enough values for characterisation")

    def _process_characterisation(self, dc_signals: np.ndarray) -> Generator[int, None, int]:
        last_index: int = 0
        data_length: int = dc_signals.size // Characterization._CHANNELS
        if self.use_configuration:
            self._load_settings()
        else:
            self._estimate_settings(dc_signals)
        for i in range(data_length):
            self.interferometer.calculate_phase(dc_signals[i])
            self.add_phase(self.interferometer.phase)
            if self.enough_values:
                self._signals = dc_signals[last_index:i + 1].T
                self.phases = self.tracking_phase
                if not self.use_parameters:
                    self._iterate_characterization()
                    self.use_parameters = True  # For next time these values can be used now
                else:
                    self._characterise_interferometer()
                self.calculate_symmetry()
                last_index = i + 1
            yield i
            if self.enough_values:
                self.clear()
        self.clear()
        return last_index

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

        cosine_values = np.cos(self.phases)
        sine_values = np.sin(self.phases)
        results, _, _, _ = linalg.lstsq(np.array([cosine_values, np.ones(len(cosine_values))]).T,
                                        self._signals[0], check_finite=False)
        amplitudes.append(results[0])
        offsets.append(results[1])
        output_phases.append(0)

        parameters = np.array([cosine_values, sine_values, np.ones(len(sine_values))]).T

        results, _, _, _ = linalg.lstsq(parameters, self._signals[1], check_finite=False)
        add_values(results)

        results, _, _, _ = linalg.lstsq(parameters, self._signals[2], check_finite=False)
        add_values(results)

        self.interferometer.output_phases = output_phases
        self.interferometer.amplitudes = amplitudes
        self.interferometer.offsets = offsets

    def _iterate_characterization(self) -> None:
        logging.info("Start iteration...")
        for _ in itertools.repeat(None, Characterization.MAX_ITERATIONS):
            self.interferometer.calculate_phase(self._signals.T)
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
        output_data["Symmetry"].append(self.interferometer.absolute_symmetry)
        output_data["Relative Symmetry"].append(self.interferometer.relative_symmetry)

    def _calculate_offline(self, dc_signals=None):
        output_data = defaultdict(list)
        time_stamps = []
        if dc_signals is None:
            data = self.interferometer.read_decimation()
            for header in Interferometer.DC_HEADERS:
                try:
                    dc_signals = data[header].to_numpy()
                    break
                except KeyError:
                    continue
            else:
                raise KeyError("Invalid key for DC values given")
        self.clear()
        if last_index == 0:
            logging.warning("Not enough values for characterization")
        else:
            pd.DataFrame(output_data, index=time_stamps).to_csv(f"{self.destination_folder}/Characterisation.csv",
                                                                mode="a", index_label="Time Stamp", header=False)
            logging.info("Characterization finished")
            logging.info("Saved data into %s", self.destination_folder)

        while True:
            try:
                i = next(process_characterisation)
                if self.enough_values:
                    time_stamps.append(i)
                    self._add_characterised_data(output_data)
            except StopIteration as ex:
                last_index = ex.value
                break
        if last_index == 0:
            logging.warning("Not enough values for characterization")
        else:
            pd.DataFrame(output_data, index=time_stamps).to_csv(f"{self.destination_folder}/Characterisation.csv",
                                                                mode="a", index_label="Time Stamp", header=False)
            logging.info("Characterization finished")
            logging.info("Saved data into %s", self.destination_folder)

    def _calculate_online(self) -> None:
        self.event.wait()
        self._signals = np.array(self._signals).T
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
