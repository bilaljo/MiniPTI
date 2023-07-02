import abc
import copy
import csv
import enum
import itertools
import logging
import os
import platform
import subprocess
import threading
import time
import typing
from typing import Union
from collections import deque
from dataclasses import dataclass, asdict
from datetime import datetime


import numpy as np
import pandas as pd
from PyQt5 import QtCore
from scipy import ndimage

from .. import algorithm
from .. import hardware


class DestinationFolder:
    def __init__(self):
        self._destination_folder = os.getcwd()

    @property
    def folder(self) -> str:
        return self._destination_folder

    @folder.setter
    def folder(self, folder: str) -> None:
        self._destination_folder = folder
        signals.destination_folder_changed.emit(self._destination_folder)


class Table(QtCore.QAbstractTableModel):
    def __init__(self):
        QtCore.QAbstractTableModel.__init__(self)
        self._data = pd.DataFrame()

    @property
    @abc.abstractmethod
    def _headers(self) -> list[str]:
        ...

    @property
    @abc.abstractmethod
    def _indices(self) -> list[str]:
        ...

    def rowCount(self, parent=None) -> int:
        return self._data.shape[0]

    def columnCount(self, parent=None) -> int:
        return self._data.shape[1]

    def data(self, index, role: int = ...) -> Union[str, None]:
        if index.isValid():
            if role == QtCore.Qt.DisplayRole or role == QtCore.Qt.EditRole:
                value = self._data.iloc[index.row()][self._headers[index.column()]]
                return str(round(value, SettingsTable.SIGNIFICANT_VALUES))

    def flags(self, index):
        return QtCore.Qt.ItemIsSelectable | QtCore.Qt.ItemIsEnabled | QtCore.Qt.ItemIsEditable

    def setData(self, index, value, role: int = ...):
        if index.isValid():
            if role == QtCore.Qt.EditRole:
                self._data.iloc[index.row()][self._headers[index.column()]] = float(value)
                return True

    def headerData(self, section, orientation, role=QtCore.Qt.DisplayRole):
        if orientation == QtCore.Qt.Horizontal and role == QtCore.Qt.DisplayRole:
            return self._headers[section]
        elif orientation == QtCore.Qt.Vertical and role == QtCore.Qt.DisplayRole:
            return self._indices[section]
        return super().headerData(section, orientation, role)

    @property
    def table_data(self) -> pd.DataFrame:
        return self._data

    @table_data.setter
    def table_data(self, data) -> None:
        self._data = data


class SettingsTable(Table):
    SIGNIFICANT_VALUES = 4

    def __init__(self):
        Table.__init__(self)
        self._data = pd.DataFrame(columns=self._headers, index=self._indices)
        self.file_path = f"{os.path.dirname(os.path.dirname(__file__))}/algorithm/configs/settings.csv"
        signals.settings.connect(self.update_settings)
        self.load()

    @property
    def _headers(self) -> list[str]:
        return ["Detector 1", "Detector 2", "Detector 3"]

    @property
    def _indices(self) -> list[str]:
        return ["Amplitude [V]", "Offset [V]", "Output Phases [deg]", "Response Phases [rad]"]

    @QtCore.pyqtSlot(algorithm.interferometry.Interferometer)
    def update_settings(self, interferometer: algorithm.interferometry.Interferometer) -> None:
        self.update_settings_parameters(interferometer)

    def save(self) -> None:
        self._data.to_csv(self.file_path, index_label="Setting", index=True)

    def load(self) -> None:
        self.table_data = pd.read_csv(self.file_path, index_col="Setting")

    def update_settings_parameters(self, interferometer: algorithm.interferometry.Interferometer):
        self.table_data.loc["Output Phases [deg]"] = np.rad2deg(interferometer.output_phases)
        self.table_data.loc["Amplitude [V]"] = interferometer.amplitudes
        self.table_data.loc["Offset [V]"] = interferometer.offsets

    def update_settings_paths(self, interferometer: algorithm.interferometry.Interferometer,
                              inversion: algorithm.pti.Inversion) -> None:
        interferometer.settings_path = self.file_path
        inversion.settings_path = self.file_path
        interferometer.load_settings()
        inversion.load_response_phase()

    def setup_settings_file(self) -> None:
        # If no settings found, a new empty file is created filled with NaN.
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


class RawDataTable(Table):
    class Direction(typing.NamedTuple):
        DOWNWARDS = algorithm.pti.Iterator.REVERSE
        UPWARDS = algorithm.pti.Iterator.FORWARD

    def __init__(self):
        Table.__init__(self)
        res = {}
        for i in ["DC CH1", "DC CH2", "DC CH3", "AC CH1", "AC CH2", "AC CH3"]:
            res[i] = [np.nan for _ in range(100000)]
        self._data = pd.DataFrame(res)
        self.raw_data_buffer = RawDataBuffer()
        self.decimation = algorithm.pti.Decimation()
        self.get_raw_data = self.decimation.get_raw_data()
        self.counter = 0

    @property
    def _indices(self):
        return self._data.index

    @property
    def _headers(self) -> list[str]:
        return ["DC CH1", "DC CH2", "DC CH3", "AC CH1", "AC CH2", "AC CH3"]

    def update_table(self, direction: Direction) -> None:
        if self.raw_data_buffer.is_empty:
            return  # Nothing to do
        self.counter += 1
        if self.counter == 8000:
            self.get_raw_data.send(direction)
            self.raw_data_buffer.append(next(self.get_raw_data))
            self.counter = 0
        if direction == algorithm.pti.Iterator.FORWARD:
            self.raw_data_buffer.popleft()
        else:
            self.raw_data_buffer.pop()
        data = {}
        for i in range(1, 4):
            data[f"DC CH{i}"] = self.raw_data_buffer.dc_buffer
            data[f"AC CH{i}"] = self.raw_data_buffer.ac_buffer
        self._data = pd.DataFrame(data, columns=self._headers)


class Logging(logging.Handler):
    LOGGING_HISTORY = 50

    def __init__(self):
        logging.Handler.__init__(self)
        self.logging_messages = deque(maxlen=Logging.LOGGING_HISTORY)
        self.formatter = logging.Formatter("[%(threadName)s] %(levelname)s %(asctime)s: %(message)s",
                                           datefmt="%Y-%m-%d %H:%M:%S")
        logging.getLogger().addHandler(self)
        root_logger = logging.getLogger()
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(self.formatter)
        root_logger.addHandler(console_handler)

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


def find_delimiter(file_path: str) -> typing.Union[str, None]:
    delimiter_sniffer = csv.Sniffer()
    if not file_path:
        return
    with open(file_path, "r") as file:
        delimiter = str(delimiter_sniffer.sniff(file.readline()).delimiter)
    return delimiter


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

    def __setitem__(self, key, value) -> None:
        setattr(self, key.casefold().replace(" ", "_"), value)

    def __iter__(self):
        for member in dir(self):
            if not callable(getattr(self, member)) and not member.startswith("__") and member != "time_counter":
                yield getattr(self, member)

    @property
    @abc.abstractmethod
    def is_empty(self) -> bool:
        ...

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
    decimation: algorithm.pti.Decimation
    inversion: algorithm.pti.Inversion


class Interferometry(typing.NamedTuple):
    interferometer: algorithm.interferometry.Interferometer
    characterization: algorithm.interferometry.Characterization


class PTIBuffer(Buffer):
    MEAN_SIZE = 60
    CHANNELS = 3

    def __init__(self):
        Buffer.__init__(self)
        self._dc_values = [deque(maxlen=Buffer.QUEUE_SIZE) for _ in range(PTIBuffer.CHANNELS)]
        self._interferometric_phase = deque(maxlen=Buffer.QUEUE_SIZE)
        self._sensitivity = [deque(maxlen=Buffer.QUEUE_SIZE) for _ in range(PTIBuffer.CHANNELS)]
        self._pti_signal = deque(maxlen=Buffer.QUEUE_SIZE)
        self._pti_signal_mean = deque(maxlen=Buffer.QUEUE_SIZE)
        self._pti_signal_mean_queue = deque(maxlen=PTIBuffer.MEAN_SIZE)

    @property
    def is_empty(self) -> bool:
        return len(self._pti_signal) == 0

    def append(self, pti_data: PTI, interferometer: algorithm.interferometry.Interferometer) -> None:
        for i in range(3):
            self._dc_values[i].append(pti_data.decimation.dc_signals[i])
            self.sensitivity[i].append(pti_data.inversion.sensitivity[i])
        self._interferometric_phase.append(interferometer.phase)
        self._pti_signal.append(pti_data.inversion.pti_signal)
        self._pti_signal_mean_queue.append(pti_data.inversion.pti_signal)
        self._pti_signal_mean.append(np.mean(self._pti_signal_mean_queue))
        self.time.append(next(self.time_counter))

    @property
    def dc_values(self) -> list[deque]:
        return self._dc_values

    @property
    def interferometric_phase(self) -> deque:
        return self._interferometric_phase

    @property
    def sensitivity(self) -> list[deque]:
        return self._sensitivity

    @property
    def pti_signal(self) -> deque:
        return self._pti_signal

    @property
    def pti_signal_mean(self) -> deque:
        return self._pti_signal_mean


class CharacterisationBuffer(Buffer):
    CHANNELS = 3

    def __init__(self):
        Buffer.__init__(self)
        # The first channel has always the phase 0 by definition hence it is not needed.
        self._output_phases = [deque(maxlen=Buffer.QUEUE_SIZE) for _ in range(self.CHANNELS - 1)]
        self._amplitudes = [deque(maxlen=Buffer.QUEUE_SIZE) for _ in range(CharacterisationBuffer.CHANNELS)]
        self._symmetry = deque(maxlen=Buffer.QUEUE_SIZE)
        self._relative_symmetry = deque(maxlen=Buffer.QUEUE_SIZE)

    @property
    def is_empty(self) -> bool:
        return len(self._output_phases) == 0

    def append(self, characterization: algorithm.interferometry.Characterization,
               interferometer: algorithm.interferometry.Interferometer) -> None:
        for i in range(3):
            self._amplitudes[i].append(interferometer.amplitudes[i])
        for i in range(2):
            self._output_phases[i].append(interferometer.output_phases[i + 1])
        self.symmetry.append(interferometer.absolute_symmetry)
        self.relative_symmetry.append(interferometer.relative_symmetry)
        self.time.append(characterization.time_stamp)

    @property
    def output_phases(self) -> list[deque]:
        return self._output_phases

    @property
    def amplitudes(self) -> list[deque]:
        return self._amplitudes

    @property
    def symmetry(self) -> deque:
        return self._symmetry

    @property
    def relative_symmetry(self) -> deque:
        return self._relative_symmetry


class LaserBuffer(Buffer):
    def __init__(self):
        Buffer.__init__(self)
        self._pump_laser_voltage = deque(maxlen=Buffer.QUEUE_SIZE)
        self._pump_laser_current = deque(maxlen=Buffer.QUEUE_SIZE)
        self._probe_laser_current = deque(maxlen=Buffer.QUEUE_SIZE)

    @property
    def is_empty(self) -> bool:
        return len(self._pump_laser_voltage) == 0

    def append(self, laser_data: hardware.laser.Data) -> None:
        self.time.append(next(self.time_counter) / 10)
        self._pump_laser_voltage.append(laser_data.high_power_laser_voltage)
        self.pump_laser_current.append(laser_data.high_power_laser_current)
        self.probe_laser_current.append(laser_data.low_power_laser_current)

    @property
    def pump_laser_voltage(self) -> deque:
        return self._pump_laser_voltage

    @property
    def pump_laser_current(self) -> deque:
        return self._pump_laser_current

    @property
    def probe_laser_current(self) -> deque:
        return self._probe_laser_current


class TecBuffer(Buffer):
    def __init__(self):
        Buffer.__init__(self)
        self._set_point: list[deque] = [deque(maxlen=Buffer.QUEUE_SIZE), deque(maxlen=Buffer.QUEUE_SIZE)]
        self._actual_value: list[deque] = [deque(maxlen=Buffer.QUEUE_SIZE), deque(maxlen=Buffer.QUEUE_SIZE)]

    @property
    def is_empty(self) -> bool:
        return len(self._set_point[0]) == 0

    def append(self, tec_data: hardware.tec.Data) -> None:
        self._set_point[Tec.PUMP_LASER].append(tec_data.set_point[Tec.PUMP_LASER])
        self._set_point[Tec.PROBE_LASER].append(tec_data.set_point[Tec.PROBE_LASER])
        self._actual_value[Tec.PUMP_LASER].append(tec_data.actual_temperature[Tec.PUMP_LASER])
        self._actual_value[Tec.PROBE_LASER].append(tec_data.actual_temperature[Tec.PROBE_LASER])
        self.time.append(next(self.time_counter))

    @property
    def set_point(self) -> list[deque]:
        return self._set_point

    @property
    def actual_value(self) -> list[deque]:
        return self._actual_value


class RawDataBuffer(Buffer):
    QUEUE_SIZE = 8000 * 3

    def __init__(self):
        Buffer.__init__(self)
        self._dc_buffer = deque(maxlen=Buffer.QUEUE_SIZE)
        self._ac_buffer = deque(maxlen=Buffer.QUEUE_SIZE)

    @property
    def is_empty(self) -> bool:
        return len(self._dc_buffer) == 0

    def append(self, raw_data: algorithm.pti.RawData) -> None:
        dc, ac = raw_data
        self._dc_buffer.extend(dc)
        self._ac_buffer.extend(ac)

    def popleft(self) -> None:
        self._dc_buffer.popleft()
        self._ac_buffer.popleft()

    def pop(self) -> None:
        self._dc_buffer.pop()
        self._ac_buffer.pop()

    @property
    def dc_buffer(self) -> deque:
        return self._dc_buffer

    @property
    def ac_buffer(self) -> deque:
        return self._ac_buffer


class Mode(enum.IntEnum):
    DISABLED = 0
    CONTINUOUS_WAVE = 1
    PULSED = 2


@dataclass
class Battery:
    percentage: int
    minutes_left: int


@dataclass(init=False, frozen=True)
class Signals(QtCore.QObject):
    raw_data = QtCore.pyqtSignal(algorithm.pti.RawData)
    decimation = QtCore.pyqtSignal(pd.DataFrame)
    decimation_live = QtCore.pyqtSignal(Buffer)
    inversion = QtCore.pyqtSignal(pd.DataFrame)
    inversion_live = QtCore.pyqtSignal(Buffer)
    characterization = QtCore.pyqtSignal(pd.DataFrame)
    characterization_live = QtCore.pyqtSignal(Buffer)
    settings_pti = QtCore.pyqtSignal()
    logging_update = QtCore.pyqtSignal(deque)
    daq_running = QtCore.pyqtSignal(bool)
    settings = QtCore.pyqtSignal(algorithm.interferometry.Interferometer)
    destination_folder_changed = QtCore.pyqtSignal(str)
    battery_state = QtCore.pyqtSignal(Battery)
    valve_change = QtCore.pyqtSignal(hardware.motherboard.Valve)
    bypass = QtCore.pyqtSignal(bool)
    tec_data = QtCore.pyqtSignal(Buffer)
    tec_data_display = QtCore.pyqtSignal(hardware.tec.Data)
    clear_daq = QtCore.pyqtSignal()

    def __init__(self):
        QtCore.QObject.__init__(self)


@dataclass
class LaserSignals(QtCore.QObject):
    photo_gain = QtCore.pyqtSignal(int)
    current_probe_laser = QtCore.pyqtSignal(int, float)
    max_current_probe_laser = QtCore.pyqtSignal(float)
    probe_laser_mode = QtCore.pyqtSignal(int)
    laser_voltage = QtCore.pyqtSignal(int, float)
    current_dac = QtCore.pyqtSignal(int, int)
    matrix_dac = QtCore.pyqtSignal(int, list)
    data = QtCore.pyqtSignal(Buffer)
    data_display = QtCore.pyqtSignal(hardware.laser.Data)
    pump_laser_enabled = QtCore.pyqtSignal(bool)
    probe_laser_enabled = QtCore.pyqtSignal(bool)
    clear_pumplaser = QtCore.pyqtSignal()
    clear_probelaser = QtCore.pyqtSignal()

    def __init__(self):
        QtCore.QObject.__init__(self)


class TecMode(enum.IntEnum):
    COOLING = 0
    HEATING = 1


@dataclass(init=False, frozen=True)
class TecSignals(QtCore.QObject):
    mode = QtCore.pyqtSignal(TecMode)
    p_value = QtCore.pyqtSignal(int)
    d_value = QtCore.pyqtSignal(int)
    i_1_value = QtCore.pyqtSignal(int)
    i_2_value = QtCore.pyqtSignal(int)
    setpoint_temperature = QtCore.pyqtSignal(float)
    loop_time = QtCore.pyqtSignal(int)
    reference_resistor = QtCore.pyqtSignal(float)
    max_power = QtCore.pyqtSignal(int)
    enabled = QtCore.pyqtSignal(bool)
    clear_plots = QtCore.pyqtSignal()
    use_ntc = QtCore.pyqtSignal(bool)

    def __init__(self):
        QtCore.QObject.__init__(self)


def shutdown_procedure() -> None:
    Laser.driver.close()
    Tec.driver.close()
    time.sleep(0.5)  # Give the calculations threads time to finish their write operation
    Motherboard.shutdown()
    if platform.system() == "Windows":
        subprocess.run(r"shutdown /s /t 1", shell=True)
    else:
        subprocess.run("sleep 0.5s && poweroff", shell=True)


class Calculation:
    def __init__(self):
        self.settings_path = ""
        self.interferometry = Interferometry(algorithm.interferometry.Interferometer(),
                                             algorithm.interferometry.Characterization())
        self.interferometry.characterization.interferometer = self.interferometry.interferometer
        self.pti = PTI(algorithm.pti.Decimation(),
                       algorithm.pti.Inversion(interferometer=self.interferometry.interferometer))
        self._destination_folder = os.getcwd()
        signals.destination_folder_changed.connect(self._update_destination_folder)

    def _update_destination_folder(self, folder: str) -> None:
        self.interferometry.characterization.destination_folder = folder
        self.pti.inversion.destination_folder = folder
        self.pti.decimation.destination_folder = folder
        self._destination_folder = folder


class LiveCalculation(Calculation):
    MEAN_INTERVAL = 60
    QUEUE_SIZE = 1000
    ONE_MINUTE = 60  # s

    def __init__(self):
        Calculation.__init__(self)
        self.current_time = 0
        self.save_raw_data = False
        self.dc_signals = []
        self.pti_buffer = PTIBuffer()
        self.characterisation_buffer = CharacterisationBuffer()
        self.pti_signal_mean_queue = deque(maxlen=LiveCalculation.ONE_MINUTE)
        signals.clear_daq.connect(self.clear_buffer)

    def process_daq_data(self) -> None:
        threading.Thread(target=self._run_pti_inversion, daemon=True).start()
        threading.Thread(target=self._characterisation, daemon=True).start()

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

    def clear_buffer(self) -> None:
        self.pti_buffer = PTIBuffer()
        self.characterisation_buffer = CharacterisationBuffer()

    def set_raw_data_saving(self) -> None:
        if self.save_raw_data:
            self.pti.decimation.save_raw_data = False
        else:
            self.pti.decimation.save_raw_data = True

    def _run_pti_inversion(self):
        while Motherboard.driver.running.is_set():
            self._decimation()
            self._pti_inversion()

    def _run_characterization(self) -> None:
        while Motherboard.driver.running.is_set():
            self.interferometry.characterization.characterise(live=True)
            self.characterisation_buffer.append(self.interferometry.characterization,
                                                self.interferometry.interferometer)
            signals.characterization_live.emit(self.characterisation_buffer)

    def _init_calculation(self) -> None:
        self.pti.inversion.init_header = True
        self.pti.decimation.init_header = True
        self.interferometry.characterization.init_online = True
        self.interferometry.interferometer.load_settings()

    def _decimation(self) -> None:
        self.pti.decimation.ref = np.array(Motherboard.driver.ref_signal)
        self.pti.decimation.dc_coupled = np.array(Motherboard.driver.dc_coupled)
        self.pti.decimation.ac_coupled = np.array(Motherboard.driver.ac_coupled)
        self.pti.decimation.decimate(live=True)
        signals.decimation_live.emit(self.pti_buffer)

    def _pti_inversion(self) -> None:
        self.pti.inversion.lock_in = self.pti.decimation.lock_in
        self.pti.inversion.dc_signals = self.pti.decimation.dc_signals
        self.pti.inversion.invert(live=True)
        self.pti_buffer.append(self.pti, self.interferometry.interferometer)
        signals.inversion_live.emit(self.pti_buffer)

    def _characterisation(self) -> None:
        self.interferometry.characterization.add_phase(self.interferometry.interferometer.phase)
        self.dc_signals.append(copy.deepcopy(self.pti.decimation.dc_signals))
        if self.interferometry.characterization.enough_values:
            self.interferometry.characterization._signals = copy.deepcopy(self.dc_signals)
            self.interferometry.characterization.phases = copy.deepcopy(
                self.interferometry.characterization.tracking_phase)
            self.interferometry.characterization.event.set()
            self.dc_signals = []


class OfflineCalculation(Calculation):
    def __init__(self):
        Calculation.__init__(self)

    def calculate_characterisation(self, dc_file_path: str, use_settings=False, settings_path="") -> None:
        self.interferometry.interferometer.decimation_filepath = dc_file_path
        self.interferometry.interferometer.settings_path = settings_path
        self.interferometry.characterization.use_configuration = use_settings
        self.interferometry.characterization.characterise()
        signals.settings.emit(self.interferometry.interferometer)

    def calculate_decimation(self, decimation_path: str) -> None:
        self.pti.decimation.file_path = decimation_path
        self.pti.decimation.decimate()

    def calculate_inversion(self, settings_path: str, inversion_path: str) -> None:
        self.interferometry.interferometer.decimation_filepath = inversion_path
        self.interferometry.interferometer.settings_path = settings_path
        self.interferometry.interferometer.load_settings()
        self.pti.inversion.invert()


class ProbeLaserMode(enum.IntEnum):
    CONSTANT_LIGHT = 0
    CONSTANT_CURRENT = 1


class Serial:
    """
    This class is a base class for subclasses of the driver objects from driver/serial.
    """

    driver = hardware.serial_device.Driver()

    def __init__(self):
        signals.destination_folder_changed.connect(self._update_file_path)
        self._destination_folder = os.getcwd()
        self._init_headers = True
        self._running = False
        signals.daq_running.connect(self._daq_running_changed)

    def _daq_running_changed(self, running) -> None:
        self._running = running

    # @QtCore.pyqtSlot(str)
    def _update_file_path(self, destination_folder: str) -> None:
        self._destination_folder = destination_folder
        self._init_headers = True

    @classmethod
    def find_port(cls) -> None:
        cls.driver.find_port()

    @classmethod
    def open(cls) -> None:
        """
        Connects to a serial device and listens to incoming data.
        """
        cls.driver.open()

    @classmethod
    def run(cls) -> None:
        cls.driver.run()

    @classmethod
    def close(cls) -> None:
        """
        Disconnects to a serial device and stops listening to data
        """
        cls.driver.close()

    @classmethod
    @abc.abstractmethod
    def save_configuration(cls) -> None:
        ...

    @abc.abstractmethod
    def fire_configuration_change(self) -> None:
        """
        By initiation of a Serial Object (on which the laser model relies) the configuration is
        already set and do not fire events to update the GUI. This function is hence only called
        once to manually activate the firing.
        """

    @abc.abstractmethod
    def load_configuration(self) -> None:
        self.fire_configuration_change()

    def _incoming_data(self) -> None:
        """
        Listens to incoming data and emits them as _signals to the view as long a serial connection
        is established.
        """

    def process_measured_data(self) -> threading.Thread:
        processing_thread = threading.Thread(target=self._incoming_data, daemon=True)
        processing_thread.start()
        return processing_thread


class Motherboard(Serial):
    driver = hardware.motherboard.Driver()

    def __init__(self):
        Serial.__init__(self)
        self.bms_data: tuple[float, float] = (0, 0)
        self.driver.load_config()

    @property
    def connected(self) -> bool:
        return self.driver.connected.is_set()

    @staticmethod
    def centi_kelvin_to_celsius(temperature: float) -> float:
        return round((temperature - 273.15) / 100, 2)

    def _incoming_data(self) -> None:
        while self.driver.connected.is_set():
            bms_data = Motherboard.driver.bms
            bms_data.battery_temperature = Motherboard.centi_kelvin_to_celsius(bms_data.battery_temperature)
            signals.battery_state.emit(Battery(bms_data.battery_percentage, bms_data.minutes_left))
            if self.running:
                if self._init_headers:
                    units = {"Time": "H:M:S", "External DC Power": "bool",
                             "Charging Battery": "bool",
                             "Minutes Left": "min", "Charging Level": "%", "Temperature": "°C", "Current": "mA",
                             "Voltage": "V", "Full Charge Capacity": "mAh", "Remaining Charge Capacity": "mAh"}
                    pd.DataFrame(units, index=["Y:M:D"]).to_csv(self._destination_folder + "/BMS.csv",
                                                                index_label="Date")
                    self.init_header = False
                now = datetime.now()
                output_data = {"Time": str(now.strftime("%H:%M:%S"))}
                for key, value in asdict(bms_data).items():
                    output_data[key.replace("_", " ").title()] = value
                bms_data_frame = pd.DataFrame(output_data, index=[str(now.strftime("%Y-%m-%d"))])
                bms_data_frame.to_csv(self._destination_folder + "/BMS.csv", header=False, mode="a")

    @property
    def running(self) -> bool:
        return self._running

    @running.setter
    def running(self, running):
        self._running = running
        if running:
            # Before we start a new run, we clear all old data
            self.driver.reset()
            signals.clear_daq.emit()
            self.driver.running.set()
            signals.daq_running.emit(True)

        else:
            self.driver.running.clear()
            signals.daq_running.emit(False)

    @property
    def shutdown_event(self) -> threading.Event:
        return self.driver.shutdown

    @property
    def valve_period(self) -> int:
        return self.driver.config.valve.period

    @valve_period.setter
    def valve_period(self, period: int) -> None:
        if period < 0:
            raise ValueError("Invalid value for period")
        self.driver.config.valve.period = period

    @property
    def valve_duty_cycle(self) -> int:
        return self.driver.config.valve.duty_cycle

    @valve_duty_cycle.setter
    def valve_duty_cycle(self, duty_cycle: int) -> None:
        if not 0 < self.driver.config.valve.duty_cycle < 100:
            raise ValueError("Invalid value for duty cycle")
        self.driver.config.valve.duty_cycle = duty_cycle

    @property
    def automatic_valve_switch(self) -> bool:
        return self.driver.config.valve.automatic_switch

    @automatic_valve_switch.setter
    def automatic_valve_switch(self, automatic_switch: bool) -> None:
        self.driver.config.valve.automatic_switch = automatic_switch
        if automatic_switch:
            self.driver.automatic_switch.set()
            self.driver.automatic_valve_change()
        else:
            self.driver.automatic_switch.clear()

    @property
    def bypass(self) -> bool:
        return self.driver.bypass

    @bypass.setter
    def bypass(self, state: bool) -> None:
        self.driver.bypass = state
        signals.bypass.emit(state)

    @staticmethod
    def shutdown() -> None:
        Motherboard.driver.do_shutdown()

    def load_configuration(self) -> None:
        Motherboard.driver.load_config()
        self.fire_configuration_change()

    @classmethod
    def save_configuration(cls) -> None:
        cls.driver.save_config()

    @property
    def config_path(self) -> str:
        return self.driver.config_path

    @config_path.setter
    def config_path(self, config_path: str) -> None:
        if not os.path.exists(config_path):
            raise ValueError("File does not exist")
        self.driver.config_path = config_path

    def fire_configuration_change(self) -> None:
        signals.valve_change.emit(Motherboard.driver.config.valve)


class Laser(Serial):
    buffer = LaserBuffer()
    driver = hardware.laser.Driver()

    def __init__(self):
        Serial.__init__(self)
        self._config_path = "hardware/configs/laser.json"

    @property
    @abc.abstractmethod
    def config_path(self) -> str:
        ...

    @config_path.setter
    @abc.abstractmethod
    def config_path(self, config_path: str) -> None:
        ...

    @property
    @abc.abstractmethod
    def enabled(self) -> bool:
        ...

    @enabled.setter
    @abc.abstractmethod
    def enabled(self, enabled: bool) -> None:
        ...

    @abc.abstractmethod
    def load_configuration(self) -> None:
        ...

    @abc.abstractmethod
    def save_configuration(self) -> None:
        ...

    @abc.abstractmethod
    def apply_configuration(self) -> None:
        ...

    def _incoming_data(self):
        while self.driver.connected.is_set():
            if self._running:
                if self._init_headers:
                    units = {"Time": "H:M:S",
                             "Pump Laser Enabled": "bool",
                             "Pump Laser Voltage": "V",
                             "Probe Laser Enabled": "bool",
                             "Pump Laser Current": "mA",
                             "Probe Laser Current": "mA"}
                    pd.DataFrame(units, index=["Y:M:D"]).to_csv(self._destination_folder + "/laser.csv",
                                                                index_label="Date")
                    self._init_headers = False
            received_data: hardware.laser.Data = self.driver.data.get(block=True)
            Laser.buffer.append(received_data)
            laser_signals.data.emit(Laser.buffer)
            laser_signals.data_display.emit(received_data)
            if self._running:
                now = datetime.now()
                output_data = {"Time": str(now.strftime("%H:%M:%S")),
                               "Pump Laser Enabled": received_data.high_power_laser_enabled,
                               "Pump Laser Voltage": received_data.high_power_laser_voltage,
                               "Probe Laser Enabled": received_data.low_power_laser_enabled,
                               "Pump Laser Current": received_data.high_power_laser_current,
                               "Probe Laser Current": received_data.low_power_laser_current}
                laser_data_frame = pd.DataFrame(output_data, index=[str(now.strftime("%Y-%m-%d"))])
                pd.DataFrame(laser_data_frame).to_csv(f"{self._destination_folder}/laser.csv", mode="a", header=False)

    def fire_configuration_change(self) -> None:
        ...


class PumpLaser(Laser):
    def __init__(self):
        Laser.__init__(self)
        self.pump_laser = self.driver.high_power_laser

    @property
    def connected(self) -> bool:
        return self.driver.connected.is_set()

    @property
    def driver_bits(self) -> int:
        return self.pump_laser.configuration.bit_value

    @driver_bits.setter
    def driver_bits(self, bits: int) -> None:
        # With increasing the slider decreases its value but the voltage should increase, hence we subtract the bits.
        self.pump_laser.configuration.bit_value = hardware.laser.HighPowerLaserConfig.NUMBER_OF_STEPS - bits
        self.fire_driver_bits_signal()
        self.pump_laser.set_voltage()

    @property
    def config_path(self) -> str:
        return self.pump_laser.config_path

    @config_path.setter
    @abc.abstractmethod
    def config_path(self, config_path: str) -> None:
        self.pump_laser.config_path = config_path

    def save_configuration(self) -> None:
        self.pump_laser.save_configuration()

    def load_configuration(self) -> None:
        self.pump_laser.load_configuration()

    def apply_configuration(self) -> None:
        self.pump_laser.apply_configuration()

    def fire_driver_bits_signal(self) -> None:
        bits: int = self.pump_laser.configuration.bit_value
        voltage: float = hardware.laser.HighPowerLaserConfig.bit_to_voltage(bits)
        bits = hardware.laser.HighPowerLaserConfig.NUMBER_OF_STEPS - bits
        laser_signals.laser_voltage.emit(bits, voltage)

    @property
    def enabled(self) -> bool:
        return self.pump_laser.enabled

    @enabled.setter
    def enabled(self, enable: bool):
        if enable:
            laser_signals.clear_pumplaser.emit()
        self.pump_laser.enabled = enable
        laser_signals.pump_laser_enabled.emit(enable)

    @property
    def current_bits_dac_1(self) -> int:
        return self.pump_laser.configuration.DAC[0].bit_value

    @current_bits_dac_1.setter
    def current_bits_dac_1(self, bits: int) -> None:
        self.pump_laser.configuration.DAC[0].bit_value = bits
        self.fire_current_bits_dac_1()
        self.pump_laser.set_dac(0)

    def fire_current_bits_dac_1(self) -> None:
        laser_signals.current_dac.emit(0, self.pump_laser.configuration.DAC[0].bit_value)

    @property
    def current_bits_dac_2(self) -> int:
        return self.pump_laser.configuration.DAC[1].bit_value

    @current_bits_dac_2.setter
    def current_bits_dac_2(self, bits: int) -> None:
        self.pump_laser.configuration.DAC[1].bit_value = bits
        self.fire_current_bits_dac2()
        self.pump_laser.set_dac(1)

    def fire_current_bits_dac2(self) -> None:
        laser_signals.current_dac.emit(1, self.pump_laser.configuration.DAC[1].bit_value)

    @property
    def dac_1_matrix(self) -> hardware.laser.DAC:
        return self.pump_laser.configuration.DAC[0]

    @property
    def dac_2_matrix(self) -> hardware.laser.DAC:
        return self.pump_laser.configuration.DAC[1]

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
        laser_signals.matrix_dac.emit(dac_number, indices)

    @dac_1_matrix.setter
    def dac_1_matrix(self, dac: hardware.laser.DAC) -> None:
        self.pump_laser.configuration.DAC[0] = dac
        self.fire_dac_matrix_1()

    def fire_dac_matrix_1(self) -> None:
        PumpLaser._set_indices(dac_number=0, dac=self.dac_1_matrix)

    @dac_2_matrix.setter
    def dac_2_matrix(self, dac: hardware.laser.DAC) -> None:
        self.pump_laser.configuration.DAC[1] = dac
        self.fire_dac_matrix_2()

    def fire_dac_matrix_2(self) -> None:
        PumpLaser._set_indices(dac_number=1, dac=self.dac_2_matrix)

    def update_dac_mode(self, dac: hardware.laser.DAC, channel: int, mode: int) -> None:
        if mode == Mode.CONTINUOUS_WAVE:
            dac.continuous_wave[channel] = True
            dac.pulsed_mode[channel] = False
        elif mode == Mode.PULSED:
            dac.continuous_wave[channel] = False
            dac.pulsed_mode[channel] = True
        elif mode == Mode.DISABLED:
            dac.continuous_wave[channel] = False
            dac.pulsed_mode[channel] = False
        self.pump_laser.set_dac_matrix()

    def fire_configuration_change(self) -> None:
        self.fire_driver_bits_signal()
        self.fire_current_bits_dac_1()
        self.fire_current_bits_dac2()
        self.fire_dac_matrix_1()
        self.fire_dac_matrix_2()


class ProbeLaser(Laser):
    def __init__(self):
        Laser.__init__(self)
        self.probe_laser = self.driver.low_power_laser

    @property
    def connected(self) -> bool:
        return self.driver.connected.is_set()

    @property
    def current_bits_probe_laser(self) -> int:
        return self.probe_laser.configuration.current.bits

    @current_bits_probe_laser.setter
    def current_bits_probe_laser(self, bits: int) -> None:
        self.probe_laser.configuration.current.bits = bits
        self.probe_laser.set_current()
        bit, current = self.fire_current_bits_signal()
        laser_signals.current_probe_laser.emit(hardware.laser.LowPowerLaser.CURRENT_BITS - bits, current)

    @property
    def config_path(self) -> str:
        return self.probe_laser.config_path

    @config_path.setter
    @abc.abstractmethod
    def config_path(self, config_path: str) -> None:
        self.probe_laser.config_path = config_path

    def save_configuration(self) -> None:
        self.probe_laser.save_configuration()

    def load_configuration(self) -> None:
        self.probe_laser.load_configuration()

    def fire_current_bits_signal(self) -> tuple[int, float]:
        bits: int = self.probe_laser.configuration.current.bits
        current: float = hardware.laser.LowPowerLaserConfig.bit_to_current(bits)
        laser_signals.current_probe_laser.emit(hardware.laser.LowPowerLaser.CURRENT_BITS - bits, current)
        return bits, current

    @property
    def enabled(self) -> bool:
        return self.probe_laser.enabled

    @enabled.setter
    def enabled(self, enable: bool) -> None:
        if enable:
            laser_signals.clear_probelaser.emit()
        self.probe_laser.enabled = enable
        laser_signals.probe_laser_enabled.emit(enable)

    @property
    def photo_diode_gain(self) -> int:
        return self.probe_laser.configuration.photo_diode_gain

    @photo_diode_gain.setter
    def photo_diode_gain(self, photo_diode_gain: int) -> None:
        self.probe_laser.configuration.photo_diode_gain = photo_diode_gain
        self.fire_photo_diode_gain_signal()
        self.probe_laser.set_photo_diode_gain()

    def fire_photo_diode_gain_signal(self) -> None:
        laser_signals.photo_gain.emit(self.probe_laser.configuration.photo_diode_gain - 1)

    @property
    def probe_laser_max_current(self) -> float:
        return self.probe_laser.configuration.current.max_mA

    @probe_laser_max_current.setter
    def probe_laser_max_current(self, current: float) -> None:
        if self.probe_laser.configuration.current.max_mA != current:
            self.probe_laser.configuration.current.max_mA = current
            self.fire_max_current_signal()

    def fire_max_current_signal(self) -> None:
        laser_signals.max_current_probe_laser.emit(self.probe_laser.configuration.current.max_mA)

    @property
    def probe_laser_mode(self) -> ProbeLaserMode:
        if self.probe_laser.configuration.mode.constant_light:
            return ProbeLaserMode.CONSTANT_LIGHT
        else:
            return ProbeLaserMode.CONSTANT_CURRENT

    @probe_laser_mode.setter
    def probe_laser_mode(self, mode: ProbeLaserMode) -> None:
        if mode == ProbeLaserMode.CONSTANT_CURRENT:
            self.driver.low_power_laser.configuration.mode.constant_current = True
            self.driver.low_power_laser.configuration.mode.constant_light = False
        elif mode == ProbeLaserMode.CONSTANT_LIGHT:
            self.driver.low_power_laser.configuration.mode.constant_current = False
            self.driver.low_power_laser.configuration.mode.constant_light = True
        self.probe_laser.set_mode()
        self.fire_laser_mode_signal()

    def fire_laser_mode_signal(self) -> None:
        if self.probe_laser.configuration.mode.constant_light:
            laser_signals.probe_laser_mode.emit(ProbeLaserMode.CONSTANT_LIGHT)
        else:
            laser_signals.probe_laser_mode.emit(ProbeLaserMode.CONSTANT_CURRENT)

    def fire_configuration_change(self) -> None:
        self.fire_current_bits_signal()
        self.fire_laser_mode_signal()
        self.fire_photo_diode_gain_signal()
        self.fire_max_current_signal()

    def apply_configuration(self) -> None:
        self.probe_laser.apply_configuration()


class Tec(Serial):
    PUMP_LASER = 0
    PROBE_LASER = 1

    driver = hardware.tec.Driver()
    _buffer = TecBuffer()

    def __init__(self, channel: int):
        Serial.__init__(self)
        self.tec = self.driver.tec[channel]
        self.tec_signals = tec_signals[channel]

    @property
    def connected(self) -> bool:
        return self.driver.connected.is_set()

    @property
    def enabled(self) -> bool:
        return self.tec.enabled

    @enabled.setter
    def enabled(self, enable) -> None:
        if enable:
            self.tec_signals.clear_plots.emit()
        self.tec.enabled = enable
        self.tec_signals.enabled.emit(enable)

    @property
    def config_path(self) -> str:
        return self.tec.config_path

    @config_path.setter
    def config_path(self, config_path: str) -> None:
        self.tec.config_path = config_path

    def save_configuration(self) -> None:
        self.tec.save_configuration()

    def load_configuration(self) -> None:
        self.tec.load_configuration()
        self.fire_configuration_change()

    def apply_configuration(self) -> None:
        self.tec.apply_configuration()

    @property
    def p_value(self) -> float:
        return self.tec.configuration.pid.proportional_value

    @p_value.setter
    def p_value(self, p_value: float) -> None:
        self.tec.configuration.pid.proportional_value = p_value
        self.tec.set_pid_p_value()

    @property
    def i_1_value(self) -> float:
        return self.tec.configuration.pid.integral_value[0]

    @i_1_value.setter
    def i_1_value(self, i_value: int) -> None:
        self.tec.configuration.pid.integral_value[0] = i_value
        self.tec.set_pid_i_value(0)

    @property
    def i_2_value(self) -> float:
        return self.tec.configuration.pid.integral_value[1]

    @i_2_value.setter
    def i_2_value(self, i_value: float) -> None:
        self.tec.configuration.pid.integral_value[1] = i_value
        self.tec.set_pid_i_value(1)

    @property
    def d_value(self) -> int:
        return self.tec.configuration.pid.derivative_value

    @d_value.setter
    def d_value(self, d_value: int) -> None:
        if isinstance(d_value, int) and d_value >= 0:
            self.tec.configuration.pid.derivative_value = d_value
            self.tec.set_pid_p_value()
        else:
            self.tec_signals.d_value.emit(self.tec.configuration.pid.derivative_value)

    @property
    def setpoint_temperature(self) -> float:
        return self.tec.configuration.system_parameter.setpoint_temperature

    @setpoint_temperature.setter
    def setpoint_temperature(self, setpoint_temperature: float) -> None:
        self.tec.configuration.system_parameter.setpoint_temperature = setpoint_temperature
        self.tec.set_setpoint_temperature_value()

    @property
    def loop_time(self) -> int:
        return self.tec.configuration.system_parameter.loop_time

    @loop_time.setter
    def loop_time(self, loop_time: int) -> None:
        self.tec.configuration.system_parameter.loop_time = loop_time
        self.tec.set_loop_time_value()

    @property
    def reference_resistor(self) -> int:
        return self.tec.configuration.system_parameter.reference_resistor

    @reference_resistor.setter
    def reference_resistor(self, reference_resistor: float) -> None:
        self.tec.configuration.system_parameter.reference_resistor = reference_resistor
        self.tec.set_reference_resistor_value()

    @property
    def max_power(self) -> float:
        return self.tec.configuration.system_parameter.max_power

    @max_power.setter
    def max_power(self, max_power: float) -> None:
        self.tec.configuration.system_parameter.max_power = max_power
        self.tec.set_max_power_value()

    @property
    def cooling(self) -> bool:
        return self.tec.configuration.mode.cooling

    @cooling.setter
    def cooling(self, cooling: bool) -> None:
        self.tec.configuration.mode.cooling = cooling
        self.tec.configuration.mode.heating = not cooling
        self.tec.set_mode()
        if cooling:
            self.tec_signals.mode.emit(TecMode.COOLING)
        else:
            self.tec_signals.mode.emit(TecMode.HEATING)

    @property
    def heating(self) -> bool:
        return not self.cooling

    @heating.setter
    def heating(self, heating: bool) -> None:
        self.cooling = not heating

    def fire_configuration_change(self) -> None:
        self.tec_signals.d_value.emit(self.d_value)
        self.tec_signals.p_value.emit(self.p_value)
        self.tec_signals.i_1_value.emit(self.i_2_value)
        self.tec_signals.i_2_value.emit(self.i_2_value)
        self.tec_signals.setpoint_temperature.emit(self.setpoint_temperature)
        self.tec_signals.loop_time.emit(self.loop_time)
        self.tec_signals.reference_resistor.emit(self.reference_resistor)
        self.tec_signals.max_power.emit(self.max_power)
        if self.cooling:
            self.tec_signals.mode.emit(TecMode.COOLING)
        else:
            self.tec_signals.mode.emit(TecMode.HEATING)
        self.tec_signals.use_ntc.emit(self.tec.configuration.temperature_element.NTC)

    def _incoming_data(self) -> None:
        while self.driver.connected.is_set():
            if self._running:
                if self._init_headers:
                    units = {"Time": "H:M:S",
                             "TEC Pump Laser Enabled": "bool",
                             "TEC Probe Laser Enabled": "bool",
                             "Measured Temperature Pump Laser": "°C",
                             "Set Point Temperature Pump Laser": "°C",
                             "Measured Temperature Probe Laser": "°C",
                             "Set Point Temperature Probe Laser": "°C"}
                    pd.DataFrame(units, index=["Y:M:D"]).to_csv(f"{self._destination_folder}/tec.csv",
                                                                index_label="Date")
                    self._init_headers = False
            received_data: hardware.tec.Data = self.driver.data.get(block=True)
            self._buffer.append(received_data)
            signals.tec_data.emit(self._buffer)
            signals.tec_data_display.emit(received_data)
            if self._running:
                now = datetime.now()
                tec_data = {"Time": str(now.strftime("%H:%M:%S")),
                            "TEC Pump Laser Enabled": self.driver.tec[Tec.PUMP_LASER].enabled,
                            "TEC Probe Laser Enabled": self.driver.tec[Tec.PROBE_LASER].enabled,
                            "Measured Temperature Pump Laser": received_data.actual_temperature[Tec.PUMP_LASER],
                            "Set Point Temperature Pump Laser": received_data.set_point[Tec.PUMP_LASER],
                            "Measured Temperature Probe Laser": received_data.actual_temperature[Tec.PROBE_LASER],
                            "Set Point Temperature Probe Laser": received_data.set_point[Tec.PROBE_LASER]}
                tec_data_frame = pd.DataFrame(tec_data, index=[str(now.strftime("%Y-%m-%d"))])
                pd.DataFrame(tec_data_frame).to_csv(f"{self._destination_folder}/tec.csv", header=False, mode="a")


def _process_data(file_path: str, headers: list[str, ...]) -> pd.DataFrame:
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
    for header in headers:
        for header_data in data.columns:
            if header == header_data:
                break
        else:
            raise KeyError(f"Header {header} not found in file")
    return data


def process_dc_data(dc_file_path: str) -> None:
    headers = [f"DC CH{i}" for i in range(1, 4)]
    try:
        data = _process_data(dc_file_path, headers)
    except KeyError:
        headers = [f"PD{i}" for i in range(1, 4)]
        data = _process_data(dc_file_path, headers)
    except FileNotFoundError:
        return
    signals.decimation.emit(data)


def process_inversion_data(inversion_file_path: str) -> None:
    try:
        headers = ["Interferometric Phase", "Sensitivity CH1", "Sensitivity CH2", "Sensitivity CH3", "PTI Signal"]
        data = _process_data(inversion_file_path, headers)
        data["PTI Signal 60 s Mean"] = LiveCalculation.running_average(data["PTI Signal"], mean_size=60)
    except KeyError:
        headers = ["Sensitivity CH1", "Sensitivity CH2", "Sensitivity CH3", "Interferometric Phase"]
        data = _process_data(inversion_file_path, headers)
    except FileNotFoundError:
        return
    signals.inversion.emit(data)


def process_characterization_data(characterization_file_path: str) -> None:
    headers = [f"Amplitude CH{i}" for i in range(1, 4)]
    headers += [f"Output Phase CH{i}" for i in range(1, 4)]
    headers += [f"Offset CH{i}" for i in range(1, 4)]
    headers += ["Symmetry", "Relative Symmetry"]
    try:
        data = _process_data(characterization_file_path, headers)
    except FileNotFoundError:
        return
    signals.characterization.emit(data)


signals = Signals()
laser_signals = LaserSignals()
tec_signals = [TecSignals(), TecSignals()]
