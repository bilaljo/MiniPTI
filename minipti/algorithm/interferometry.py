import csv
import logging
import os
import threading
import typing
from collections import defaultdict

import numpy as np
import pandas as pd
from scipy import optimize, linalg


class Interferometer:
    DC_HEADERS = [[f"PD{i}" for i in range(1, 4)],
                  [f"DC CH{i}" for i in range(1, 4)]]

    def __init__(
        self,
        settings_path=f"{os.path.dirname(__file__)}/configs/settings.csv",
        decimation_filepath="data/Decimation.csv",
        output_phases=np.empty(shape=3), amplitudes=np.empty(shape=3),
        offsets=np.empty(shape=3)
    ):
        self.settings_path = settings_path
        self.decimation_filepath = decimation_filepath
        self.phase = 0  # type: float | np.ndarray
        self._output_phases = output_phases
        self._amplitudes = amplitudes
        self._offsets = offsets
        self._locks = {"Output Phases": threading.Lock(), "Amplitudes": threading.Lock(), "Offsets": threading.Lock()}

    def load_settings(self) -> None:
        settings = pd.read_csv(self.settings_path, index_col="Setting")
        self.output_phases = np.deg2rad(settings.loc["Output Phases [deg]"].to_numpy())
        self.amplitudes = settings.loc["Amplitude [V]"].to_numpy()
        self.offsets = settings.loc["Offset [V]"].to_numpy()

    def __eq__(self, other) -> bool:
        return self.amplitudes == other.amplitudes and self.offsets == other.amplitudes and \
            self.output_phases == other.output_phases

    def __repr__(self) -> str:
        class_name = self.__class__.__name__
        representation = f"{class_name}(setting_path={self.settings_path}, decimation_path={self.decimation_filepath}\n"
        representation += f"phae={self.phase}, output_phases={self.output_phases}, amplitudes={self.amplitudes}\n"
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
        with self._locks["Amplitudes"]:
            amplitudes = self._amplitudes
        return amplitudes

    @amplitudes.setter
    def amplitudes(self, amplitudes: np.ndarray):
        with self._locks["Amplitudes"]:
            self._amplitudes = amplitudes

    @property
    def offsets(self) -> np.ndarray:
        with self._locks["Offsets"]:
            offsets = self._offsets
        return offsets

    @offsets.setter
    def offsets(self, offsets: np.ndarray):
        with self._locks["Offsets"]:
            self._offsets = offsets

    @property
    def output_phases(self) -> np.ndarray:
        with self._locks["Output Phases"]:
            output_phase = self._output_phases
        return output_phase

    @output_phases.setter
    def output_phases(self, output_phases: np.ndarray):
        with self._locks["Output Phases"]:
            self._output_phases = output_phases

    def read_decimation(self) -> pd.DataFrame | None:
        try:
            with open(self.decimation_filepath, "r") as csv_file:
                dc_delimiter = str(csv.Sniffer().sniff(csv_file.readline()).delimiter)
        except FileNotFoundError:
            logging.error(f"Could not find {self.decimation_filepath}")
            return
        return pd.read_csv(self.decimation_filepath, delimiter=dc_delimiter, skiprows=[1])

    @staticmethod
    def error_handing_intensity(intensity):
        if type(intensity) != np.ndarray:
            intensity = np.array(intensity)
        if len(intensity.shape) != 2:
            raise ValueError(f"Expected length of shape of 2, got {len(intensity.shape)} instead.")
        elif not (intensity.shape[0] == 3 or intensity.shape[1] == 3):
            raise ValueError(f"Expected length of (3, n) or (n, 3), got {intensity.shape} instead.")
        elif intensity.shape[0] == intensity.shape[1]:
            raise ValueError(f"Same shape for both dimensions. Could determine which dimension describes channels.")

    def calculate_amplitudes(self, intensity: np.ndarray):
        Interferometer.error_handing_intensity(intensity)
        if intensity.shape[1] == 3:
            self.amplitudes = (np.max(intensity, axis=0) - np.min(intensity, axis=0)) / 2
        else:
            self.amplitudes = (np.max(intensity, axis=1) - np.min(intensity, axis=1)) / 2

    def calculate_offsets(self, intensity: np.ndarray):
        Interferometer.error_handing_intensity(intensity)
        if intensity.shape[1] == 3:
            self.offsets = (np.max(intensity, axis=0) + np.min(intensity, axis=0)) / 2
        else:
            self.offsets = (np.max(intensity, axis=1) + np.min(intensity, axis=1)) / 2

    def _error_function(self, intensity: np.ndarray):
        intensity_scaled = (intensity - self.offsets) / self.amplitudes

        def error(phase: typing.Iterable):
            try:
                return np.cos(phase - self.output_phases) - intensity_scaled
            except TypeError:
                return np.cos(np.array(phase) - np.array(self.output_phases)) - intensity_scaled

        return error

    def _error_function_df(self, phase: typing.Iterable):
        try:
            return -np.sin(phase - self.output_phases).reshape((3, 1))
        except AttributeError:
            return -np.sin(np.array(phase) - np.array(self.output_phases)).reshape((3, 1))

    def _calculate_phase(self, intensity: np.ndarray):
        res = optimize.least_squares(fun=self._error_function(intensity), method="lm", x0=np.array(0),
                                     tr_solver="exact", jac=self._error_function_df).x
        return res % (2 * np.pi)

    def calculate_phase(self, intensities: np.ndarray):
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

    def __init__(self, step_size=100, interferometry=None, use_settings=True):
        self.interferometry = interferometry
        self.tracking_phase = []
        self._phases = []
        self.step_size = step_size
        self._occurred_phases = np.full(step_size, False)
        self.use_settings = use_settings
        self.time_stamp = 0
        self.characterised_data = defaultdict(list)
        self.event = threading.Event()
        self._parameters_changed = False  # Toggles if it changes
        self.observers = []
        self.signals = None  # type: None | np.ndarray
        self.destination_folder = os.getcwd()
        self.init_headers = True

    def __call__(self, live=True) -> None:
        if self.init_headers:
            units = {}
            # The order of headers is important because the output data has no headers it relies on this order
            for channel in range(1, 4):
                units[f"Output Phase CH{channel}"] = "deg"
                units[f"Amplitude CH{channel}"] = "V"
                units[f"Offset CH{channel}"] = "V"
            pd.DataFrame(units, index=["s"]).to_csv(f"{self.destination_folder}/Characterisation.csv",
                                                    index_label="Time Stamp")
            self.init_headers = False
        if live:
            self._calculate_online()
        else:
            self._calculate_offline()
            self.init_headers = True

    def __repr__(self) -> str:
        class_name = self.__class__.__name__
        representation = f"{class_name}(signals={self.signals}, use_settings={self.use_settings}," \
                         f" step_size={self.step_size}, characterised_data={self.characterised_data})"
        return representation

    @property
    def occurred_phases(self) -> np.ndarray:
        return self._occurred_phases

    @property
    def phases(self) -> np.ndarray:
        return np.array(self._phases)

    @phases.setter
    def phases(self, phases: np.ndarray | list):
        self._phases = list(phases)

    def add_phase(self, phase: float) -> None:
        """
        Adds a phase to list of occurred phase and mark its corresponding index in the occurred array.
        Args:
            phase (float): The occurred interferometric phase in rad.
        """
        self.time_stamp += 1
        if phase > 2 * np.pi:
            phase %= 2 * np.pi  # Phase is out of range
        self.tracking_phase.append(phase)
        k = int(self.step_size * phase / (2 * np.pi))
        self._occurred_phases[k] = True

    @property
    def enough_values(self) -> bool:
        return np.all(self._occurred_phases)

    def clear(self) -> None:
        self.phases = []
        self.tracking_phase = []
        self._occurred_phases = np.full(self.step_size, False)
        self.signals = []
        self.event.clear()

    def characterise_interferometer(self) -> None:
        """
        Calculates with the least squares method the output phases and min and max intensities for every channel.
        If no min/max values and output phases are given (either none or nan) the function try to estimate them
        best-possible.
        """

        output_phases = []
        amplitudes = []
        offsets = []

        def add_values(p):
            output_phases.append((np.arctan2(p[1], p[0])) % (2 * np.pi))
            amplitudes.append(np.sqrt(p[0] ** 2 + p[1] ** 2))
            offsets.append(p[2])

        cosine_values = np.cos(self.phases)
        sine_values = np.sin(self.phases)
        p, res, rnk, s = linalg.lstsq(np.array([cosine_values, np.ones(len(cosine_values))]).T, self.signals[0],
                                      check_finite=False)
        amplitudes.append(p[0])
        offsets.append(p[1])
        output_phases.append(0)

        parameters = np.array([cosine_values, sine_values, np.ones(len(sine_values))]).T

        p, res, rnk, s = linalg.lstsq(parameters, self.signals[1], check_finite=False)
        add_values(p)

        p, res, rnk, s = linalg.lstsq(parameters, self.signals[2], check_finite=False)
        add_values(p)

        self.interferometry.output_phases = output_phases
        self.interferometry.amplitudes = amplitudes
        self.interferometry.offsets = offsets

    def _iterate_characterization(self) -> None:
        logging.info("Start iteration...")
        for i in range(Characterization.MAX_ITERATIONS):
            self.interferometry.calculate_phase(self.signals.T)
            self.phases = self.interferometry.phase
            self.characterise_interferometer()
            logging.info(f"Current estimation:\n" + str(self.interferometry))
        else:
            logging.info("Final values:\n" + str(self.interferometry))

    def _add_characterised_data(self, output_data: defaultdict) -> None:
        for channel in range(3):
            output_phase_deg = np.rad2deg(self.interferometry.output_phases[channel])
            output_data[f"Output Phase CH{channel + 1}"].append(output_phase_deg)
            output_data[f"Amplitude CH{channel + 1}"].append(self.interferometry.amplitudes[channel])
            output_data[f"Offset CH{channel + 1}"].append(self.interferometry.offsets[channel])

    def _calculate_offline(self):
        output_data = defaultdict(list)
        data = self.interferometry.read_decimation()
        time_stamps = []
        for header in Interferometer.DC_HEADERS:
            try:
                dc_signals = data[header].to_numpy()
                break
            except KeyError:
                continue
        else:
            raise KeyError("Invalid key for DC values given")
        self.clear()
        last_index = 0
        if self.use_settings:
            settings = pd.read_csv(self.interferometry.settings_path, index_col="Setting")
            self.interferometry.output_phases = np.deg2rad(settings.loc["Output Phases [deg]"])
            self.interferometry.amplitudes = settings.loc["Amplitude [V]"]
            self.interferometry.offsets = settings.loc["Offset [V]"]
        else:
            self.interferometry.calculate_offsets(dc_signals)
            self.interferometry.calculate_amplitudes(dc_signals)
            self.interferometry.output_phases = np.array([0, 2 * np.pi / 3, 4 * np.pi / 3])
        for i in range(len(data)):
            self.interferometry.calculate_phase(dc_signals[i])
            self.add_phase(self.interferometry.phase)
            if self.enough_values:
                self.signals = dc_signals[last_index:i + 1].T
                self.phases = self.tracking_phase
                if not self.use_settings:
                    self._iterate_characterization()
                else:
                    self.characterise_interferometer()
                self._add_characterised_data(output_data)
                last_index = i + 1
                time_stamps.append(i)
                self.clear()
        if last_index == 0:
            logging.warning("Not enough values for characterization")
        else:
            pd.DataFrame(output_data, index=time_stamps).to_csv(f"{self.destination_folder}/Characterisation.csv",
                                                                mode="a", index_label="Time Stamp", header=False)
            logging.info("Characterization finished")

    def _calculate_online(self) -> None:
        self.event.wait()
        self.signals = np.array(self.signals).T
        self.characterise_interferometer()
        characterised_data = {}
        for i in range(3):
            characterised_data[f"Output Phase CH{1 + i}"] = np.rad2deg(self.interferometry.output_phases[i])
            characterised_data[f"Amplitude CH{1 + i}"] = self.interferometry.amplitudes[i]
            characterised_data[f"Offset CH{1 + i}"] = self.interferometry.offsets[i]
        pd.DataFrame(
            characterised_data,
            index=[self.time_stamp]).to_csv(
            f"{self.destination_folder}/Characterisation.csv",
            mode="a", header=False, index_label="Time Stamp"
        )
        self.clear()
        self._parameters_changed ^= True
