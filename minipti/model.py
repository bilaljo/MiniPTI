import copy
import csv
import itertools
import logging
import os
import threading
from collections import deque, namedtuple
from dataclasses import dataclass

import numpy as np
import pandas as pd
from PySide6 import QtCore
from scipy import ndimage

import driver
import interferometry
import pti


class SettingsTable(QtCore.QAbstractTableModel):
    HEADERS = ["Detector 1", "Detector 2", "Detector 3"]
    INDEX = ["Amplitude [V]", "Offset [V]", "Output Phases [deg]", "Response Phases [deg]"]
    SIGNIFICANT_VALUES = 4

    def __init__(self):
        QtCore.QAbstractTableModel.__init__(self)
        self._data = pd.DataFrame(columns=SettingsTable.HEADERS, index=SettingsTable.INDEX)
        self._file_path = "configs/settings.csv"
        self._observer_callbacks = []

    def rowCount(self, parent=None):
        return self._data.shape[0]

    def columnCount(self, parent=None):
        return self._data.shape[1]

    def data(self, index, role: int = ...):
        if index.isValid():
            if role == QtCore.Qt.DisplayRole or role == QtCore.Qt.EditRole:
                value = self._data.values[index.row()][index.column()]
                return str(round(value, SettingsTable.SIGNIFICANT_VALUES))

    def flags(self, index):
        return QtCore.Qt.ItemIsSelectable | QtCore.Qt.ItemIsEnabled | QtCore.Qt.ItemIsEditable

    def setData(self, index, value, role: int = ...):
        if index.isValid():
            if role == QtCore.Qt.EditRole:
                self._data.at[SettingsTable.INDEX[index.row()], SettingsTable.HEADERS[index.column()]] = value
                return True

    def headerData(self, section, orientation, role=QtCore.Qt.DisplayRole):
        if orientation == QtCore.Qt.Horizontal and role == QtCore.Qt.DisplayRole:
            return SettingsTable.HEADERS[section]
        elif orientation == QtCore.Qt.Vertical and role == QtCore.Qt.DisplayRole:
            return SettingsTable.INDEX[section]
        return super().headerData(section, orientation, role)

    @property
    def table_data(self):
        return self._data

    @table_data.setter
    def table_data(self, data):
        self._data = data
        for observer in self._observer_callbacks:
            observer(self.table_data.values.tolist())

    def update_data(self, data):
        self._data = pd.DataFrame(data, columns=SettingsTable.HEADERS, index=SettingsTable.INDEX)

    @property
    def file_path(self):
        return self._file_path

    @file_path.setter
    def file_path(self, file_path):
        if os.path.exists(file_path):
            self._file_path = file_path

    @property
    def observer_callbacks(self):
        return self._observer_callbacks

    def add_observer(self, callback):
        self._observer_callbacks.append(callback)

    def save(self):
        self._data.to_csv(self.file_path, index_label="Setting", index=True)

    def load(self):
        self.table_data = pd.read_csv(self.file_path, index_col="Setting")

    def update_settings_parameters(self, interferometer):
        self.table_data.loc["Output Phases [deg]"] = np.rad2deg(interferometer.output_phases)
        self.table_data.loc["Amplitude [V]"] = interferometer.amplitudes
        self.table_data.loc["Offset [V]"] = interferometer.offsets

    def update_settings(self, interferometer, inversion):
        interferometer.settings_path = self.file_path
        inversion.settings_path = self.file_path
        interferometer.init_settings()
        inversion.load_response_phase()

    def setup_settings_file(self):
        if not os.path.exists("configs/settings.csv"):  # If no settings found, a new empty file is created.
            self.save()
        else:
            try:
                settings = pd.read_csv("configs/settings.csv", index_col="Setting")
            except FileNotFoundError:
                self.save()
            else:
                if list(settings.columns) != SettingsTable.HEADERS or list(settings.index) != SettingsTable.INDEX:
                    self.save()  # The file is in any way broken.

    def load_settings(self):
        try:
            self.load()
        except (ValueError, PermissionError) as e:
            logging.error(f"Could not load settings. Got \"{e}\".")
            return

    def save_settings(self):
        self.save()


class _Signals(QtCore.QObject):
    INVERSION = QtCore.Signal()
    CHARACTERISATION = QtCore.Signal()
    PTI_SETTINGS = QtCore.Signal()
    LOGGING_UPDATE = QtCore.Signal()

    def __init__(self):
        QtCore.QObject.__init__(self)


class QtHandler(logging.Handler):
    _LOGGING_HISTORY = 20

    def __init__(self, model):
        logging.Handler.__init__(self)
        self.logging_messages = deque(maxlen=QtHandler._LOGGING_HISTORY)
        self.model = model
        self.formatter = logging.Formatter('%(levelname)s %(asctime)s: %(message)s\n', datefmt='%Y-%m-%d %H:%M:%S')

    def emit(self, record: logging.LogRecord):
        self.logging_messages.append(self.format(record))
        self.model.observers.logging_update.emit()


@dataclass
class Threads:
    inversion = threading.Thread()
    characterisation = threading.Thread()
    daq = threading.Thread()


_pti_calculations = namedtuple("PTI", ("decimation", "inversion", "characterization"))


def find_delimiter(file_path):
    delimiter_sniffer = csv.Sniffer()
    if not file_path:
        return
    with open(file_path, "r") as file:
        delimiter = str(delimiter_sniffer.sniff(file.readline()).delimiter)
    return delimiter


def calculate_mean(data, mean_size):
    i = 1
    current_mean = data[0]
    result = [current_mean]
    while i < Calculation.MEAN_INTERVAL and i < len(data):
        current_mean += data[i]
        result.append(current_mean / i)
        i += 1
    result.extend(ndimage.uniform_filter1d(data[mean_size:], size=mean_size))
    return result


class BufferedData:
    _QUEUE_SIZE = 1000
    MEAN_SIZE = 60

    def __init__(self):
        self.time = deque(maxlen=BufferedData._QUEUE_SIZE)
        self.dc_values = [deque(maxlen=BufferedData._QUEUE_SIZE) for _ in range(3)]
        self.interferometric_phase = deque(maxlen=BufferedData._QUEUE_SIZE)
        self.sensitivity = deque(maxlen=BufferedData._QUEUE_SIZE)
        self.pti_signal = deque(maxlen=BufferedData._QUEUE_SIZE)
        self.pti_signal_mean = deque(maxlen=BufferedData._QUEUE_SIZE)
        self.pti_signal_mean_queue = deque(maxlen=BufferedData.MEAN_SIZE)
        self.amplitudes = [deque(maxlen=BufferedData._QUEUE_SIZE) for _ in range(3)]
        self.output_phases = [deque(maxlen=BufferedData._QUEUE_SIZE) for _ in range(3)]
        self.time_counter = itertools.count()
        self.time_stamps = deque(maxlen=BufferedData._QUEUE_SIZE)

    def __getitem__(self, key):
        return getattr(self, key.casefold().replace(" ", "_"))

    def __setitem__(self, key, value):
        setattr(self, key.casefold().replace(" ", "_"), value)

    def add_pti_data(self, pti_data: _pti_calculations, interferometer: interferometry.Interferometer):
        for i in range(3):
            self.dc_values[i].append(pti_data.decimation.dc_signals[i])
        self.interferometric_phase.append(interferometer.phase)
        self.sensitivity.append(pti_data.inversion.sensitivity)
        self.pti_signal.append(pti_data.inversion.pti_signal)
        self.pti_signal_mean_queue.append(pti_data.inversion.pti_signal)
        self.pti_signal_mean.append(np.mean(self.pti_signal_mean_queue))
        self.time.append(next(self.time_counter))

    def clear_buffers(self):
        self.time_counter = itertools.count()
        self.time = deque(maxlen=BufferedData._QUEUE_SIZE)
        self.dc_values = [deque(maxlen=BufferedData._QUEUE_SIZE) for _ in range(3)]
        self.interferometric_phase = deque(maxlen=BufferedData._QUEUE_SIZE)
        self.sensitivity = deque(maxlen=BufferedData._QUEUE_SIZE)
        self.pti_signal = deque(maxlen=BufferedData._QUEUE_SIZE)
        self.pti_signal_mean = deque(maxlen=BufferedData._QUEUE_SIZE)
        self.amplitudes = [deque(maxlen=BufferedData._QUEUE_SIZE) for _ in range(3)]
        self.output_phases = [deque(maxlen=BufferedData._QUEUE_SIZE) for _ in range(3)]
        self.time_stamps = deque(maxlen=BufferedData._QUEUE_SIZE)


class Calculation:
    MEAN_INTERVAL = 60

    def __init__(self, queue_size=1000):
        self.running = threading.Event()
        self.settings_path = ""
        self.queue_size = queue_size
        self.signals = _Signals()
        self.dc_signals = []
        self.buffered_data = BufferedData()
        self.pti_signal_mean_queue = deque(maxlen=60)
        self.current_time = 0
        self.interferometer = interferometry.Interferometer()
        self.pti = _pti_calculations(pti.Decimation(), pti.Inversion(interferometry=self.interferometer),
                                     interferometry.Characterization(interferometry=self.interferometer))
        self.daq = DAQ()
        self.live = threading.Event()

    def live_calculation(self):
        def calculate_characterization():
            while self.live.is_set():
                self.pti.characterization()

        def calculate_inversion():
            while self.live.is_set():
                self.pti.decimation.ref = np.array(self.daq.ref_signal)
                self.pti.decimation.dc_coupled = np.array(self.daq.dc_coupled)
                self.pti.decimation.ac_coupled = np.array(self.daq.ac_coupled)
                self.pti.decimation()
                self.pti.inversion.lock_in = self.pti.decimation.lock_in  # Note that this copies a reference
                self.pti.inversion.dc_signals = self.pti.decimation.dc_signals
                self.pti.inversion()
                self.pti.characterization.add_phase(self.interferometer.phase)
                self.dc_signals.append(copy.deepcopy(self.pti.decimation.dc_signals))
                if self.pti.characterization.enough_values():
                    self.pti.characterization.signals = copy.deepcopy(self.dc_signals)
                    self.pti.characterization.phases = copy.deepcopy(self.pti.characterization.tracking_phase)
                    self.pti.characterization.event.set()
                    self.dc_signals = []
                    self.signals.CHARACTERISATION.emit()
                self.buffered_data.add_pti_data(self.pti, self.interferometer)
                self.signals.INVERSION.emit()

        characterization_thread = threading.Thread(target=calculate_characterization)
        inversion_thread = threading.Thread(target=calculate_inversion)
        characterization_thread.start()
        inversion_thread.start()
        return characterization_thread, inversion_thread

    def __call__(self):
        self.pti.inversion.init_header = True
        self.pti.decimation.init_header = True
        self.pti.characterization.init_online = True
        self.running.set()
        self.live_calculation()

    def calculate_characterisation(self, dc_file_path, use_settings=False, settings_path=""):
        self.interferometer.decimation_filepath = dc_file_path
        self.interferometer.settings_path = settings_path
        self.pti.characterization.use_settings = use_settings
        self.pti.characterization()

    def calculate_decimation(self, decimation_path):
        self.pti.decimation.file_path = decimation_path
        self.pti.decimation()

    def calculate_inversion(self, settings_path, inversion_path):
        self.interferometer.decimation_filepath = inversion_path
        self.interferometer.settings_path = settings_path
        self.pti.inversion()


class DAQ:
    def __init__(self):
        self.daq = driver.DAQ()
        self.running = threading.Event()
        self._inversion_flag = False
        self._characterisation_flag = False
        self.logging = QtHandler(self)

    @property
    def ref_signal(self):
        return self.daq.package_data.ref_signal.get(block=True)

    @property
    def dc_coupled(self):
        return self.daq.package_data.dc_coupled.get(block=True)

    @property
    def ac_coupled(self):
        return self.daq.package_data.ac_coupled.get(block=True)


class Measurement:
    def __init__(self, calculation: Calculation, device: driver.DAQ, buffered_data: BufferedData):
        self.device = device
        self.calculation = calculation
        self.buffered_data = buffered_data
        self.threads = {}
        self.running = False

    def __call__(self):
        if not self.running:
            self.device.running.set()
            self.calculation.running.set()
            self.threads["Device"] = threading.Thread(target=self.device, daemon=True)
            self.threads["Calculation"] = threading.Thread(target=self.calculation, daemon=True)
            for name, thread in self.threads:
                thread.start()
        else:
            self.device.running.clear()
            self.calculation.running.clear()
            self.buffered_data.clear_buffers()
