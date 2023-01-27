import abc
import copy
import csv
import dataclasses
import itertools
import json
import logging
import os
import threading
from collections import deque
import typing
from dataclasses import dataclass

import dacite
import numpy as np
import pandas as pd
from PySide6 import QtCore
from scipy import ndimage

from minipti import interferometry, pti
import hardware


class SettingsTable(QtCore.QAbstractTableModel):
    HEADERS = ["Detector 1", "Detector 2", "Detector 3"]
    INDEX = ["Amplitude [V]", "Offset [V]", "Output Phases [deg]", "Response Phases [deg]"]
    SIGNIFICANT_VALUES = 4

    def __init__(self):
        QtCore.QAbstractTableModel.__init__(self)
        self._data = pd.DataFrame(columns=SettingsTable.HEADERS, index=SettingsTable.INDEX)
        self._file_path = "minipti/configs/settings.csv"
        self._observer_callbacks = []

    def rowCount(self, parent=None):
        return self._data.shape[0]

    def columnCount(self, parent=None):
        return self._data.shape[1]

    def data(self, index, role: int = ...):
        if index.isValid():
            if role == QtCore.Qt.DisplayRole or role == QtCore.Qt.EditRole:
                value = self._data.at[SettingsTable.INDEX[index.row()], SettingsTable.HEADERS[index.column()]]
                return str(round(value, SettingsTable.SIGNIFICANT_VALUES))

    def flags(self, index):
        return QtCore.Qt.ItemIsSelectable | QtCore.Qt.ItemIsEnabled | QtCore.Qt.ItemIsEditable

    def setData(self, index, value, role: int = ...):
        if index.isValid():
            if role == QtCore.Qt.EditRole:
                self._data.at[SettingsTable.INDEX[index.row()], SettingsTable.HEADERS[index.column()]] = float(value)
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

    @property
    def file_path(self):
        return self._file_path

    @file_path.setter
    def file_path(self, file_path: str):
        if os.path.exists(file_path):
            self._file_path = file_path

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
        if not os.path.exists("minipti/configs/settings.csv"):  # If no settings found, a new empty file is created.
            self.save()
        else:
            try:
                settings = pd.read_csv("minipti/configs/settings.csv", index_col="Setting")
            except FileNotFoundError:
                self.save()
            else:
                if list(settings.columns) != SettingsTable.HEADERS or list(settings.index) != SettingsTable.INDEX:
                    self.save()  # The file is in any way broken.
                else:
                    self.table_data = settings


class Logging(logging.Handler):
    LOGGING_HISTORY = 20

    def __init__(self):
        logging.Handler.__init__(self)
        self.logging_messages = deque(maxlen=Logging.LOGGING_HISTORY)
        self.formatter = logging.Formatter('%(levelname)s %(asctime)s: %(message)s\n', datefmt='%Y-%m-%d %H:%M:%S')
        logging.getLogger().addHandler(self)

    def emit(self, record: logging.LogRecord):
        self.logging_messages.append(self.format(record))
        signals.logging_update.emit(self.logging_messages)


def find_delimiter(file_path: str):
    delimiter_sniffer = csv.Sniffer()
    if not file_path:
        return
    with open(file_path, "r") as file:
        delimiter = str(delimiter_sniffer.sniff(file.readline()).delimiter)
    return delimiter


def running_average(data, mean_size: int):
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
        self._pti_signal_mean_queue = deque(maxlen=PTIBuffer.MEAN_SIZE)

    def append(self, pti_data: PTI, interferometer: interferometry.Interferometer):
        for i in range(3):
            self.dc_values[i].append(pti_data.decimation.dc_signals[i])
        self.interferometric_phase.append(interferometer.phase)
        self.sensitivity.append(pti_data.inversion.sensitivity)
        self.pti_signal.append(pti_data.inversion.pti_signal)
        self._pti_signal_mean_queue.append(pti_data.inversion.pti_signal)
        self._pti_signal_mean_queue.append(np.mean(self.pti_signal_mean))
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


@dataclass(init=False, frozen=True)
class Signals(QtCore.QObject):
    decimation = QtCore.Signal(pd.DataFrame)
    decimation_live = QtCore.Signal(Buffer)
    inversion = QtCore.Signal(pd.DataFrame)
    inversion_live = QtCore.Signal(Buffer)
    characterization = QtCore.Signal(pd.DataFrame)
    characterization_live = QtCore.Signal(Buffer)
    settings_pti = QtCore.Signal()
    logging_update = QtCore.Signal(deque)
    daq_running = QtCore.Signal()
    laser_voltage = QtCore.Signal(float)

    def __init__(self):
        QtCore.QObject.__init__(self)


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
        self.driver = Driver()
        self.running = threading.Event()

    def live_calculation(self):
        def calculate_characterization():
            while self.running.is_set() and self.driver.ports.daq.is_open():
                self.interferometry.characterization()
                self.characterisation_buffer.append(self.interferometry)
                signals.characterization.emit(self.characterisation_buffer)

        def calculate_inversion():
            while self.running.is_set() and self.driver.ports.daq.is_open():
                self.pti.decimation.ref = np.array(self.driver.ports.daq.ref_signal)
                self.pti.decimation.dc_coupled = np.array(self.driver.ports.daq.dc_coupled)
                self.pti.decimation.ac_coupled = np.array(self.driver.ports.daq.ac_coupled)
                self.pti.decimation()
                self.pti.inversion.lock_in = self.pti.decimation.lock_in  # Note that this copies a reference
                self.pti.inversion.dc_signals = self.pti.decimation.dc_signals
                signals.decimation_live.emit(self.pti_buffer)
                self.pti.inversion()
                self.interferometry.characterization.add_phase(self.interferometry.interferometer.phase)
                self.dc_signals.append(copy.deepcopy(self.pti.decimation.dc_signals))
                if self.interferometry.characterization.enough_values():
                    self.interferometry.characterization.signals = copy.deepcopy(self.dc_signals)
                    self.interferometry.characterization.phases = copy.deepcopy(
                        self.interferometry.characterization.tracking_phase)
                    self.interferometry.characterization.event.set()
                    self.dc_signals = []
                    Signals.characterization_live.emit(self.characterisation_buffer)
                self.pti_buffer.append(self.pti, self.interferometry.interferometer)
                signals.inversion_live.emit(self.pti_buffer)

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


class Ports(typing.NamedTuple):
    daq: hardware.driver.DAQ
    laser: hardware.driver.Laser
    tec: hardware.driver.Tec


class Driver:
    def __init__(self):
        self.ports = Ports(daq=hardware.driver.DAQ(), laser=hardware.driver.Laser(), tec=hardware.driver.Tec())

    def open_daq(self):
        self.ports.daq.open()

    def open_laser(self):
        self.ports.laser.open()

    def open_tec(self):
        self.ports.tec.open()

    def close(self):
        for port in self.ports:
            if port.is_open():
                port.close()

    def find_device(self):
        for port in self.ports:
            try:
                port.find_port()
            except hardware.driver.SerialError:
                continue  # Check still the other devices for connection


class DAQMeasurement:
    """
    Functor which process income DAQ data and saves it to an internally buffer.
    Processing incoming data is optional.
    """
    def __init__(self, device: hardware.driver.DAQ):
        self.device = device
        self.threads = {}
        self.running = False
        self.calculation = Calculation()

    def __call__(self):
        if not self.running:
            if not self.device.is_open():
                self.device.open()
            self.device.running.set()
            self.threads["Calculation"] = threading.Thread(target=self.calculation, daemon=True)
            self.threads["Device"] = threading.Thread(target=self.device, daemon=True)
            for name, thread in self.threads:
                thread.start()
            self.running ^= True
            signals.daq_running.emit()
        else:
            self.device.running.clear()
            self.calculation.running.clear()
            self.calculation.pti_buffer.clear()
            self.calculation.characterisation_buffer.clear()
            self.running ^= True
            signals.daq_running.emit()


def _process__data(file_path: str, headers: list[str]) -> pd.DataFrame:
    if not file_path:
        raise FileNotFoundError("No file path given")
    delimiter = find_delimiter(file_path)
    try:
        data = pd.read_csv(file_path, delimiter=delimiter, skiprows=[1], index_col="Time")
    except ValueError:  # Data isn't saved with any index
        data = pd.read_csv(file_path, delimiter=delimiter, skiprows=[1])
    for header in headers:
        for header_data in data.columns:
            if header == header_data:
                break
        else:
            raise KeyError(f"Header {header} not found in file")
    return data


def process_dc_data(dc_file_path: str):
    headers = ["DC CH1", "DC CH2", "DC CH3"]
    data = _process__data(dc_file_path, headers)
    signals.decimation.emit(data)


def process_inversion_data(inversion_file_path: str):
    headers = ["Interferometric Phase", "Sensitivity", "PTI Signal"]
    data = _process__data(inversion_file_path, headers)
    signals.inversion.emit(data)


def process_characterization_data(characterization_file_path: str):
    headers = [f"Amplitudes CH{i}" for i in range(3)]
    headers += [f"Output Phases CH{i}" for i in range(3)]
    headers += [f"Offsets CH{i}" for i in range(3)]
    data = _process__data(characterization_file_path, headers)
    data["PTI Signal 60 s Mean"] = running_average(data["PTI Signal"], mean_size=60)
    signals.characterization.emit(data)



class Laser:
    def __init__(self, config_path="hardware/laser.json"):
        self._driver_bits = 0
        self.config_path = config_path
        self.configuration = None  # type: None | PumpLaser
        self.load_config()

    def load_config(self):
        with open(self.config_path) as config:
            self.configuration = dacite.from_dict(PumpLaser, json.load(config))

    @property
    def driver_bits(self):
        return self._driver_bits

    @driver_bits.setter
    def driver_bits(self, bits):
        self._driver_bits = bits
        self._update_laser_driver_voltage()

    def _update_laser_driver_voltage(self):
        self.configuration.bit_value = self._driver_bits
        voltage = hardware.driver.Laser.bit_to_voltage(hardware.driver.Laser.NUMBER_OF_STEPS - self._driver_bits)
        signals.laser_voltage.emit(voltage)

    @staticmethod
    def process_mode_index(index):
        continoues_wave = False
        pulsed_mode = False
        match index:
            case 0:
                continoues_wave = False
                pulsed_mode = False
            case 1:
                continoues_wave = True
                pulsed_mode = False
            case 2:
                continoues_wave = False
                pulsed_mode = True
        return continoues_wave, pulsed_mode

    def mode_dac1(self, i):
        def update(index):
            continoues_wave, pulsed_mode = Laser.process_mode_index(index)
            self.configuration.DAC_1.continuous_wave[i] = continoues_wave
            self.configuration.DAC_1.pulsed_mode[i] = pulsed_mode
        return update

    def mode_dac2(self, i):
        def update(index):
            continoues_wave, pulsed_mode = Laser.process_mode_index(index)
            self.configuration.DAC_2.continuous_wave[i] = continoues_wave
            self.configuration.DAC_2.pulsed_mode[i] = pulsed_mode
        return update

    def update_configuration(self):
        with open(self.config_path, "w") as configuration:
            print(self.configuration)
            configuration.write(json.dumps(dataclasses.asdict(self.configuration), indent=2))


signals = Signals()
