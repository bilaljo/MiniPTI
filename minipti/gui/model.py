import abc
import copy
import csv
import enum
import itertools
import logging
import os
import platform
import queue
import subprocess
import threading
import time
import typing
from collections import deque
from dataclasses import dataclass, asdict
from datetime import datetime

import numpy as np
import pandas as pd
from PyQt5 import QtCore
from scipy import ndimage

from .. import algorithm
from .. import hardware


class SettingsTable(QtCore.QAbstractTableModel):
    HEADERS = ["Detector 1", "Detector 2", "Detector 3"]
    INDEX = ["Amplitude [V]", "Offset [V]", "Output Phases [deg]", "Response Phases [deg]"]
    SIGNIFICANT_VALUES = 4

    def __init__(self):
        QtCore.QAbstractTableModel.__init__(self)
        self._data = pd.DataFrame(columns=SettingsTable.HEADERS, index=SettingsTable.INDEX)
        self._file_path = f"{os.path.dirname(os.path.dirname(__file__))}/algorithm/configs/settings.csv"
        self._observer_callbacks = []
        signals.settings.connect(self.update_settings)

    @QtCore.pyqtSlot(algorithm.interferometry.Interferometer)
    def update_settings(self, interferometer: algorithm.interferometry.Interferometer) -> None:
        self.update_settings_parameters(interferometer)

    def rowCount(self, parent=None) -> int:
        return self._data.shape[0]

    def columnCount(self, parent=None) -> int:
        return self._data.shape[1]

    def data(self, index, role: int = ...) -> str | None:
        if index.isValid():
            if role == QtCore.Qt.DisplayRole or role == QtCore.Qt.EditRole:
                value = self._data.at[
                    SettingsTable.INDEX[index.row()], SettingsTable.HEADERS[index.column()]]
                return str(round(value, SettingsTable.SIGNIFICANT_VALUES))

    def flags(self, index):
        return QtCore.Qt.ItemIsSelectable | QtCore.Qt.ItemIsEnabled | QtCore.Qt.ItemIsEditable

    def setData(self, index, value, role: int = ...):
        if index.isValid():
            if role == QtCore.Qt.EditRole:
                self._data.at[SettingsTable.INDEX[index.row()], SettingsTable.HEADERS[
                    index.column()]] = float(value)
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

    def update_settings_parameters(self, interferometer: algorithm.interferometry.Interferometer):
        self.table_data.loc["Output Phases [deg]"] = np.rad2deg(interferometer.output_phases)
        self.table_data.loc["Amplitude [V]"] = interferometer.amplitudes
        self.table_data.loc["Offset [V]"] = interferometer.offsets

    def update_settings_paths(self, interferometer: algorithm.interferometry.Interferometer,
                              inversion: algorithm.pti.Inversion):
        interferometer.settings_path = self.file_path
        inversion.settings_path = self.file_path
        interferometer.load_settings()
        inversion.load_response_phase()

    def setup_settings_file(self):
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
                if list(settings.columns) != SettingsTable.HEADERS or list(
                        settings.index) != SettingsTable.INDEX:
                    self.save()  # The file is in any way broken.
                else:
                    self.table_data = settings


class Logging(logging.Handler):
    LOGGING_HISTORY = 50

    def __init__(self):
        logging.Handler.__init__(self)
        self.logging_messages = deque(maxlen=Logging.LOGGING_HISTORY)
        self.formatter = logging.Formatter('%(levelname)s %(asctime)s: %(message)s\n',
                                           datefmt='%Y-%m-%d %H:%M:%S')
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
            if not callable(getattr(self, member)) and not member.startswith(
                    "__") and member != "time_counter":
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
        self.dc_values = [deque(maxlen=Buffer.QUEUE_SIZE) for _ in range(PTIBuffer.CHANNELS)]
        self.interferometric_phase = deque(maxlen=Buffer.QUEUE_SIZE)
        self.sensitivity = [deque(maxlen=Buffer.QUEUE_SIZE) for _ in range(PTIBuffer.CHANNELS)]
        self.symmetry = deque(maxlen=Buffer.QUEUE_SIZE)
        self.pti_signal = deque(maxlen=Buffer.QUEUE_SIZE)
        self.pti_signal_mean = deque(maxlen=Buffer.QUEUE_SIZE)
        self._pti_signal_mean_queue = deque(maxlen=PTIBuffer.MEAN_SIZE)

    def append(self, pti_data: PTI,
               interferometer: algorithm.interferometry.Interferometer) -> None:
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
        # The first channel has always the phase 0 by definition hence it is not needed.
        self.output_phases = [deque(maxlen=Buffer.QUEUE_SIZE) for _ in range(self.CHANNELS - 1)]
        self.amplitudes = [deque(maxlen=Buffer.QUEUE_SIZE) for _ in
                           range(CharacterisationBuffer.CHANNELS)]

    def append(self, characterization: algorithm.interferometry.Characterization,
               interferometer: algorithm.interferometry.Interferometer) -> None:
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
        self.set_point: list[deque] = [deque(maxlen=Buffer.QUEUE_SIZE),
                                       deque(maxlen=Buffer.QUEUE_SIZE)]
        self.actual_value: list[deque] = [deque(maxlen=Buffer.QUEUE_SIZE),
                                          deque(maxlen=Buffer.QUEUE_SIZE)]

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


@dataclass
class Battery:
    percentage: int
    minutes_left: int


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
    settings = QtCore.pyqtSignal(pd.DataFrame)
    destination_folder_changed = QtCore.pyqtSignal(str)
    battery_state = QtCore.pyqtSignal(Battery)
    valve_change = QtCore.pyqtSignal(hardware.motherboard.Valve)
    bypass = QtCore.pyqtSignal(bool)
    tec_data = QtCore.pyqtSignal(Buffer)
    tec_data_display = QtCore.pyqtSignal(hardware.tec.Data)

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

    def __init__(self):
        QtCore.QObject.__init__(self)


class TecMode(enum.IntEnum):
    COOLING = 0
    HEATING = 1


@dataclass(init=False, frozen=True)
class TecSignals(QtCore.QObject):
    mode = QtCore.pyqtSignal(TecMode)
    p_value = QtCore.pyqtSignal(float)
    d_value = QtCore.pyqtSignal(float)
    i_1_value = QtCore.pyqtSignal(float)
    i_2_value = QtCore.pyqtSignal(float)
    setpoint_temperature = QtCore.pyqtSignal(float)
    loop_time = QtCore.pyqtSignal(float)
    reference_resistor = QtCore.pyqtSignal(float)
    max_power = QtCore.pyqtSignal(float)
    enabled = QtCore.pyqtSignal(bool)

    def __init__(self):
        QtCore.QObject.__init__(self)


def shutdown_procedure() -> None:
    Motherboard.driver.close()
    Laser.driver.close()
    Tec.driver.close()
    time.sleep(0.5)  # Give the calculations threads time to finish their write operation
    if platform.system() == "Windows":
        subprocess.run(r"shutdown /s /t 1", shell=True)
    else:
        subprocess.run("sleep 0.5s && echo poweroff", shell=True)


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
        self.interferometry = Interferometry(algorithm.interferometry.Interferometer(),
                                             algorithm.interferometry.Characterization())
        self.interferometry.characterization.interferometry = self.interferometry.interferometer
        self.pti = PTI(algorithm.pti.Decimation(),
                       algorithm.pti.Inversion(interferometer=self.interferometry.interferometer))
        self.interferometry.characterization.interferometry = self.interferometry.interferometer
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

        def calculate_characterization():
            while Motherboard.driver.running.is_set():
                self.interferometry.characterization()
                self.characterisation_buffer.append(self.interferometry.characterization,
                                                    self.interferometry.interferometer)
                signals.characterization_live.emit(self.characterisation_buffer)

        def calculate_inversion():
            while Motherboard.driver.running.is_set():
                self.pti.decimation.ref = np.array(Motherboard.driver.ref_signal)
                self.pti.decimation.dc_coupled = np.array(Motherboard.driver.dc_coupled)
                self.pti.decimation.ac_coupled = np.array(Motherboard.driver.ac_coupled)
                self.pti.decimation()
                self.pti.inversion.lock_in = self.pti.decimation.lock_in
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

        characterization_thread = threading.Thread(target=calculate_characterization, daemon=True)
        inversion_thread = threading.Thread(target=calculate_inversion, daemon=True)
        characterization_thread.start()
        inversion_thread.start()
        return characterization_thread, inversion_thread

    def calculate_characterisation(self, dc_file_path: str, use_settings=False, settings_path="") -> None:
        self.interferometry.interferometer.decimation_filepath = dc_file_path
        self.interferometry.interferometer.settings_path = settings_path
        self.interferometry.characterization.use_settings = use_settings
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

    @staticmethod
    def kelvin_to_celsius(temperature: float) -> float:
        return temperature - 273.15

    def process_bms_data(self) -> None:
        units = {"Date": "Y:M:D", "Time": "H:M:S", "External DC Power": "bool",
                 "Charging Battery": "bool",
                 "Minutes Left": "min", "Charging Level": "%", "Temperature": "°C", "Current": "mA",
                 "Voltage": "V", "Full Charge Capacity": "mAh", "Remaining Charge Capacity": "mAh"}
        pd.DataFrame(units).to_csv(self._destination_folder + "/BMS.csv")

        def incoming_data() -> None:
            while Motherboard.driver.running.is_set():
                bms_data: hardware.motherboard.BMSData = Motherboard.driver.bms
                bms_data.battery_temperature = Calculation.kelvin_to_celsius(
                    bms_data.battery_temperature)
                signals.battery_state.emit(Battery(bms_data.battery_percentage, bms_data.minutes_left))
                now = datetime.now()
                output_data = {"Date": str(now.strftime("%Y-%m-%d")),
                               "Time": str(now.strftime("%H:%M:%S"))}
                for key, value in asdict(bms_data).values():
                    output_data[key.replace("_", " ").title()] = value
                pd.DataFrame(output_data).to_csv(self._destination_folder + "/BMS.csv",
                                                 header=False, mode="a")
        threading.Thread(target=incoming_data).start()


class ProbeLaserMode(enum.IntEnum):
    CONSTANT_LIGHT = 0
    CONSTANT_CURRENT = 1


class Serial:
    """
    This class is a base class for subclasses of the driver objects from driver/serial.
    """

    driver = hardware.serial_device.Driver()

    @staticmethod
    def open() -> None:
        """
        Connects to a serial device and listens to incoming data.
        """
        Serial.driver.open()

    @staticmethod
    def close() -> None:
        """
        Disconnects to a serial device and stops listening to data
        """
        Serial.driver.close()

    @staticmethod
    @abc.abstractmethod
    def save_configuration() -> None:
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

    @staticmethod
    def _incoming_data():
        """
        Listens to incoming data and emits them as signals to the view as long a serial connection
        is established.
        """

    @staticmethod
    def process_measured_data() -> threading.Thread:
        processing_thread = threading.Thread(target=Serial._incoming_data, daemon=True)
        processing_thread.start()
        return processing_thread


class Motherboard(Serial):
    driver = hardware.motherboard.Driver()

    def __init__(self):
        Serial.__init__(self)
        self.bms_data: tuple[float, float] = (0, 0)

    @property
    def connected(self) -> bool:
        return self.driver.connected.is_set()

    @staticmethod
    def open() -> None:
        Motherboard.driver.open()
        Motherboard.driver.run()

    def run(self) -> bool:
        if not self.driver.connected.is_set():
            return False
        self.driver.reset()
        self.driver.running.set()
        return True

    def stop(self) -> None:
        self.driver.running.clear()

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
    def valve_duty_cycle(self, duty_cycle: int):
        if not 0 < self.driver.config.valve.duty_cycle < 100:
            raise ValueError("Invalid value for duty cycle")
        self.driver.config.valve.duty_cycle = duty_cycle

    @property
    def automatic_valve_switch(self) -> bool:
        return self.driver.config.valve.automatic_switch

    @automatic_valve_switch.setter
    def automatic_valve_switch(self, automatic_switch: bool):
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

    def load_configuration(self) -> None:
        Motherboard.driver.load_config()
        self.fire_configuration_change()

    @staticmethod
    def save_configuration() -> None:
        Motherboard.driver.save_config()

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
        self.config_path = "hardware/configs/laser.json"

    def load_configuration(self) -> None:
        Laser.driver.load_configuration()
        self.fire_configuration_change()

    @staticmethod
    def save_configuration() -> None:
        Laser.driver.save_configuration()

    @staticmethod
    def apply_configuration() -> None:
        Laser.driver.apply_configuration()

    @staticmethod
    def _incoming_data():
        while Laser.driver.running.is_set():
            received_data = Laser.driver.data.get(block=True)
            Laser.buffer.append(received_data)
            laser_signals.data.emit(Laser.buffer)
            laser_signals.data_display.emit(received_data)

    def fire_configuration_change(self) -> None:
        ...


class PumpLaser(Laser):
    def __init__(self):
        Laser.__init__(self)

    @property
    def connected(self) -> bool:
        return self.driver.connected.is_set()

    @property
    def driver_bits(self) -> int:
        return self.driver.pump_laser.bit_value

    @driver_bits.setter
    def driver_bits(self, bits: int) -> None:
        # With increasing the slider decreases its value but the voltage should increase
        # - hence we subtract the bits.
        self.driver.pump_laser.bit_value = hardware.laser.PumpLaser.NUMBER_OF_STEPS - bits
        self.fire_driver_bits_signal()
        self.driver.set_driver_voltage()

    def fire_driver_bits_signal(self) -> None:
        bits: int = self.driver.pump_laser.bit_value
        voltage: float = hardware.laser.PumpLaser.bit_to_voltage(bits)
        bits = hardware.laser.PumpLaser.NUMBER_OF_STEPS - bits
        laser_signals.laser_voltage.emit(bits, voltage)

    @property
    def enabled(self) -> bool:
        return self.driver.pump_laser_enabled

    @enabled.setter
    def enabled(self, state: bool):
        self.driver.pump_laser_enabled = state
        laser_signals.pump_laser_enabled.emit(state)

    @property
    def current_bits_dac_1(self) -> int:
        return self.driver.pump_laser.DAC_1.bit_value

    @current_bits_dac_1.setter
    def current_bits_dac_1(self, bits: int) -> None:
        self.driver.pump_laser.DAC_1.bit_value = bits
        self.fire_current_bits_dac_1()
        self.driver.set_dac_1()

    def fire_current_bits_dac_1(self) -> None:
        laser_signals.current_dac.emit(0, self.driver.pump_laser.DAC_1.bit_value)

    @property
    def current_bits_dac_2(self) -> int:
        return self.driver.pump_laser.DAC_2.bit_value

    @current_bits_dac_2.setter
    def current_bits_dac_2(self, bits: int) -> None:
        self.driver.pump_laser.DAC_2.bit_value = bits
        self.fire_current_bits_dac2()
        self.driver.set_dac_2()

    def fire_current_bits_dac2(self) -> None:
        laser_signals.current_dac.emit(1, self.driver.pump_laser.DAC_2.bit_value)

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
        laser_signals.matrix_dac.emit(dac_number, indices)

    @dac_1_matrix.setter
    def dac_1_matrix(self, dac: hardware.laser.DAC) -> None:
        self.driver.pump_laser.DAC_1 = dac
        self.fire_dac_matrix_1()

    def fire_dac_matrix_1(self) -> None:
        PumpLaser._set_indices(dac_number=0, dac=self.dac_1_matrix)

    @dac_2_matrix.setter
    def dac_2_matrix(self, dac: hardware.laser.DAC) -> None:
        self.driver.pump_laser.DAC_2 = dac
        self.fire_dac_matrix_2()

    def fire_dac_matrix_2(self) -> None:
        PumpLaser._set_indices(dac_number=1, dac=self.dac_2_matrix)

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

    def fire_configuration_change(self) -> None:
        self.fire_driver_bits_signal()
        self.fire_current_bits_dac_1()
        self.fire_current_bits_dac2()
        self.fire_dac_matrix_1()
        self.fire_dac_matrix_2()


class ProbeLaser(Laser):
    def __init__(self):
        Laser.__init__(self)

    @property
    def connected(self) -> bool:
        return self.driver.connected.is_set()

    @property
    def current_bits_probe_laser(self) -> int:
        return self.driver.probe_laser.current_bits

    @current_bits_probe_laser.setter
    def current_bits_probe_laser(self, bits: int) -> None:
        self.driver.probe_laser.current_bits = bits
        bit, current = self.fire_current_bits_signal()
        laser_signals.current_probe_laser.emit(hardware.laser.Driver.CURRENT_BITS - bits, current)
        self.driver.set_probe_laser_current()

    def fire_current_bits_signal(self) -> tuple[int, float]:
        bits: int = self.driver.probe_laser.current_bits
        current: float = hardware.laser.ProbeLaser.bit_to_current(bits)
        laser_signals.current_probe_laser.emit(hardware.laser.Driver.CURRENT_BITS - bits, current)
        return bits, current

    @property
    def enabled(self) -> bool:
        return self.driver.probe_laser_enabled

    @enabled.setter
    def enabled(self, state: bool) -> None:
        self.driver.probe_laser_enabled = state
        laser_signals.probe_laser_enabled.emit(state)

    @property
    def photo_diode_gain(self) -> int:
        return self.driver.probe_laser.photo_diode_gain

    @photo_diode_gain.setter
    def photo_diode_gain(self, photo_diode_gain: int) -> None:
        self.driver.probe_laser.photo_diode_gain = photo_diode_gain
        self.fire_photo_diode_gain_signal()
        self.driver.set_photo_gain()

    def fire_photo_diode_gain_signal(self) -> None:
        laser_signals.photo_gain.emit(self.driver.probe_laser.photo_diode_gain - 1)

    @property
    def probe_laser_max_current(self) -> float:
        return self.driver.probe_laser.max_current_mA

    @probe_laser_max_current.setter
    def probe_laser_max_current(self, current: float) -> None:
        if self.driver.probe_laser.max_current_mA != current:
            self.driver.probe_laser.max_current_mA = current
            self.fire_max_current_signal()

    def fire_max_current_signal(self) -> None:
        laser_signals.max_current_probe_laser.emit(self.driver.probe_laser.max_current_mA)

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
        self.fire_laser_mode_signal()

    def fire_laser_mode_signal(self) -> None:
        if self.driver.probe_laser.constant_light:
            laser_signals.probe_laser_mode.emit(ProbeLaserMode.CONSTANT_LIGHT)
        else:
            laser_signals.probe_laser_mode.emit(ProbeLaserMode.CONSTANT_CURRENT)

    def fire_configuration_change(self) -> None:
        self.fire_current_bits_signal()
        self.fire_laser_mode_signal()
        self.fire_photo_diode_gain_signal()
        self.fire_max_current_signal()


class Tec(Serial):
    driver = hardware.tec.Driver()
    _buffer = TecBuffer()

    def __init__(self, laser: str):
        Serial.__init__(self)
        self.laser = laser

    @property
    def connected(self) -> bool:
        return self.driver.connected.is_set()

    @property
    def enabled(self) -> bool:
        if self.laser == "Pump Laser":
            return self.driver.pump_laser_enabled
        else:
            return self.driver.probe_laser_enabled

    @enabled.setter
    def enabled(self, state):
        if self.laser == "Pump Laser":
            self.driver.pump_laser_enabled = state
            tec_signals["Pump Laser"].enabled.emit(state)
        else:
            self.driver.probe_laser_enabled = state
            tec_signals["Probe Laser"].enabled.emit(state)

    @property
    def config_path(self) -> str:
        return Tec.driver.config_path

    @config_path.setter
    def config_path(self, config_path: str):
        Tec.driver.config_path = config_path

    @staticmethod
    def save_configuration() -> None:
        Tec.driver.save_configuration()

    def load_configuration(self) -> None:
        Tec.driver.load_config()
        self.fire_configuration_change()

    @staticmethod
    def apply_configuration() -> None:
        Tec.driver.apply_configuration()

    @property
    def p_value(self) -> float:
        return self.driver[self.laser].pid.proportional_value

    @p_value.setter
    def p_value(self, p_value: float) -> None:
        self.driver[self.laser].pid.proportional_value = p_value
        self.driver.set_pid_p_value(self.laser)

    @property
    def i_1_value(self) -> float:
        return self.driver[self.laser].pid.integral_value[0]

    @i_1_value.setter
    def i_1_value(self, i_value: float) -> None:
        self.driver[self.laser].pid.integral_value[0] = i_value
        self.driver.set_pid_i_value(self.laser, 0)

    @property
    def i_2_value(self) -> float:
        return self.driver[self.laser].pid.integral_value[1]

    @i_2_value.setter
    def i_2_value(self, i_value: float) -> None:
        self.driver[self.laser].pid.integral_value[1] = i_value
        self.driver.set_pid_i_value(self.laser, 1)

    @property
    def d_value(self) -> float:
        return self.driver[self.laser].pid.derivative_value

    @d_value.setter
    def d_value(self, d_value: float) -> None:
        self.driver[self.laser].pid.derivative_value = d_value
        self.driver.set_pid_d_value(self.laser)

    @property
    def setpoint_temperature(self) -> float:
        return self.driver[self.laser].system_parameter.setpoint_temperature

    @setpoint_temperature.setter
    def setpoint_temperature(self, setpoint_temperature: float) -> None:
        self.driver[self.laser].system_parameter.setpoint_temperature = setpoint_temperature
        self.driver.set_setpoint_temperature_value(self.laser)

    @property
    def loop_time(self) -> float:
        return self.driver[self.laser].system_parameter.loop_time

    @loop_time.setter
    def loop_time(self, loop_time: float) -> None:
        self.driver[self.laser].system_parameter.loop_time = loop_time
        self.driver.set_loop_time_value(self.laser)

    @property
    def reference_resistor(self) -> float:
        return self.driver[self.laser].system_parameter.reference_resistor

    @reference_resistor.setter
    def reference_resistor(self, reference_resistor: float) -> None:
        self.driver[self.laser].system_parameter.reference_resistor = reference_resistor
        self.driver.set_reference_resistor_value(self.laser)

    @property
    def max_power(self) -> float:
        return self.driver[self.laser].system_parameter.reference_resistor

    @max_power.setter
    def max_power(self, max_power: float) -> None:
        self.driver[self.laser].system_parameter.reference_resistor = max_power
        self.driver.set_max_power_value(self.laser)

    @property
    def cooling(self) -> bool:
        return self.driver[self.laser].mode.cooling

    @cooling.setter
    def cooling(self, mode: bool):
        if mode:
            self.driver[self.laser].mode.heating = False
            self.driver[self.laser].mode.cooling = True
            tec_signals[self.laser].mode.emit(TecMode.COOLING)
            self.driver.set_mode(self.laser)
        else:
            self.driver[self.laser].mode.cooling = False
            tec_signals[self.laser].mode.emit(TecMode.HEATING)
            self.driver.set_mode(self.laser)

    @property
    def heating(self) -> bool:
        return self.driver[self.laser].mode.heating

    @heating.setter
    def heating(self, mode: bool):
        if mode:
            self.driver[self.laser].mode.heating = True
            self.driver[self.laser].mode.cooling = False
            tec_signals[self.laser].mode.emit(TecMode.HEATING)
            self.driver.set_mode(self.laser)
        else:
            self.driver[self.laser].mode.heating = False
            tec_signals[self.laser].mode.emit(TecMode.COOLING)
            self.driver.set_mode(self.laser)

    def fire_configuration_change(self):
        tec_signals[self.laser].d_value.emit(self.d_value)
        tec_signals[self.laser].p_value.emit(self.p_value)
        tec_signals[self.laser].i_1_value.emit(self.i_2_value)
        tec_signals[self.laser].i_2_value.emit(self.i_2_value)
        tec_signals[self.laser].setpoint_temperature.emit(self.setpoint_temperature)
        tec_signals[self.laser].loop_time.emit(self.loop_time)
        tec_signals[self.laser].reference_resistor.emit(self.reference_resistor)
        tec_signals[self.laser].max_power.emit(self.max_power)
        if self.cooling:
            tec_signals[self.laser].mode.emit(TecMode.COOLING)
        else:
            tec_signals[self.laser].mode.emit(TecMode.HEATING)

    def _incoming_data(self) -> None:
        while self.driver.connected.is_set():
            received_data = Tec.driver.data.get(block=True)
            Tec._buffer.append(received_data)
            signals.tec_data.emit(Tec._buffer)
            signals.tec_data_display.emit(received_data)


def _process_data(file_path: str, headers: list[str, ...]) -> pd.DataFrame:
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
        data = _process_data(dc_file_path, headers)
    except KeyError:
        headers = [f"PD{i}" for i in range(1, 4)]
        data = _process_data(dc_file_path, headers)
    signals.decimation.emit(data)


def process_inversion_data(inversion_file_path: str):
    try:
        headers = ["Interferometric Phase", "Sensitivity CH1", "Sensitivity CH2", "Sensitivity CH3",
                   "Total Sensitivity", "PTI Signal"]
        data = _process_data(inversion_file_path, headers)
        data["PTI Signal 60 s Mean"] = running_average(data["PTI Signal"], mean_size=60)
    except KeyError:
        headers = ["Sensitivity CH1", "Sensitivity CH2", "Sensitivity CH3",
                   "Total Sensitivity", "Interferometric Phase"]
        data = _process_data(inversion_file_path, headers)
    signals.inversion.emit(data)


def process_characterization_data(characterization_file_path: str):
    headers = [f"Amplitude CH{i}" for i in range(1, 4)]
    headers += [f"Output Phase CH{i}" for i in range(1, 4)]
    headers += [f"Offset CH{i}" for i in range(1, 4)]
    data = _process_data(characterization_file_path, headers)
    signals.characterization.emit(data)


class TecLaserSignals(typing.NamedTuple):
    probe_laser = TecSignals()
    pump_laser = TecSignals()

    def __getitem__(self, item) -> TecSignals:
        if item == "Pump Laser" or item == "Probe Laser":
            return getattr(self, item.replace(" ", "_").casefold())
        else:
            raise KeyError("Can only subscribe Pump Laser or Probe Laser")


signals = Signals()
laser_signals = LaserSignals()
tec_signals = TecLaserSignals()
