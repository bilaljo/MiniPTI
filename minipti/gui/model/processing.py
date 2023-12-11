import csv
import logging
import os
import threading
import typing
from collections import deque
from typing import Union

import numpy as np
import pandas as pd
from PyQt5 import QtCore
from overrides import override
from scipy import ndimage

import minipti
from minipti import algorithm
from minipti.gui.model import buffer, serial_devices
from minipti.gui.model import configuration
from minipti.gui.model import general_purpose
from minipti.gui.model import signals


class DestinationFolder:
    def __init__(self):
        self._destination_folder = configuration.GUI.destination_folder.default_path

    @property
    def folder(self) -> str:
        return self._destination_folder

    @folder.setter
    def folder(self, folder: str) -> None:
        self._destination_folder = folder
        signals.GENERAL_PURPORSE.destination_folder_changed.emit(self._destination_folder)


class Calculation:
    def __init__(self):
        self.settings_path = ""
        decimation = algorithm.pti.Decimation()
        self.interferometer = algorithm.interferometry.Interferometer()
        self.pti = PTI(decimation, algorithm.pti.Inversion(decimation=decimation))
        self.pti.inversion.interferometer = self.interferometer
        self.interferometer_characterization = algorithm.interferometry.Characterization(self.interferometer)
        self._destination_folder = os.getcwd()
        signals.GENERAL_PURPORSE.destination_folder_changed.connect(self._update_destination_folder)
        signals.DAQ.samples_changed.connect(self._update_decimation_average_period)
        signals.CALCULATION.settings_path_changed.connect(self.update_settings_path)

    def update_settings_path(self, settings_path: str) -> None:
        self.interferometer.settings_path = settings_path

    def _update_destination_folder(self, folder: str) -> None:
        self.interferometer_characterization.destination_folder = folder
        self.pti.inversion.destination_folder = folder
        self.pti.decimation.destination_folder = folder
        self._destination_folder = folder

    def _update_decimation_average_period(self, samples: int) -> None:
        self.pti.decimation.average_period = samples


class LiveCalculation(Calculation):
    MEAN_INTERVAL = 60  # s

    def __init__(self):
        Calculation.__init__(self)
        self.current_time = 0
        self.dc_signals = []
        self.interferometer_buffer = buffer.Interferometer()
        self.pti_buffer = buffer.PTI()
        self.characterisation_buffer = buffer.Characterisation()
        self.pti_signal_mean_queue = deque(maxlen=LiveCalculation.MEAN_INTERVAL)
        self.new_directory = True
        signals.DAQ.clear.connect(self._clear_buffers)

    def update_new_directory(self) -> None:
        self.new_directory = True

    def _clear_buffers(self) -> None:
        self.interferometer_buffer.clear()
        self.pti_buffer.clear()
        self.characterisation_buffer.clear()

    def process_daq_data(self) -> None:
        threading.Thread(target=self._run_calculation, name="PTI Inversion", daemon=True).start()
        threading.Thread(target=self._run_characterization, name="Characterisation", daemon=True).start()

    @staticmethod
    def running_average(data, mean_size: int) -> list[float]:
        i = 1
        current_mean = data[0]
        result = [current_mean]
        while i < LiveCalculation.MEAN_INTERVAL and i < len(data):
            current_mean += data[i]
            result.append(current_mean / i)
            i += 1
        result.extend(ndimage.uniform_filter1d(data[mean_size:], size=mean_size))
        return result

    def set_raw_data_saving(self, save_raw_data: bool) -> None:
        self.pti.decimation.save_raw_data = save_raw_data

    def set_common_mode_noise_reduction(self, common_mode_noise_reduction: bool) -> None:
        self.pti.decimation.use_common_mode_noise_reduction = common_mode_noise_reduction

    def _run_calculation(self):
        self._init_calculation()
        while serial_devices.TOOLS.daq.running:
            self._decimation()
            self._interferometer_calculation()
            self._characterisation()
            self._pti_inversion()

    def _run_characterization(self) -> None:
        while serial_devices.TOOLS.daq.running:
            self.interferometer_characterization.characterise(live=True)
            self.characterisation_buffer.append(self.interferometer_characterization)
            signals.DAQ.characterization.emit(self.characterisation_buffer)
            signals.CALCULATION.settings_interferometer.emit(self.interferometer.characteristic_parameter)

    def _init_calculation(self) -> None:
        self.pti.inversion.init_header = True
        self.pti.decimation.init_header = True
        self.interferometer.init_online = True
        self.interferometer_characterization.init_online = True
        self.interferometer.load_settings()

    def _decimation(self) -> None:
        self.pti.decimation.raw_data.ref = serial_devices.TOOLS.daq.ref_signal.copy()
        self.pti.decimation.raw_data.dc = serial_devices.TOOLS.daq.dc_coupled.copy()
        self.pti.decimation.raw_data.ac = serial_devices.TOOLS.daq.ac_coupled.copy()
        self.pti.decimation.run(live=True)

    def _interferometer_calculation(self) -> None:
        self.interferometer.intensities = self.pti.decimation.dc_signals
        self.interferometer.run(live=True)
        self.interferometer_buffer.append(self.interferometer)
        signals.DAQ.interferometry.emit(self.interferometer_buffer)

    def _pti_inversion(self) -> None:
        self.pti.inversion.run(live=True)
        self.pti_buffer.append(self.pti, self.pti.decimation.average_period)
        signals.DAQ.inversion.emit(self.pti_buffer)

    def _characterisation(self) -> None:
        self.interferometer_characterization.add_phase(self.interferometer.phase)
        self.dc_signals.append(self.pti.decimation.dc_signals.copy())
        if self.interferometer_characterization.enough_values:
            self.interferometer_characterization.interferometry_data.dc_signals = np.array(self.dc_signals)
            phase: list[float] = self.interferometer_characterization.tracking_phase
            self.interferometer_characterization.interferometry_data.phases = np.array(phase)
            self.dc_signals = []
            self.interferometer_characterization.event.set()


class OfflineCalculation(Calculation):
    def __init__(self):
        Calculation.__init__(self)

    def calculate_characterisation(self, dc_file_path: str, use_settings=False) -> None:
        self.interferometer_characterization.use_configuration = use_settings
        self.interferometer_characterization.characterise(file_path=dc_file_path)
        signals.CALCULATION.settings_interferometer.emit(self.interferometer.characteristic_parameter)

    def calculate_decimation(self, decimation_path: str) -> None:
        self.pti.decimation.file_path = decimation_path
        logging.info("Starting Decimation of Raw Data")
        threading.Thread(target=self.pti.decimation.run, name="Decimation Thread").start()

    def calculate_interferometry(self, interferometry_path: str) -> None:
        self.interferometer.load_settings()
        self.interferometer.run(file_path=interferometry_path)

    def calculate_inversion(self, inversion_path: str) -> None:
        self.interferometer.load_settings()
        self.pti.inversion.run(file_path=inversion_path)


def find_delimiter(file_path: str) -> typing.Union[str, None]:
    delimiter_sniffer = csv.Sniffer()
    if not file_path:
        return
    with open(file_path, "r") as file:
        delimiter = str(delimiter_sniffer.sniff(file.readline()).delimiter)
    return delimiter


def _process_data(file_path: str, headers: list[str, ...]) -> Union[pd.DataFrame, typing.NoReturn]:
    if not file_path:
        raise FileNotFoundError("No file path given")
    delimiter = find_delimiter(file_path)
    try:
        data = pd.read_csv(file_path, delimiter=delimiter, skiprows=[1], index_col="Time")
    except ValueError:
        try:
            data = pd.read_csv(file_path, delimiter=delimiter, skiprows=[1], index_col="Time Stamp")
        except ValueError:  # Data isn't saved with any index
            data = pd.read_csv(file_path, delimiter=delimiter, skiprows=[1])
    return data[headers].to_numpy()


def process_dc_data(dc_file_path: str) -> None:
    headers = [f"DC CH{i}" for i in range(1, 4)]
    try:
        data = _process_data(dc_file_path, headers).T
    except KeyError:
        headers = [f"PD{i}" for i in range(1, 4)]
        data = _process_data(dc_file_path, headers).T
    except FileNotFoundError:
        return
    signals.CALCULATION.dc_signals.emit(data)


def process_inversion_data(inversion_file_path: str) -> None:
    send_data = {}
    try:
        headers = ["PTI Signal"]
        data = _process_data(inversion_file_path, headers)
        send_data["PTI Signal"] = data
        send_data["PTI Signal 60 s Mean"] = pd.DataFrame(data).rolling(60, center=True).mean()
    except FileNotFoundError:
        return
    signals.CALCULATION.inversion.emit(send_data)


def process_interferometric_phase_data(interferometric_phase_file_path: str) -> None:
    try:
        headers = ["Interferometric Phase"]
        data = _process_data(interferometric_phase_file_path, headers)
    except FileNotFoundError:
        return
    signals.CALCULATION.interferometric_phase.emit(data)


def process_characterization_data(characterization_file_path: str) -> None:
    headers = [f"Amplitude CH{i}" for i in range(1, 4)]
    headers += [f"Output Phase CH{i}" for i in range(1, 4)]
    headers += [f"Offset CH{i}" for i in range(1, 4)]
    headers += ["Symmetry", "Relative Symmetry"]
    try:
        data = _process_data(characterization_file_path, headers)
    except FileNotFoundError:
        return
    signals.CALCULATION.characterization.emit(data)


class SettingsTable(general_purpose.Table):
    def __init__(self):
        general_purpose.Table.__init__(self)
        self._data = pd.DataFrame(columns=self._headers, index=self._indices)
        self.file_path = f"{minipti.module_path}/algorithm/configs/settings.csv"
        signals.CALCULATION.settings_interferometer.connect(self.update_settings)
        self.load()

    @property
    @override
    def _headers(self) -> list[str]:
        return ["Detector 1", "Detector 2", "Detector 3"]

    @property
    @override
    def _indices(self) -> list[str]:
        return ["Amplitude [V]", "Offset [V]", "Output Phases [deg]", "Response Phases [rad]"]

    @QtCore.pyqtSlot(algorithm.interferometry.CharacteristicParameter)
    def update_settings(self, characteristic_parameter: algorithm.interferometry.CharacteristicParameter) -> None:
        self.update_settings_parameters(characteristic_parameter)

    def save(self) -> None:
        self._data.to_csv(self.file_path, index_label="Setting", index=True)

    def load(self) -> None:
        self.table_data = pd.read_csv(self.file_path, index_col="Setting")

    def update_settings_parameters(self, characteristic_parameter: algorithm.interferometry.CharacteristicParameter):
        self.table_data.loc["Output Phases [deg]"] = np.rad2deg(characteristic_parameter.output_phases)
        self.table_data.loc["Amplitude [V]"] = characteristic_parameter.amplitudes
        self.table_data.loc["Offset [V]"] = characteristic_parameter.offsets
        signals.CALCULATION.settings_pti.emit()

    def update_settings_paths(self, interferometer: algorithm.interferometry.Interferometer,
                              inversion: algorithm.pti.Inversion) -> None:
        signals.CALCULATION.settings_path_changed.emit(self.file_path)
        interferometer.settings_path = self.file_path
        inversion.settings_path = self.file_path
        interferometer.load_settings()
        inversion.load_response_phase()

    def setup_settings_file(self) -> None:
        # If no algorithm_settings found, a new empty file is created filled with NaN.
        algorithm_dir: str = f"{os.path.dirname(os.path.dirname(__file__))}/algorithm"
        if not os.path.exists(f"{algorithm_dir}/configs/settings.csv"):
            self.save()
        else:
            try:
                settings = pd.read_csv(f"{algorithm_dir}/configs/settings.csv", index_col="Setting")
            except FileNotFoundError:
                self.save()
            else:
                if list(settings.columns) != self._headers or list(settings.index) != self._indices:
                    self.save()  # The file is in any way broken.
                else:
                    self.table_data = settings


class PTI(typing.NamedTuple):
    decimation: algorithm.pti.Decimation
    inversion: algorithm.pti.Inversion
