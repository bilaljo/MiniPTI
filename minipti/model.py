import numpy as np
from scipy import ndimage
from dataclasses import dataclass
import logging
from collections import deque, namedtuple
import threading
import os

from PySide6 import QtCore
import pandas as pd

import interferometry
import pti
import driver


@dataclass
class _Struct:
    def __getitem__(self, key):
        return getattr(self, key.casefold().replace(" ", "_"))

    def __setitem__(self, key, value):
        setattr(self, key.casefold().replace(" ", "_"), value)


class BufferedData(_Struct):
    _QUEUE_SIZE = 1000

    def __init__(self):
        self.time = deque(maxlen=BufferedData._QUEUE_SIZE)
        self.dc_values = [deque(maxlen=BufferedData._QUEUE_SIZE) for _ in range(3)]
        self.interferometric_phase = deque(maxlen=BufferedData._QUEUE_SIZE)
        self.sensitivity = deque(maxlen=BufferedData._QUEUE_SIZE)
        self.pti_signal = deque(maxlen=BufferedData._QUEUE_SIZE)
        self.pti_signal_mean = deque(maxlen=BufferedData._QUEUE_SIZE)
        self.amplitudes = [deque(maxlen=BufferedData._QUEUE_SIZE) for _ in range(3)]
        self.output_phases = [deque(maxlen=BufferedData._QUEUE_SIZE) for _ in range(3)]
        self.time_stamps = deque(maxlen=BufferedData._QUEUE_SIZE)

    def clear_buffers(self):
        self.time = deque(maxlen=BufferedData._QUEUE_SIZE)
        self.dc_values = [deque(maxlen=BufferedData._QUEUE_SIZE) for _ in range(3)]
        self.interferometric_phase = deque(maxlen=BufferedData._QUEUE_SIZE)
        self.sensitivity = deque(maxlen=BufferedData._QUEUE_SIZE)
        self.pti_signal = deque(maxlen=BufferedData._QUEUE_SIZE)
        self.pti_signal_mean = deque(maxlen=BufferedData._QUEUE_SIZE)
        self.amplitudes = [deque(maxlen=BufferedData._QUEUE_SIZE) for _ in range(3)]
        self.output_phases = [deque(maxlen=BufferedData._QUEUE_SIZE) for _ in range(3)]
        self.time_stamps = deque(maxlen=BufferedData._QUEUE_SIZE)


class Settings(QtCore.QAbstractTableModel):
    HEADERS = ["Detector 1", "Detector 2", "Detector 3"]
    INDEX = ["Amplitude [V]", "Offset [V]", "Output Phases [deg]", "Response Phases [deg]"]
    SIGNIFICANT_VALUES = 4

    def __init__(self):
        QtCore.QAbstractTableModel.__init__(self)
        self._data = pd.DataFrame(columns=Settings.HEADERS, index=Settings.INDEX)
        self._file_path = "configs/settings.csv"
        self._observer_callbacks = []

    def rowCount(self, parent=None):
        return self._data.shape[0]

    def columnCount(self, parent=None):
        return self._data.shape[1]

    def data(self, index, role: int = ...):
        if index.isValid():
            if role == Qt.DisplayRole or role == Qt.EditRole:
                value = self._data.values[index.row()][index.column()]
                return str(round(value, Settings.SIGNIFICANT_VALUES))

    def flags(self, index):
        return QtCore.Qt.ItemIsSelectable | QtCore.Qt.ItemIsEnabled | QtCore.Qt.ItemIsEditable

    def setData(self, index, value, role: int = ...):
        if index.isValid():
            if role == Qt.EditRole:
                self._data.at[Settings.INDEX[index.row()], Settings.HEADERS[index.column()]] = value
                return True

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if orientation == Qt.Horizontal and role == Qt.DisplayRole:
            return Settings.HEADERS[section]
        elif orientation == Qt.Vertical and role == Qt.DisplayRole:
            return Settings.INDEX[section]
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
        self._data = pd.DataFrame(data, columns=Settings.HEADERS, index=Settings.INDEX)

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


class Observers(QtCore.QObject):
    def __init__(self):
        QtCore.QObject.__init__(self)

    inversion = QtCore.Signal()
    characterisation = QtCore.Signal()
    pti_settings = QtCore.Signal()
    logging_update = QtCore.Signal()


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


class Calculation:
    def __init__(self):
        pass


class Driver:
    MEAN_INTERVAL = 60

    def __init__(self, queue_size=1000):
        self.queue_size = queue_size
        self.buffered_data = BufferedData()
        self.pti_signal_mean_queue = deque(maxlen=60)
        self.current_time = 0
        pti_calculations = namedtuple("PTI", ("decimation", "inversion", "characterization"))
        self.interferometry = interferometry.Interferometer()
        self.pti = pti_calculations(pti.Decimation(), pti.Inversion(interferometry=self.interferometry),
                                    interferometry.Characterization(interferometry=self.interferometry))
        self.decimation_path = ""
        self.settings = Settings()
        self.daq = driver.DAQ()
        self.pti.decimation.daq = self.daq
        self.delimiter_sniffer = csv.Sniffer()
        self.live_measurement = pti.LiveMeasurement(self.interferometry,
                                                    self.pti.inversion, self.pti.characterization, self.pti.decimation)
        self.running = threading.Event()
        self.threads = Threads()
        self._inversion_flag = False
        self._characterisation_flag = False
        self.observers = Observers()
        self.pti.characterization.observers.append(self.update_parameter_buffer)
        self.pti.characterization.observers.append(self.update_settings_parameters)
        self.pti.characterization.observers.append(self.emit_parameter_plot_signal)
        self.logging = QtHandler(self)

    def init_settings(self):
        if not os.path.exists("configs/settings.csv"):  # If no settings found, a new empty file is created.
            self.settings.save()
        else:
            try:
                settings = pd.read_csv("configs/settings.csv", index_col="Setting")
            except FileNotFoundError:
                self.settings.save()
            else:
                if list(settings.columns) != Settings.HEADERS or list(settings.index) != Settings.INDEX:
                    self.settings.save()  # The file is in any way broken.

    def load_settings(self):
        try:
            self.settings.load()
        except (ValueError, PermissionError) as e:
            logging.error(f"Could not load settings. Exception was \"{e}\".")
            return

    def save_settings(self):
        self.settings.save()

    def emit_parameter_plot_signal(self):
        self.observers.characterisation.emit()

    @property
    def measurement_running(self):
        return self.live_measurement.running.is_set()

    def find_delimiter(self, file_path):
        if not file_path:
            return
        with open(file_path, "r") as file:
            delimiter = str(self.delimiter_sniffer.sniff(file.readline()).delimiter)
        return delimiter

    def update_parameter_buffer(self):
        self.buffered_data.time_stamps.append(self.pti.characterization.time_stamp)
        for i in range(3):
            amplitudes = self.interferometry.amplitudes
            self.buffered_data.amplitudes[i].append(amplitudes[i])
            output_phases = np.rad2deg(self.interferometry.output_phases)
            self.buffered_data.output_phases[i].append(output_phases[i])

    def update_settings_parameters(self):
        self.settings.table_data.loc["Output Phases [deg]"] = np.rad2deg(self.interferometry.output_phases)
        self.settings.table_data.loc["Amplitude [V]"] = self.interferometry.amplitudes
        self.settings.table_data.loc["Offset [V]"] = self.interferometry.offsets

    def update_settings(self):
        self.interferometry.settings_path = self.settings.file_path
        self.pti.inversion.settings_path = self.settings.file_path
        self.interferometry.init_settings()
        self.pti.inversion.load_response_phase()

    @staticmethod
    def calculate_mean(data):
        i = 1
        current_mean = data[0]
        result = [current_mean]
        while i < Model.MEAN_INTERVAL and i < len(data):
            current_mean += data[i]
            result.append(current_mean / i)
            i += 1
        result.extend(ndimage.uniform_filter1d(data[Model.MEAN_INTERVAL:], size=Model.MEAN_INTERVAL))
        return result

    def calculate_characterisation(self, dc_file_path, use_settings=False, settings_path=""):
        self.interferometry.decimation_filepath = dc_file_path
        self.interferometry.settings_path = settings_path
        self.pti.characterization.use_settings = use_settings
        self.pti.characterization(mode="offline")

    def calculate_decimation(self, decimation_path):
        self.pti.decimation.file_path = decimation_path
        self.pti.decimation(mode="offline")

    def calculate_inversion(self, settings_path, inversion_path):
        self.interferometry.decimation_filepath = inversion_path
        self.interferometry.settings_path = settings_path
        self.pti.inversion(mode="offline")

    def live_calculation(self):
        while self.running.is_set():
            self.live_measurement.calculate_inversion()
            self.pti.inversion.settings_path = self.settings.file_path
            for i in range(3):
                self.buffered_data.dc_values[i].append(self.pti.decimation.dc_signals[i])
            self.buffered_data.interferometric_phase.append(self.interferometry.phase)
            self.buffered_data.sensitivity.append(self.pti.inversion.sensitivity)
            self.buffered_data.pti_signal.append(self.pti.inversion.pti_signal)
            self.pti_signal_mean_queue.append(self.pti.inversion.pti_signal)
            self.buffered_data.pti_signal_mean.append(np.mean(self.pti_signal_mean_queue))
            self.current_time += 1
            self.buffered_data.time.append(self.current_time)
            self.observers.inversion.emit()

    def run_measurement(self):
        self.live_measurement.running.set()
        self.threads.characterisation = threading.Thread(target=self.live_measurement.calculate_characterization,
                                                         daemon=True)
        self.threads.inversion = threading.Thread(target=self.live_calculation, daemon=True)
        self.threads.inversion.start()
        self.threads.characterisation.start()

    def clear_all(self):
        self.daq.running.clear()
        self.buffered_data.clear_buffers()
        self.live_measurement.running.clear()
        self.current_time = 0
        self.pti.inversion.init_header = True
        self.pti.decimation.init_header = True
        self.pti.characterization.init_online = True

    def connect_daq(self):
        self.daq.find_port()

    def start_daq(self):
        self.daq.running.set()
        self.threads.daq = threading.Thread(target=self.daq, daemon=True)
        self.threads.daq.start()

    def stop_daq(self):
        self.daq.running.clear()

    def stop_measurement(self):
        self.live_measurement.running.clear()
        self.clear_all()
        self.running.clear()
