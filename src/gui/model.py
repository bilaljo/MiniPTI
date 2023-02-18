import abc
import copy
import csv
import dataclasses
import enum
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

import json_parser
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
        signals.settings.connect(self.update_settings)

    @QtCore.Slot(interferometry.Interferometer)
    def update_settings(self, interferometer: interferometry.Interferometer) -> None:
        self.update_settings_parameters(interferometer)

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

    def update_settings_paths(self, interferometer: interferometry.Interferometer, inversion: pti.Inversion):
        interferometer.settings_path = self.file_path
        inversion.settings_path = self.file_path
        interferometer.load_settings()
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
        log = self.format(record)
        if "ERROR" in log:
            log = f"<p style='color:red'>{log}</p>"
        elif "INFO" in log:
            log = f"<p style='color:green'>{log}</p>"
        elif "WARNING" in log:
            log = f"<p style='color:orange'>{log}</p>"
        elif "DEBUG" in log:
            log = f"<p style='color:blue'>{log}</p>"
        elif "CRITICAL" in log:
            log = f"<b><p style='color:darkred'>{log}</p></b>"
        self.logging_messages.append(log)
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
        self.sensitivity = [deque(maxlen=Buffer.QUEUE_SIZE) for _ in range(PTIBuffer.CHANNELS)]
        self.pti_signal = deque(maxlen=Buffer.QUEUE_SIZE)
        self.pti_signal_mean = deque(maxlen=Buffer.QUEUE_SIZE)
        self._pti_signal_mean_queue = deque(maxlen=PTIBuffer.MEAN_SIZE)

    def append(self, pti_data: PTI, interferometer: interferometry.Interferometer):
        for i in range(3):
            self.dc_values[i].append(pti_data.decimation.dc_signals[i])
            self.sensitivity[i].append(pti_data.inversion.sensitivity[i])
        self.interferometric_phase.append(interferometer.phase)
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


class LaserBuffer(Buffer):
    def __init__(self):
        Buffer.__init__(self)
        self.pump_laser_voltage = deque(maxlen=Buffer.QUEUE_SIZE)
        self.pump_laser_current = deque(maxlen=Buffer.QUEUE_SIZE)
        self.probe_laser_current = deque(maxlen=Buffer.QUEUE_SIZE)

    def append(self, laser_data: hardware.laser.LaserData):
        self.time.append(next(self.time_counter) / 10)
        self.pump_laser_current.append(laser_data.pump_laser_current)
        self.pump_laser_voltage.append(laser_data.pump_laser_voltage)
        self.probe_laser_current.append(laser_data.probe_laser_current)


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
    current_dac1 = QtCore.Signal(int)
    current_dac2 = QtCore.Signal(int)
    laser_data = QtCore.Signal(Buffer)
    laser_data_display = QtCore.Signal(hardware.laser.LaserData)
    current_probe_laser = QtCore.Signal(float)
    settings = QtCore.Signal(pd.DataFrame)
    destination_folder_changed = QtCore.Signal(str)

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
        self.interferometry.characterization.interferometry = self.interferometry.interferometer
        self.pti = PTI(pti.Decimation(), pti.Inversion(interferometer=self.interferometry.interferometer))
        self.driver = Hardware()
        self.running = threading.Event()
        self._destination_folder = os.getcwd()

    @property
    def destination_folder(self):
        return self._destination_folder

    @destination_folder.setter
    def destination_folder(self, folder):
        self.interferometry.characterization.destination_folder = folder
        self.pti.inversion.destination_folder = folder
        self._destination_folder = folder
        signals.destination_folder_changed.emit(folder)

    def live_calculation(self):
        self.pti.inversion.init_header = True
        self.pti.decimation.init_header = True
        self.interferometry.characterization.init_online = True
        self.driver.enable_daq()
        self.running.set()

        def calculate_characterization():
            while self.running.is_set():
                self.interferometry.characterization()
                self.characterisation_buffer.append(self.interferometry)
                signals.characterization.emit(self.characterisation_buffer)

        def calculate_inversion():
            while self.running.is_set():
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
                if self.interferometry.characterization.enough_values:
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

    def calculate_characterisation(self, dc_file_path: str, use_settings=False, settings_path=""):
        self.interferometry.interferometer.decimation_filepath = dc_file_path
        self.interferometry.interferometer.settings_path = settings_path
        self.interferometry.characterization.use_settings = use_settings
        self.interferometry.characterization(live=False)
        signals.settings.emit(self.interferometry.interferometer)

    def calculate_decimation(self, decimation_path: str):
        self.pti.decimation.file_path = decimation_path
        self.pti.decimation(live=False)

    def calculate_inversion(self, settings_path: str, inversion_path: str):
        self.interferometry.interferometer.decimation_filepath = inversion_path
        self.interferometry.interferometer.settings_path = settings_path
        self.interferometry.interferometer.load_settings()
        self.pti.inversion(live=False)



class DAQ:
    def __init__(self):
        self.driver = hardware.daq.Driver()
        self.running = False

    def find_daq(self):
        self.driver.find_port()

    def open_daq(self):
        self.driver.open()

    def close(self):
        self.driver.close()

    def enable_daq(self):
        self.driver.run()


class Laser:
    def __init__(self):
        self.laser_driver = hardware.laser.Driver()
        self.config_path = config_path
        self.laser_buffer = LaserBuffer()
        self.load_config()

    def load_config(self):
        with open(self.config_path) as config:
            loaded_config = json.load(config)
            self.laser_driver.pump_laser = dacite.from_dict(hardware.laser.PumpLaser, loaded_config["Pump Laser"])
            self.laser_driver.probe_laser = dacite.from_dict(hardware.laser.ProbeLaser, loaded_config["Probe Laser"])

    @property
    def driver_bits(self):
        return self.laser_driver.pump_laser.bit_value

    @driver_bits.setter
    def driver_bits(self, bits):
        # With increasing the slider decreases its value but the voltage should increase - hence we subtract the bits.
        self.laser_driver.pump_laser.bit_value = hardware.laser.PumpLaser.NUMBER_OF_STEPS - bits
        voltage = hardware.laser.PumpLaser.bit_to_voltage(hardware.laser.PumpLaser.NUMBER_OF_STEPS - bits)
        signals.laser_voltage.emit(voltage)
        self.laser_driver.set_driver_voltage()

    @property
    def current_bits_dac_1(self):
        return self.driver.pump_laser.DAC_1.bit_value

    @current_bits_dac_1.setter
    def current_bits_dac_1(self, bits):
        self.laser_driver.pump_laser.DAC_1.bit_value = bits
        signals.current_dac1.emit(bits)
        self.laser_driver.set_dac_1()

    @property
    def current_bits_dac_2(self):
        return self.laser_driver.pump_laser.DAC_1.bit_value

    @current_bits_dac_2.setter
    def current_bits_dac_2(self, bits):
        self.laser_driver.pump_laser.DAC_2.bit_value = bits
        signals.current_dac2.emit(bits)
        self.laser_driver.set_dac_2()

    @property
    def current_bits_probe_laser(self):
        return self.laser_driver.probe_laser.current_bits

    @current_bits_probe_laser.setter
    def current_bits_probe_laser(self, bits):
        # With increasing the slider decreases its value but the voltage should increase - hence we subtract the bits.
        self.laser_driver.probe_laser.current_bits = hardware.laser.Driver.CURRENT_BITS - bits
        current = hardware.laser.ProbeLaser.bit_to_current(hardware.laser.Driver.CURRENT_BITS - bits)
        signals.current_probe_laser.emit(current)
        self.laser_driver.set_probe_laser_current()

    @property
    def photo_diode_gain(self):
        return self.laser_driver.probe_laser.photo_diode_gain

    @photo_diode_gain.setter
    def photo_diode_gain(self, phot_diode_gain):
        self.laser_driver.probe_laser.photo_diode_gain = phot_diode_gain
        self.laser_driver.set_photo_gain()

    @staticmethod
    def process_mode_index(index):
        continuous_wave = False
        pulsed_mode = False
        match index:
            case Mode.DISABLED:
                continuous_wave = False
                pulsed_mode = False
            case Mode.CONTINUOUS_WAVE:
                continuous_wave = True
                pulsed_mode = False
            case Mode.PULSED:
                continuous_wave = False
                pulsed_mode = True
        return continuous_wave, pulsed_mode

    def mode_dac1(self, i) -> typing.Callable:
        def update(index):
            continuous_wave, pulsed_mode = Laser.process_mode_index(index)
            self.driver.pump_laser.DAC_1.continuous_wave[i] = continuous_wave
            self.driver.pump_laser.DAC_1.pulsed_mode[i] = pulsed_mode
            self.driver.set_dac_matrix()
        return update

    def mode_dac2(self, i) -> typing.Callable:
        def update(index):
            continuous_wave, pulsed_mode = Laser.process_mode_index(index)
            self.driver.pump_laser.DAC_2.continuous_wave[i] = continuous_wave
            self.driver.pump_laser.DAC_2.pulsed_mode[i] = pulsed_mode
            self.driver.set_dac_matrix()
        return update

    def update_configuration(self):
        with open(self.config_path, "w") as configuration:
            lasers = {"Pump Laser": dataclasses.asdict(self.laser_driver.pump_laser),
                      "Probe Laser": dataclasses.asdict(self.laser_driver.probe_laser)}
            configuration.write(json_parser.to_json(lasers) + "\n")

    def process_measured_data(self):
        def incoming_data():
            while self.laser_driver.connected.is_set():
                received_data = self.laser_driver.data.get(block=True)
                self.laser_buffer.append(received_data)
                signals.laser_data.emit(self.laser_buffer)
                signals.laser_data_display.emit(received_data)
        threading.Thread(target=incoming_data, daemon=True).start()


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
    headers = [f"DC CH{i}" for i in range(1, 4)]
    try:
        data = _process__data(dc_file_path, headers)
    except KeyError:
        headers = [f"PD{i}" for i in range(1, 4)]
        data = _process__data(dc_file_path, headers)
    signals.decimation.emit(data)


def process_inversion_data(inversion_file_path: str):
    try:
        headers = ["Interferometric Phase", "Sensitivity CH1", "Sensitivity CH2", "Sensitivity CH3",
                   "Total Sensitivity", "PTI Signal"]
        data = _process__data(inversion_file_path, headers)
        data["PTI Signal 60 s Mean"] = running_average(data["PTI Signal"], mean_size=60)
    except KeyError:
        headers = ["Sensitivity CH1", "Sensitivity CH2", "Sensitivity CH3",
                   "Total Sensitivity", "Interferometric Phase"]
        data = _process__data(inversion_file_path, headers)
    signals.inversion.emit(data)


def process_characterization_data(characterization_file_path: str):
    headers = [f"Amplitude CH{i}" for i in range(1, 4)]
    headers += [f"Output Phase CH{i}" for i in range(1, 4)]
    headers += [f"Offset CH{i}" for i in range(1, 4)]
    data = _process__data(characterization_file_path, headers)
    signals.characterization.emit(data)


class Mode(enum.IntEnum):
    DISABLED = 0
    PULSED = 1
    CONTINUOUS_WAVE = 2


signals = Signals()
