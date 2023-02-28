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

    def rowCount(self, parent=None) -> int:
        return self._data.shape[0]

    def columnCount(self, parent=None) -> int:
        return self._data.shape[1]

    def data(self, index, role: int = ...) -> str | None:
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

    def emit(self, record: logging.LogRecord) -> None:
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


def find_delimiter(file_path: str) -> str | None:
    delimiter_sniffer = csv.Sniffer()
    if not file_path:
        return
    with open(file_path, "r") as file:
        delimiter = str(delimiter_sniffer.sniff(file.readline()).delimiter)
    return delimiter


def running_average(data, mean_size: int) -> list[float]:
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
    def append(self, *args: typing.Any) -> None:
        ...

    def clear(self) -> None:
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
        self.symmetry = deque(maxlen=Buffer.QUEUE_SIZE)
        self.pti_signal = deque(maxlen=Buffer.QUEUE_SIZE)
        self.pti_signal_mean = deque(maxlen=Buffer.QUEUE_SIZE)
        self._pti_signal_mean_queue = deque(maxlen=PTIBuffer.MEAN_SIZE)

    def append(self, pti_data: PTI, interferometer: interferometry.Interferometer) -> None:
        for i in range(3):
            self.dc_values[i].append(pti_data.decimation.dc_signals[i])
            self.sensitivity[i].append(pti_data.inversion.sensitivity[i])
        self.symmetry.append(pti_data.inversion.symmetry)
        self.interferometric_phase.append(interferometer.phase)
        self.pti_signal.append(pti_data.inversion.pti_signal)
        self._pti_signal_mean_queue.append(pti_data.inversion.pti_signal)
        self.pti_signal_mean.append(np.mean(self._pti_signal_mean_queue))
        self.time.append(next(self.time_counter))


class CharacterisationBuffer(Buffer):
    CHANNELS = 3

    def __init__(self):
        Buffer.__init__(self)
        self.output_phases = [deque(maxlen=Buffer.QUEUE_SIZE) for _ in range(self.CHANNELS - 1)]
        # The number of channels for output phases is -1 because the first channel has always the phase 0 by definition.
        self.amplitudes = [deque(maxlen=Buffer.QUEUE_SIZE) for _ in range(CharacterisationBuffer.CHANNELS)]

    def append(self, characterization: interferometry.Characterization,
               interferometer: interferometry.Interferometer) -> None:
        for i in range(3):
            self.amplitudes[i].append(interferometer.amplitudes[i])
        for i in range(2):
            self.output_phases[i].append(interferometer.output_phases[i + 1])
        self.time.append(characterization.time_stamp)


class LaserBuffer(Buffer):
    def __init__(self):
        Buffer.__init__(self)
        self.pump_laser_voltage = deque(maxlen=Buffer.QUEUE_SIZE)
        self.pump_laser_current = deque(maxlen=Buffer.QUEUE_SIZE)
        self.probe_laser_current = deque(maxlen=Buffer.QUEUE_SIZE)

    def append(self, laser_data: hardware.laser.LaserData) -> None:
        self.time.append(next(self.time_counter) / 10)
        self.pump_laser_current.append(laser_data.pump_laser_current)
        self.pump_laser_voltage.append(laser_data.pump_laser_voltage)
        self.probe_laser_current.append(laser_data.probe_laser_current)


class Mode(enum.IntEnum):
    DISABLED = 0
    CONTINUOUS_WAVE = 1
    PULSED = 2


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
    laser_voltage = QtCore.Signal(int, float)
    current_dac = QtCore.Signal(int, int)
    matrix_dac = QtCore.Signal(int, list)
    laser_data = QtCore.Signal(Buffer)
    laser_data_display = QtCore.Signal(hardware.laser.LaserData)
    current_probe_laser = QtCore.Signal(int, float)
    max_current_probe_laser = QtCore.Signal(float)
    probe_laser_mode = QtCore.Signal(int)
    settings = QtCore.Signal(pd.DataFrame)
    destination_folder_changed = QtCore.Signal(str)
    photo_gain = QtCore.Signal(int)

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
        self.interferometry.characterization.interferometry = self.interferometry.interferometer
        self.running = threading.Event()
        self._destination_folder = os.getcwd()
        self.save_raw_data = False

    def set_raw_data_saving(self) -> None:
        if self.save_raw_data:
            self.pti.decimation.save_raw_data = False
        else:
            self.pti.decimation.save_raw_data = True

    @property
    def destination_folder(self) -> str:
        return self._destination_folder

    @destination_folder.setter
    def destination_folder(self, folder: str) -> None:
        self.interferometry.characterization.destination_folder = folder
        self.pti.inversion.destination_folder = folder
        self._destination_folder = folder
        signals.destination_folder_changed.emit(folder)

    def live_calculation(self) -> tuple[threading.Thread, threading.Thread]:
        self.pti.inversion.init_header = True
        self.pti.decimation.init_header = True
        self.interferometry.characterization.init_online = True
        self.interferometry.interferometer.load_settings()
        self.running.set()

        def calculate_characterization():
            while self.running.is_set():
                self.interferometry.characterization()
                self.characterisation_buffer.append(
                    self.interferometry.characterization,
                    self.interferometry.interferometer)
                signals.characterization_live.emit(self.characterisation_buffer)

        def calculate_inversion():
            while self.running.is_set():
                self.pti.decimation.ref = np.array(DAQ.driver.ref_signal)
                self.pti.decimation.dc_coupled = np.array(DAQ.driver.dc_coupled)
                self.pti.decimation.ac_coupled = np.array(DAQ.driver.ac_coupled)
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
                self.pti_buffer.append(self.pti, self.interferometry.interferometer)
                signals.inversion_live.emit(self.pti_buffer)

        characterization_thread = threading.Thread(target=calculate_characterization)
        inversion_thread = threading.Thread(target=calculate_inversion)
        characterization_thread.start()
        inversion_thread.start()
        return characterization_thread, inversion_thread

    def calculate_characterisation(self, dc_file_path: str, use_settings=False, settings_path="") -> None:
        self.interferometry.interferometer.decimation_filepath = dc_file_path
        self.interferometry.interferometer.settings_path = settings_path
        self.interferometry.characterization.use_settings = use_settings
        self.interferometry.characterization(live=False)
        signals.settings.emit(self.interferometry.interferometer)

    def calculate_decimation(self, decimation_path: str) -> None:
        self.pti.decimation.file_path = decimation_path
        self.pti.decimation(live=False)

    def calculate_inversion(self, settings_path: str, inversion_path: str) -> None:
        self.interferometry.interferometer.decimation_filepath = inversion_path
        self.interferometry.interferometer.settings_path = settings_path
        self.interferometry.interferometer.load_settings()
        self.pti.inversion(live=False)


class DAQ:
    driver = hardware.daq.Driver()

    def __init__(self, daq_driver=None):
        if daq_driver is not None:
            self.driver = daq_driver
        else:
            self.driver = DAQ.driver


class ProbeLaserMode(enum.IntEnum):
    CONSTANT_LIGHT = 0
    CONSTANT_CURRENT = 1


class Laser:
    _buffer = LaserBuffer()
    driver = hardware.laser.Driver()

    def __init__(self, laser_buffer=None, laser_driver=None):
        if laser_buffer is not None:
            self.laser_buffer = laser_buffer
        else:
            self.laser_buffer = Laser._buffer
        if laser_driver is not None:
            self.driver = laser_driver
        else:
            self.driver = Laser.driver
        self.config_path = "hardware/configs/laser.json"
        self.load_configuration()

    def open(self) -> None:
        self.driver.open()
        self.driver.run()

    def load_configuration(self) -> None:
        with open(self.config_path) as config:
            loaded_config = json.load(config)
            self.driver.pump_laser = dacite.from_dict(hardware.laser.PumpLaser, loaded_config["Pump Laser"])
            self.driver.probe_laser = dacite.from_dict(hardware.laser.ProbeLaser, loaded_config["Probe Laser"])

    def save_configuration(self) -> None:
        with open(self.config_path, "w") as configuration:
            lasers = {"Pump Laser": dataclasses.asdict(self.driver.pump_laser),
                      "Probe Laser": dataclasses.asdict(self.driver.probe_laser)}
            configuration.write(json_parser.to_json(lasers) + "\n")

    def apply_configuration(self) -> None:
        self.driver.apply_configuration()

    @property
    def driver_bits(self) -> int:
        return self.driver.pump_laser.bit_value

    @driver_bits.setter
    def driver_bits(self, bits: int) -> None:
        # With increasing the slider decreases its value but the voltage should increase - hence we subtract the bits.
        self.driver.pump_laser.bit_value = hardware.laser.PumpLaser.NUMBER_OF_STEPS - bits
        voltage: float = hardware.laser.PumpLaser.bit_to_voltage(hardware.laser.PumpLaser.NUMBER_OF_STEPS - bits)
        signals.laser_voltage.emit(bits, voltage)
        self.driver.set_driver_voltage()

    @property
    def current_bits_dac_1(self) -> int:
        return self.driver.pump_laser.DAC_1.bit_value

    @current_bits_dac_1.setter
    def current_bits_dac_1(self, bits: int) -> None:
        self.driver.pump_laser.DAC_1.bit_value = bits
        signals.current_dac.emit(0, bits)
        self.driver.set_dac_1()

    @property
    def current_bits_dac_2(self) -> int:
        return self.driver.pump_laser.DAC_2.bit_value

    @current_bits_dac_2.setter
    def current_bits_dac_2(self, bits: int) -> None:
        self.driver.pump_laser.DAC_2.bit_value = bits
        signals.current_dac.emit(1, bits)
        self.driver.set_dac_2()

    @property
    def current_bits_probe_laser(self) -> int:
        return self.driver.probe_laser.current_bits

    @current_bits_probe_laser.setter
    def current_bits_probe_laser(self, bits: int) -> None:
        self.driver.probe_laser.current_bits = bits
        current: float = hardware.laser.ProbeLaser.bit_to_current(bits)
        signals.current_probe_laser.emit(hardware.laser.Driver.CURRENT_BITS - bits, current)
        self.driver.set_probe_laser_current()

    @property
    def photo_diode_gain(self) -> int:
        return self.driver.probe_laser.photo_diode_gain

    @photo_diode_gain.setter
    def photo_diode_gain(self, photo_diode_gain: int) -> None:
        self.driver.probe_laser.photo_diode_gain = photo_diode_gain
        signals.photo_gain.emit(photo_diode_gain - 1)
        self.driver.set_photo_gain()

    @property
    def probe_laser_max_current(self) -> float:
        return self.driver.probe_laser.max_current_mA

    @probe_laser_max_current.setter
    def probe_laser_max_current(self, current: float) -> None:
        if self.driver.probe_laser.max_current_mA != current:
            self.driver.probe_laser.max_current_mA = current

    @property
    def probe_laser_mode(self) -> ProbeLaserMode:
        if self.driver.probe_laser.constant_light:
            return ProbeLaserMode.CONSTANT_LIGHT
        else:
            return ProbeLaserMode.CONSTANT_CURRENT

    @probe_laser_mode.setter
    def probe_laser_mode(self, mode: ProbeLaserMode) -> None:
        match mode:
            case ProbeLaserMode.CONSTANT_CURRENT:
                self.driver.probe_laser.constant_current = True
                self.driver.probe_laser.constant_light = False
            case ProbeLaserMode.CONSTANT_LIGHT:
                self.driver.probe_laser.constant_current = False
                self.driver.probe_laser.constant_light = True
        self.driver.set_probe_laser_mode()
        signals.probe_laser_mode.emit(mode)

    @property
    def dac_1_matrix(self) -> hardware.laser.DAC:
        return self.driver.pump_laser.DAC_1

    @property
    def dac_2_matrix(self) -> hardware.laser.DAC:
        return self.driver.pump_laser.DAC_2

    @staticmethod
    def _set_indices(dac_number: int, dac: hardware.laser.DAC) -> None:
        indices: typing.Annotated[list[int], 3] = []
        for i in range(3):
            if dac.continuous_wave[i]:
                indices.append(Mode.CONTINUOUS_WAVE)
            elif dac.pulsed_mode[i]:
                indices.append(Mode.PULSED)
            else:
                indices.append(Mode.DISABLED)
        signals.matrix_dac.emit(dac_number, indices)

    @dac_1_matrix.setter
    def dac_1_matrix(self, dac: hardware.laser.DAC) -> None:
        self.driver.pump_laser.DAC_1 = dac
        Laser._set_indices(dac_number=0, dac=self.dac_1_matrix)

    @dac_2_matrix.setter
    def dac_2_matrix(self, dac: hardware.laser.DAC) -> None:
        self.driver.pump_laser.DAC_2 = dac
        Laser._set_indices(dac_number=1, dac=self.dac_2_matrix)

    def update_dac_mode(self, dac: hardware.laser.DAC, channel: int, mode: int) -> None:
        match mode:
            case Mode.CONTINUOUS_WAVE:
                dac.continuous_wave[channel] = True
                dac.pulsed_mode[channel] = False
            case Mode.PULSED:
                dac.continuous_wave[channel] = False
                dac.pulsed_mode[channel] = True
            case Mode.DISABLED:
                print("called")
                dac.continuous_wave[channel] = False
                dac.pulsed_mode[channel] = False
        self.driver.set_dac_matrix()

    def process_measured_data(self) -> None:
        def incoming_data():
            while self.driver.connected.is_set():
                received_data = self.driver.data.get(block=True)
                self.laser_buffer.append(received_data)
                signals.laser_data.emit(self.laser_buffer)
                signals.laser_data_display.emit(received_data)
        threading.Thread(target=incoming_data, daemon=True).start()


class Tec:
    driver = hardware.tec.Driver()


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


signals = Signals()
