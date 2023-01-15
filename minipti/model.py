import abc
import copy
import csv
import itertools
import logging
import os
import threading
from collections import deque
import typing

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
    def file_path(self, file_path: str):
        if os.path.exists(file_path):
            self._file_path = file_path

    @property
    def observer_callbacks(self):
        return self._observer_callbacks

    def add_observer(self, callback: typing.Callable):
        self._observer_callbacks.append(callback)

    def save(self):
        self._data.to_csv(self.file_path, index_label="Setting", index=True)

    def load(self):
        self.table_data = pd.read_csv(self.file_path, index_col="Setting")

    def update_settings_parameters(self, interferometer: interferometry.Interferometer):
        self.table_data.loc["Output Phases [deg]"] = np.rad2deg(interferometer.output_phases)
        self.table_data.loc["Amplitude [V]"] = interferometer.amplitudes
        self.table_data.loc["Offset [V]"] = interferometer.offsets

    def update_settings(self, interferometer: interferometry.Interferometer, inversion: pti.Inversion):
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


class Signals(QtCore.QObject):
    inversion = QtCore.Signal()
    characterization = QtCore.Signal()
    settings_pti = QtCore.Signal()
    logging_update = QtCore.Signal()

    def __init__(self):
        QtCore.QObject.__init__(self)


class Logging(logging.Handler):
    LOGGING_HISTORY = 20

    def __init__(self):
        logging.Handler.__init__(self)
        self.logging_messages = deque(maxlen=Logging.LOGGING_HISTORY)
        self.formatter = logging.Formatter('%(levelname)s %(asctime)s: %(message)s\n', datefmt='%Y-%m-%d %H:%M:%S')

    def emit(self, record: logging.LogRecord):
        self.logging_messages.append(self.format(record))
        Signals.logging_update.emit()


def find_delimiter(file_path: str):
    delimiter_sniffer = csv.Sniffer()
    if not file_path:
        return
    with open(file_path, "r") as file:
        delimiter = str(delimiter_sniffer.sniff(file.readline()).delimiter)
    return delimiter


def calculate_mean(data, mean_size: int):
    i = 1
    current_mean = data[0]
    result = [current_mean]
    while i < Calculation.MEAN_INTERVAL and i < len(data):
        current_mean += data[i]
        result.append(current_mean / i)
        i += 1
    result.extend(ndimage.uniform_filter1d(data[mean_size:], size=mean_size))
    return result


class Buffer:
    """
    The buffer contains the queues for incoming data and the timer for them.
    """
    QUEUE_SIZE = 1000

    def __init__(self):
        self.time_counter = itertools.count()
        self.time = deque(maxlen=Buffer.QUEUE_SIZE)

    def __getitem__(self, key):
        return getattr(self, key.casefold().replace(" ", "_"))

    def __setitem__(self, key, value):
        setattr(self, key.casefold().replace(" ", "_"), value)

    def __iter__(self):
        for member in dir(self):
            if not callable(getattr(self, member)) and not member.startswith("__") and member != "time_counter":
                yield getattr(self, member)

    @abc.abstractmethod
    def append(self, *args):
        ...

    def clear(self):
        for member in dir(self):
            if not callable(getattr(self, member)) and not member.startswith("__"):
                if member == self.time_counter:
                    self.time_counter = itertools.count()  # Reset counter
                else:
                    setattr(self, member, deque(maxlen=Buffer.QUEUE_SIZE))


class PTI(typing.NamedTuple):
    decimation: pti.Decimation
    inversion: pti.Inversion


class Interferometry(typing.NamedTuple):
    interferometer: interferometry.Interferometer
    characterization: interferometry.Characterization


class PTIBuffer(Buffer):
    MEAN_SIZE = 60
    CHANNELS = 3

    def __init__(self):
        Buffer.__init__(self)
        self.dc_values = [deque(maxlen=Buffer.QUEUE_SIZE) for _ in range(PTIBuffer.CHANNELS)]
        self.interferometric_phase = deque(maxlen=Buffer.QUEUE_SIZE)
        self.sensitivity = deque(maxlen=Buffer.QUEUE_SIZE)
        self.pti_signal = deque(maxlen=Buffer.QUEUE_SIZE)
        self.pti_signal_mean = deque(maxlen=Buffer.QUEUE_SIZE)
        self.pti_signal_mean_queue = deque(maxlen=PTIBuffer.MEAN_SIZE)

    def append(self, pti_data: PTI, interferometer: interferometry.Interferometer):
        for i in range(3):
            self.dc_values[i].append(pti_data.decimation.dc_signals[i])
        self.interferometric_phase.append(interferometer.phase)
        self.sensitivity.append(pti_data.inversion.sensitivity)
        self.pti_signal.append(pti_data.inversion.pti_signal)
        self.pti_signal_mean_queue.append(pti_data.inversion.pti_signal)
        self.pti_signal_mean_queue.append(np.mean(self.pti_signal_mean))
        self.time.append(next(self.time_counter))


class CharacterisationBuffer(Buffer):
    CHANNELS = 3

    def __init__(self):
        Buffer.__init__(self)
        self.output_phases = [deque(maxlen=Buffer.QUEUE_SIZE) for _ in range(self.CHANNELS)]
        # The number of channels for output phases is -1 because the first channel has always the phase 0 by definition.
        self.amplitudes = [deque(maxlen=Buffer.QUEUE_SIZE) for _ in range(CharacterisationBuffer.CHANNELS - 1)]

    def append(self, interferometry_data: Interferometry):
        for i in range(3):
            self.amplitudes.append(interferometry_data.interferometer.amplitudes)
        for i in range(2):
            self.output_phases.append(interferometry_data.interferometer.amplitudes)
        self.time.append(interferometry_data.characterization.time_stamp)


class Calculation:
    MEAN_INTERVAL = 60

    def __init__(self, queue_size=1000):
        self.settings_path = ""
        self.queue_size = queue_size
        self.dc_signals = []
        self.pti_buffer = PTIBuffer()
        self.characterisation_buffer = CharacterisationBuffer()
        self.pti_signal_mean_queue = deque(maxlen=60)
        self.current_time = 0
        self.interferometry = Interferometry(interferometry.Interferometer(), interferometry.Characterization())
        self.pti = PTI(pti.Decimation(), pti.Inversion(interferometry=self.interferometry.interferometer))
        self.daq = DAQ()
        self.running = threading.Event()

    def live_calculation(self):
        def calculate_characterization():
            while self.running.is_set():
                self.interferometry.characterization()
                self.characterisation_buffer.append(self.interferometry)

        def calculate_inversion():
            while self.running.is_set():
                self.pti.decimation.ref = np.array(self.daq.ref_signal)
                self.pti.decimation.dc_coupled = np.array(self.daq.dc_coupled)
                self.pti.decimation.ac_coupled = np.array(self.daq.ac_coupled)
                self.pti.decimation()
                self.pti.inversion.lock_in = self.pti.decimation.lock_in  # Note that this copies a reference
                self.pti.inversion.dc_signals = self.pti.decimation.dc_signals
                self.pti.inversion()
                self.interferometry.characterization.add_phase(self.interferometry.interferometer.phase)
                self.dc_signals.append(copy.deepcopy(self.pti.decimation.dc_signals))
                if self.interferometry.characterization.enough_values():
                    self.interferometry.characterization.signals = copy.deepcopy(self.dc_signals)
                    self.interferometry.characterization.phases = copy.deepcopy(
                        self.interferometry.characterization.tracking_phase)
                    self.interferometry.characterization.event.set()
                    self.dc_signals = []
                    Signals.characterization.emit()
                self.pti_buffer.append(self.pti, self.interferometry.interferometer)
                Signals.inversion.emit()

        characterization_thread = threading.Thread(target=calculate_characterization)
        inversion_thread = threading.Thread(target=calculate_inversion)
        characterization_thread.start()
        inversion_thread.start()
        return characterization_thread, inversion_thread

    def __call__(self):
        self.pti.inversion.init_header = True
        self.pti.decimation.init_header = True
        self.interferometry.characterization.init_online = True
        self.live_calculation()

    def calculate_characterisation(self, dc_file_path: str, use_settings=False, settings_path=""):
        self.interferometry.interferometer.decimation_filepath = dc_file_path
        self.interferometry.interferometer.settings_path = settings_path
        self.interferometry.characterization.use_settings = use_settings
        self.interferometry.characterization()

    def calculate_decimation(self, decimation_path: str):
        self.pti.decimation.file_path = decimation_path
        self.pti.decimation()

    def calculate_inversion(self, settings_path: str, inversion_path: str):
        self.interferometry.interferometer.decimation_filepath = inversion_path
        self.interferometry.interferometer.settings_path = settings_path
        self.pti.inversion()


class DAQ:
    def __init__(self):
        self.daq = driver.DAQ()

    def open(self):
        self.daq.open()

    def close(self):
        self.daq.close()

    def find_device(self):
        self.daq.find_port()

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
    """
    Functor which process income driver data (DAQ, Laser, ...) and saves it to an internally buffer.
    Processing incoming data is optional.
    """
    def __init__(self, device: driver.DAQ, buffers: list[Buffer]):
        self.device = device
        self.buffers = buffers
        self.threads = {}
        self.running = False
        self.signals = Signals()

    def __call__(self, calculation):
        if not self.running:
            self.device.running.set()
            if calculation is not None:
                self.threads["Calculation"] = threading.Thread(target=calculation, daemon=True)
            self.threads["Device"] = threading.Thread(target=self.device, daemon=True)
            for name, thread in self.threads:
                thread.start()
            self.running ^= True
        else:
            self.device.running.clear()
            if calculation is not None:
                calculation.running.clear()
            for buffer in self.buffers:
                buffer.clear()
            self.running ^= True
