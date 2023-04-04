import abc
import copy
import csv
import enum
import itertools
import logging
import os
import threading
from collections import deque
import typing
from dataclasses import dataclass, asdict
from datetime import datetime

import numpy as np
import pandas as pd
from PyQt5 import QtCore
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
        signals.settings.connect(self.update_settings)

    @QtCore.pyqtSlot(interferometry.Interferometer)
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

    def append(self, laser_data: hardware.laser.Data) -> None:
        self.time.append(next(self.time_counter) / 10)
        self.pump_laser_current.append(laser_data.pump_laser_current)
        self.pump_laser_voltage.append(laser_data.pump_laser_voltage)
        self.probe_laser_current.append(laser_data.probe_laser_current)


class TecBuffer(Buffer):
    PUMP_LASER = hardware.tec.Driver.PUMP_LASER
    PROBE_LASER = hardware.tec.Driver.PROBE_LASER

    def __init__(self):
        Buffer.__init__(self)
        self.set_point: typing.Annotated[list[deque], 2] = [
            deque(maxlen=Buffer.QUEUE_SIZE), deque(maxlen=Buffer.QUEUE_SIZE)
        ]
        self.actual_value:  typing.Annotated[list[deque], 2] = [
            deque(maxlen=Buffer.QUEUE_SIZE), deque(maxlen=Buffer.QUEUE_SIZE)
        ]

    def append(self, tec_data: hardware.tec.Data):
        self.set_point[TecBuffer.PUMP_LASER].append(tec_data.set_point.pump_laser)
        self.set_point[TecBuffer.PROBE_LASER].append(tec_data.set_point.probe_laser)
        self.actual_value[TecBuffer.PUMP_LASER].append(tec_data.actual_temperature.pump_laser)
        self.actual_value[TecBuffer.PROBE_LASER].append(tec_data.actual_temperature.probe_laser)
        self.time.append(next(self.time_counter) / 10)


class Mode(enum.IntEnum):
    DISABLED = 0
    CONTINUOUS_WAVE = 1
    PULSED = 2


@dataclass(init=False, frozen=True)
class Signals(QtCore.QObject):
    decimation = QtCore.pyqtSignal(pd.DataFrame)
    decimation_live = QtCore.pyqtSignal(Buffer)
    inversion = QtCore.pyqtSignal(pd.DataFrame)
    inversion_live = QtCore.pyqtSignal(Buffer)
    characterization = QtCore.pyqtSignal(pd.DataFrame)
    characterization_live = QtCore.pyqtSignal(Buffer)
    settings_pti = QtCore.pyqtSignal()
    logging_update = QtCore.pyqtSignal(deque)
    daq_running = QtCore.pyqtSignal()
    laser_voltage = QtCore.pyqtSignal(int, float)
    current_dac = QtCore.pyqtSignal(int, int)
    matrix_dac = QtCore.pyqtSignal(int, list)
    laser_data = QtCore.pyqtSignal(Buffer)
    laser_data_display = QtCore.pyqtSignal(hardware.laser.Data)
    tec_data = QtCore.pyqtSignal(Buffer)
    tec_data_display = QtCore.pyqtSignal(hardware.tec.Data)
    current_probe_laser = QtCore.pyqtSignal(int, float)
    max_current_probe_laser = QtCore.pyqtSignal(float)
    probe_laser_mode = QtCore.pyqtSignal(int)
    settings = QtCore.pyqtSignal(pd.DataFrame)
    destination_folder_changed = QtCore.pyqtSignal(str)
    photo_gain = QtCore.pyqtSignal(int)
    battery_state = QtCore.pyqtSignal(tuple[int, int])


    def __init__(self):
        QtCore.QObject.__init__(self)


@dataclass(init=False, frozen=True)
class TecSignals(QtCore.QObject):
    p_value = QtCore.pyqtSignal(float)
    d_value = QtCore.pyqtSignal(float)
    i_1_value = QtCore.pyqtSignal(float)
    i_2_value = QtCore.pyqtSignal(float)
    setpoint_temperature = QtCore.pyqtSignal(float)
    loop_time = QtCore.pyqtSignal(float)
    reference_resistor = QtCore.pyqtSignal(float)
    max_power = QtCore.pyqtSignal(float)

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
                self.pti.decimation.ref = np.array(Motherboard.driver.ref_signal)
                self.pti.decimation.dc_coupled = np.array(Motherboard.driver.dc_coupled)
                self.pti.decimation.ac_coupled = np.array(Motherboard.driver.ac_coupled)
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

    def process_bms_data(self) -> None:
        units = {"Date": "Y:M:D", "Time": "H:M:S", "Exernal DC Power": "bool", "Charging Battery": "bool",
                 "Minutes Left": "min", "Charging Level": "%", "Temperature": "°C", "Current": "mA",
                 "Voltage": "V", "Full Charge Capacity": "mAh", "Remaining Charge Capacity": "mAh"}
        pd.DataFrame(units).to_csv(self._destination_folder + "/BMS.csv")

        def incoming_data():
            while Motherboard.driver.connected.is_set():
                bms_data: hardware.motherboard.BMSData = Motherboard.driver.bms
                signals.battery_state.emit((bms_data.battery_percentage, bms_data.minutes_left))
                now = datetime.now()
                output_data = {"Date": str(now.strftime("%Y-%m-%d")), "Time": str(now.strftime("%H:%M:%S"))}
                for key, value in asdict(bms_data).values():
                    new_key: str = key
                    new_key.replace("_", " ")
                    new_key.find(" ")
                pd.DataFrame(asdict(bms_data)).to_csv(self._destination_folder + "/BMS.csv", header=False, mode="a")


class Motherboard:
    driver = hardware.motherboard.Driver()

    def __init__(self, daq_driver=None):
        if daq_driver is not None:
            self._driver = daq_driver
        else:
            self._driver = Motherboard.driver
        self.bms_data: tuple[float, float] = (0, 0)


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
        self.driver.load_configuration()

    def save_configuration(self) -> None:
        self.driver.save_configuration()

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
    _buffer = TecBuffer()

    def __init__(self, laser="", tec_buffer=TecBuffer(), tec_driver=None):
        self.laser = laser
        if tec_buffer is not None:
            self.tec_buffer = tec_buffer
        else:
            self.laser_buffer = Tec._buffer
        if tec_driver is not None:
            self.driver = tec_driver
        else:
            self.driver = Tec.driver
            self.driver.used_laser = laser
        self.load_configuration()

    @property
    def config_path(self) -> str:
        return Tec.driver.config_path

    @config_path.setter
    def config_path(self, config_path: str) -> None:
        if os.path.exists(config_path):
            Tec.driver.config_path = config_path

    def load_configuration(self) -> None:
        self.driver.load_config()

    def save_configuration(self) -> None:
        self.driver.save_configuration()

    def apply_configuration(self) -> None:
        self.driver.apply_configuration()

    def open(self) -> None:
        self.driver.open()
        self.driver.run()

    @property
    def p_value(self) -> float:
        match self.laser:
            case "Pump Laser":
                return self.driver.pump_laser.PID.P_parameter
            case "Probe Laser":
                return self.driver.probe_laser.PID.P_parameter
            case _:
                raise AttributeError("Invalid laser name")

    @p_value.setter
    def p_value(self, p_value: float) -> None:
        match self.laser:
            case "Pump Laser":
                self.driver.pump_laser.PID.P_parameter = p_value
                pump_laser_tec_signals.p_value.emit(p_value)
            case "Probe Laser":
                self.driver.probe_laser.PID.P_parameter = p_value
                probe_laser_tec_signals.p_value.emit(p_value)
            case _:
                raise AttributeError("Invalid laser name")
        self.driver.set_pid_p_value(self.laser)

    @property
    def i_1_value(self) -> float:
        match self.laser:
            case "Pump Laser":
                return self.driver.pump_laser.PID.I_parameter[0]
            case "Probe Laser":
                return self.driver.probe_laser.PID.I_parameter[0]
            case _:
                raise AttributeError("Invalid laser name")

    @i_1_value.setter
    def i_1_value(self, i_value: float) -> None:
        match self.laser:
            case "Pump Laser":
                self.driver.pump_laser.PID.I_parameter[0] = i_value
                pump_laser_tec_signals.i_1_value.emit(i_value)
            case "Probe Laser":
                self.driver.probe_laser.PID.I_parameter[0] = i_value
                probe_laser_tec_signals.i_1_value.emit(i_value)
            case _:
                raise AttributeError("Invalid laser name")
        self.driver.set_pid_i_value(self.laser, 0)

    @property
    def i_2_value(self) -> float:
        match self.laser:
            case "Pump Laser":
                return self.driver.pump_laser.PID.I_parameter[1]
            case "Probe Laser":
                return self.driver.probe_laser.PID.I_parameter[1]
            case _:
                raise AttributeError("Invalid laser name")

    @i_2_value.setter
    def i_2_value(self, i_value: float) -> None:
        match self.laser:
            case "Pump Laser":
                self.driver.pump_laser.PID.I_parameter[1] = i_value
                pump_laser_tec_signals.i_2_value.emit(i_value)
            case "Probe Laser":
                self.driver.probe_laser.PID.I_parameter[1] = i_value
                probe_laser_tec_signals.i_2_value.emit(i_value)
            case _:
                raise AttributeError("Invalid laser name")
        self.driver.set_pid_i_value(self.laser, 1)

    @property
    def d_value(self) -> float:
        match self.laser:
            case "Pump Laser":
                return self.driver.pump_laser.PID.D_parameter
            case "Probe Laser":
                return self.driver.probe_laser.PID.D_parameter
            case _:
                raise AttributeError("Invalid laser name")

    @d_value.setter
    def d_value(self, d_value: float) -> None:
        match self.laser:
            case "Pump Laser":
                self.driver.pump_laser.PID.D_parameter = d_value
                pump_laser_tec_signals.d_value.emit(d_value)
            case "Probe Laser":
                self.driver.probe_laser.PID.D_parameter = d_value
                probe_laser_tec_signals.d_value.emit(d_value)
            case _:
                raise AttributeError("Invalid laser name")
        self.driver.set_pid_d_value(self.laser)

    @property
    def setpoint_temperature(self) -> float:
        match self.laser:
            case "Pump Laser":
                return self.driver.pump_laser.system_parameter.setpoint_temperature
            case "Probe Laser":
                return self.driver.probe_laser.system_parameter.setpoint_temperature

    @setpoint_temperature.setter
    def setpoint_temperature(self, setpoint_temperature: float) -> None:
        match self.laser:
            case "Pump Laser":
                self.driver.pump_laser.system_parameter.setpoint_temperature = setpoint_temperature
                pump_laser_tec_signals.setpoint_temperature.emit(setpoint_temperature)
            case "Probe Laser":
                self.driver.probe_laser.system_parameter.setpoint_temperature = setpoint_temperature
                probe_laser_tec_signals.setpoint_temperature.emit(setpoint_temperature)
            case _:
                raise AttributeError("Invalid laser name")
        self.driver.set_setpoint_temperature_value(self.laser)

    @property
    def loop_time(self) -> float:
        match self.laser:
            case "Pump Laser":
                return self.driver.pump_laser.system_parameter.loop_time
            case "Probe Laser":
                return self.driver.probe_laser.system_parameter.loop_time

    @loop_time.setter
    def loop_time(self, loop_time: float) -> None:
        match self.laser:
            case "Pump Laser":
                self.driver.pump_laser.system_parameter.loop_time = loop_time
                pump_laser_tec_signals.loop_time.emit(loop_time)
            case "Probe Laser":
                self.driver.probe_laser.system_parameter.loop_time = loop_time
                probe_laser_tec_signals.loop_time.emit(loop_time)
            case _:
                raise AttributeError("Invalid laser name")
        self.driver.set_loop_time_value(self.laser)

    @property
    def reference_resistor(self) -> float:
        match self.laser:
            case "Pump Laser":
                return self.driver.pump_laser.system_parameter.reference_resistor
            case "Probe Laser":
                return self.driver.probe_laser.system_parameter.reference_resistor

    @reference_resistor.setter
    def reference_resistor(self, reference_resistor: float) -> None:
        match self.laser:
            case "Pump Laser":
                self.driver.pump_laser.system_parameter.reference_resistor = reference_resistor
                pump_laser_tec_signals.reference_resistor.emit(reference_resistor)
            case "Probe Laser":
                self.driver.probe_laser.system_parameter.reference_resistor = reference_resistor
                probe_laser_tec_signals.reference_resistor.emit(reference_resistor)
            case _:
                raise AttributeError("Invalid laser name")
        self.driver.set_reference_resistor_value(self.laser)

    @property
    def max_power(self) -> float:
        match self.laser:
            case "Pump Laser":
                return self.driver.pump_laser.system_parameter.reference_resistor
            case "Probe Laser":
                return self.driver.probe_laser.system_parameter.reference_resistor

    @max_power.setter
    def max_power(self, max_power: float) -> None:
        match self.laser:
            case "Pump Laser":
                self.driver.pump_laser.system_parameter.max_power = max_power
                pump_laser_tec_signals.max_power.emit(max_power)
            case "Probe Laser":
                self.driver.probe_laser.system_parameter.max_power = max_power
                probe_laser_tec_signals.max_power.emit(max_power)
            case _:
                raise AttributeError("Invalid laser name")
        self.driver.set_max_power_value(self.laser)

    def update_values(self):
        match self.laser:
            case "Pump Laser":
                pump_laser_tec_signals.d_value.emit(self.d_value)
                pump_laser_tec_signals.p_value.emit(self.p_value)
                pump_laser_tec_signals.i_1_value.emit(self.i_2_value)
                pump_laser_tec_signals.i_2_value.emit(self.i_2_value)
                pump_laser_tec_signals.setpoint_temperature.emit(self.setpoint_temperature)
                pump_laser_tec_signals.loop_time.emit(self.loop_time)
                pump_laser_tec_signals.reference_resistor.emit(self.reference_resistor)
                pump_laser_tec_signals.max_power.emit(self.max_power)
            case "Probe Laser":
                probe_laser_tec_signals.d_value.emit(self.d_value)
                probe_laser_tec_signals.p_value.emit(self.p_value)
                probe_laser_tec_signals.i_1_value.emit(self.i_2_value)
                probe_laser_tec_signals.i_2_value.emit(self.i_2_value)
                probe_laser_tec_signals.setpoint_temperature.emit(self.setpoint_temperature)
                probe_laser_tec_signals.loop_time.emit(self.loop_time)
                probe_laser_tec_signals.reference_resistor.emit(self.reference_resistor)
                probe_laser_tec_signals.max_power.emit(self.max_power)

    def process_measured_data(self) -> None:
        def incoming_data():
            while self.driver.connected.is_set():
                received_data = Tec.driver.data.get(block=True)
                self.tec_buffer.append(received_data)
                signals.tec_data.emit(self.tec_buffer)
                signals.tec_data_display.emit(received_data)
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


signals = Signals()
probe_laser_tec_signals = TecSignals()
pump_laser_tec_signals = TecSignals()
