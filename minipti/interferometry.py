import csv
import threading
import os
from collections import defaultdict
import logging
from enum import IntEnum

import numpy as np
import pandas as pd
from scipy import optimize, linalg


class _Interferometry:
    def __init__(self):
        self.settings_path = "configs/settings.csv"
        self.decimation_filepath = "data/Decimation.csv"
        self.phase = 0  # type: float | np.ndarray
        self._output_phases = np.empty(shape=3)
        self._amplitudes = np.empty(shape=3)
        self._offsets = np.empty(shape=3)
        self._locks = {"Output Phases": threading.Lock(), "Amplitudes": threading.Lock(), "Offsets": threading.Lock()}
        self.init_settings()

    def init_settings(self):
        settings = pd.read_csv(self.settings_path, index_col="Setting")
        self.output_phases = np.deg2rad(settings.loc["Output Phases [deg]"].to_numpy())
        self.amplitudes = settings.loc["Amplitude [V]"].to_numpy()
        self.offsets = settings.loc["Offset [V]"].to_numpy()

    def __eq__(self, other):
        return self.amplitudes == other.amplitudes and self.offsets == other.amplitudes and \
               self.output_phases == other.output_phases

    def __repr__(self):
        class_name = self.__class__.__name__
        representation = f"{class_name}(setting_path={self.settings_path}, decimation_path={self.decimation_filepath}\n"
        representation += f"phae={self.phase}, output_phases={self.output_phases}, amplitudes={self.amplitudes}\n"
        representation += f"offsets={self.offsets}) phases={self.phase}"
        return representation

    def __str__(self):
        output_phase_str = "Output Phases [deg]:"
        amplitude_str = "Amplitudes [V]:"
        offset_str = "Offsets [V]:"
        for i in range(3):
            output_phase_str.join(f"CH {i + 1}: {np.rad2deg(round(self.output_phases[i])), 2}\n")
            amplitude_str.join(f"CH {i + 1}: {round(self.amplitudes[i]), 2}\n")
            offset_str.join(f"CH {i + 1}: {round(self.offsets[i]), 2}\n")
        return amplitude_str + "\n" + offset_str + "\n" + output_phase_str

    @property
    def amplitudes(self):
        with self._locks["Amplitudes"]:
            amplitudes = self._amplitudes
        return amplitudes

    @amplitudes.setter
    def amplitudes(self, amplitudes):
        with self._locks["Amplitudes"]:
            self._amplitudes = amplitudes

    @property
    def offsets(self):
        with self._locks["Offsets"]:
            offsets = self._offsets
        return offsets

    @offsets.setter
    def offsets(self, offsets):
        with self._locks["Offsets"]:
            self._offsets = offsets

    @property
    def output_phases(self):
        with self._locks["Output Phases"]:
            output_phase = self._output_phases
        return output_phase

    @output_phases.setter
    def output_phases(self, output_phases):
        with self._locks["Output Phases"]:
            self._output_phases = output_phases

    def read_decimation(self):
        try:
            with open(self.decimation_filepath, "r") as csv_file:
                dc_delimiter = str(csv.Sniffer().sniff(csv_file.readline()).delimiter)
        except FileNotFoundError:
            return
        data = pd.read_csv(self.decimation_filepath, delimiter=dc_delimiter, skiprows=[1])
        return data

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

    def calculate_amplitude(self, intensity):
        _Interferometry.error_handing_intensity(intensity)
        if intensity.shape[1] == 3:
            self.amplitudes = (np.max(intensity, axis=0) - np.min(intensity, axis=0)) / 2
        else:
            self.amplitudes = (np.max(intensity, axis=1) - np.min(intensity, axis=1)) / 2

    def calculate_offset(self, intensity):
        _Interferometry.error_handing_intensity(intensity)
        if intensity.shape[1] == 3:
            self.offsets = (np.max(intensity, axis=0) + np.min(intensity, axis=0)) / 2
        else:
            self.offsets = (np.max(intensity, axis=1) + np.min(intensity, axis=1)) / 2

    def __error_function(self, intensity):
        intensity_scaled = (intensity - self.offsets) / self.amplitudes

        def error(phase):
            try:
                return np.cos(phase - self.output_phases) - intensity_scaled
            except TypeError:
                return np.cos(np.array(phase) - np.array(self.output_phases)) - intensity_scaled
        return error

    def __error_function_df(self, phase):
        try:
            return -np.sin(phase - self.output_phases).reshape((3, 1))
        except AttributeError:
            return -np.sin(np.array(phase) - np.array(self.output_phases)).reshape((3, 1))

    def _calculate_phase(self, intensity):
        res = optimize.least_squares(fun=self.__error_function(intensity), method="lm", x0=np.array(0),
                                     tr_solver="exact", jac=self.__error_function_df).x
        return res % (2 * np.pi)

    def calculate_phase(self, intensities):
        if len(intensities) == 3:  # Only one Sample of 3 Values
            self.phase = self._calculate_phase(intensities)[0]
        else:
            self.phase = np.fromiter(map(self._calculate_phase, intensities), dtype=np.float)


interferometer = _Interferometry()


class _Index(IntEnum):
    AMPLITUDES = 0
    OFFSETS = 1
    OUTPUT_PHASES = 2


class Characterization:
    """
    Provided an API for the characterization of an interferometer as described in [1].

    [1]: Waveguide based passively demodulated photo-thermal
         interferometer for aerosol measurements
    """

    def __init__(self, step_size=100):
        self._signals = None
        self.tracking_phase = []
        self._phases = []
        self.step_size = step_size  # type: int
        self._occurred_phases = np.full(step_size, False)
        self.use_settings = True
        self.event = threading.Event()
        self.time_stamp = 0
        self.characterised_data = defaultdict(list)
        self.characterised_data["Time Stamp"].append("%Y-%m-%d %H:%M:%S")
        for channel in range(1, 4):
            self.characterised_data[f"Output Phase CH{channel}"].append("deg")
            self.characterised_data[f"Amplitude CH{channel}"].append("V")
            self.characterised_data[f"Offset CH{channel}"].append("V")
        self.init_online = True
        self._parameters_changed = False  # Toggles if it changes
        self.observers = []

    @property
    def parameters_changed(self):
        return self._parameters_changed

    @parameters_changed.setter
    def parameters_changed(self, new_state):
        self._parameters_changed = new_state
        for observer_callback in self.observers:
            observer_callback()

    @property
    def signals(self):
        return self._signals

    @signals.setter
    def signals(self, signals):
        interferometer.error_handing_intensity(signals)
        try:
            if signals.shape[1] == 3:
                self._signals = signals.T
            else:
                self._signals = signals
        except AttributeError:
            signals = np.array(signals)
            if signals.shape[1] == 3:
                self._signals = signals.T
            else:
                self._signals = signals

    @property
    def occurred_phases(self):
        return self._occurred_phases

    @property
    def phases(self):
        return np.array(self._phases)

    @phases.setter
    def phases(self, phases):
        self._phases = phases

    def add_phase(self, phase: float):
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

    def enough_values(self):
        return np.all(self._occurred_phases)

    def clear(self):
        self.phases = []
        self.tracking_phase = []
        self._occurred_phases = np.full(self.step_size, False)
        self._signals = []
        self.event.clear()

    def __best_fit(self, measured, output_phase):
        if output_phase:
            return lambda x: np.sum((x[0] * np.cos(self.phases - x[2]) + x[1] - measured) ** 2)
        else:  # Without searching for output phases the problem is reduced by one dimension
            return lambda x: np.sum((x[0] * np.cos(self.phases) + x[1] - measured) ** 2)

    def __best_fit_df(self, measured, output_phase):
        def inner_function(x):
            if output_phase:
                return x[0] * np.cos(self.phases - x[2]) + x[1] - measured
            else:
                return x[0] * np.cos(self.phases) + x[1] - measured

        def gradient(x):
            if output_phase:
                return np.sum([2 * np.cos(self.phases - x[2]) * inner_function(x),
                               2 * inner_function(x),
                               -2 * x[0] * np.sin(self.phases - x[2]) * inner_function(x)], axis=1)
            else:
                return np.sum([2 * np.cos(self.phases) * inner_function(x),
                               2 * inner_function(x)], axis=1)
        return gradient

    def __estimate_first_guess(self):
        phase_space = [i * 2 * np.pi / (3 * 500) for i in range(1, 1000)]

        current_error = [np.inf, np.inf]
        start_phase = [0, 0]
        error_functions = [self.__best_fit(measured=self.signals[1], output_phase=True),
                           self.__best_fit(measured=self.signals[2], output_phase=True)]
        for phase in phase_space:
            error = error_functions[0]([interferometer.amplitudes[1], interferometer.offsets[1], phase])
            if error < current_error[0]:
                current_error[0] = error
                start_phase[0] = phase
            error = error_functions[0]([interferometer.amplitudes[2], interferometer.offsets[2], phase])
            if error < current_error[1]:
                current_error[1] = error
                start_phase[1] = phase
        interferometer.output_phases = [0, start_phase[0], start_phase[1]]
        logging.info(f"Current Initial Guess: {np.rad2deg(start_phase)[0]}°, {np.rad2deg(start_phase)[1]}°")

    def characterise_interferometer(self):
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

        interferometer.output_phases = output_phases
        interferometer.amplitudes = amplitudes
        interferometer.offsets = offsets

    def _iterate_characterization(self, dc_signals):
        if not self.use_settings:
            logging.info("Start iteration...")
            for i in range(30):
                interferometer.calculate_phase(dc_signals)
                self.signals = dc_signals
                self.phases = interferometer.phase
                self.characterise_interferometer()
                logging.info(f"i = {i}: Output Phases: {np.rad2deg(interferometer.output_phases)}")
                logging.info(f"Amplitudes: {interferometer.amplitudes}")
                logging.info(f"Offsets: {interferometer.offsets}")
            else:
                logging.info("Final value: ", np.rad2deg(interferometer.output_phases))
                logging.info(f"Amplitudes: {interferometer.amplitudes}")
                logging.info(f"Offsets: {interferometer.offsets}")
        else:
            self.characterise_interferometer()

    def _add_characterisation_data(self):
        for i in range(3):
            self.characterised_data[f"Output Phase CH{1 + i}"].append(np.rad2deg(interferometer.output_phases[i]))
            self.characterised_data[f"Amplitude CH{1 + i}"].append(interferometer.amplitudes[i])
            self.characterised_data[f"Offset CH{1 + i}"].append(interferometer.offsets[i])

    def _calculate_offline(self):
        data = interferometer.read_decimation()
        dc_signals = data[[f"DC CH{i}" for i in range(1, 4)]].to_numpy()
        self.clear()
        last_index = 0
        if self.use_settings:
            settings = pd.read_csv(interferometer.settings_path, index_col="Setting")
            interferometer.output_phases = np.deg2rad(settings.loc["Output Phases [deg]"])
            interferometer.amplitudes = settings.loc["Amplitude [V]"]
            interferometer.offsets = settings.loc["Offset [V]"]
        else:
            interferometer.calculate_offset(dc_signals)
            interferometer.calculate_amplitude(dc_signals)
            interferometer.output_phases = np.array([0, 2 * np.pi / 3, 4 * np.pi / 3])
        for i in range(len(data)):
            interferometer.calculate_phase(dc_signals[i])
            self.add_phase(interferometer.phase)
            if self.enough_values():
                self.signals = dc_signals[last_index: i + 1]
                self.phases = self.tracking_phase
                self._iterate_characterization(dc_signals=dc_signals[last_index: i + 1])
                self._add_characterisation_data()
                last_index = i + 1
                self.characterised_data["Time Stamp"].append(i)
                self.clear()
        pd.DataFrame(self.characterised_data).to_csv("data/Characterisation.csv", index=False)
        logging.info("Characterization finished")

    def _calculate_online(self):
        self.event.wait()
        self.use_settings = True
        if self.init_online:
            pd.DataFrame(self.characterised_data, index=["s"]).to_csv("data/Characterisation.csv",
                                                                      index_label="Time Stamp")
            self.init_online = False
        self.characterise_interferometer()
        self._iterate_characterization(dc_signals=self.signals)
        characterised_data = {}
        for i in range(3):
            characterised_data[f"Output Phase CH{1 + i}"] = np.rad2deg(interferometer.output_phases[i])
            characterised_data[f"Amplitude CH{1 + i}"] = interferometer.amplitudes[i]
            characterised_data[f"Offset CH{1 + i}"] = interferometer.offsets[i]
        output_data = pd.DataFrame(characterised_data, index=[self.time_stamp])
        pd.DataFrame(output_data).to_csv("data/Characterisation.csv", mode="a",
                                         header=not os.path.exists("data/Characterisation.csv"),
                                         index_label="Time Stamp")
        self.clear()
        self.parameters_changed ^= True

    def __repr__(self):
        class_name = self.__class__.__name__
        representation = f"{class_name}(signals={self.signals}, use_settings={self.use_settings}," \
                         f" step_size={self.step_size}, characterised_data={self.characterised_data})"
        return representation
	
    def __call__(self, mode):
        match mode:
            case "offline":
                self._calculate_offline()
            case "online":
                self._calculate_online()
            case _:
                raise TypeError(f"Mode {mode} is an invalid mode.")