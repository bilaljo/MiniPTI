import abc
import dataclasses
import json
import logging
import os
from dataclasses import dataclass
from typing import Annotated, Union

import dacite

from . import serial_device
from .. import json_parser


@dataclass
class Data(serial_device.Data):
    high_power_laser_enabled: bool
    high_power_laser_current: float
    high_power_laser_voltage: float
    low_power_laser_current: float
    low_power_laser_enabled: bool


class Driver(serial_device.Driver):
    HARDWARE_ID: bytes = b"0002"
    NAME: str = "Laser"
    DELIMITER: str = "\t"
    DATA_START: str = "L"
    _START_MEASURED_DATA: int = 1
    _END_MEASURED_DATA: int = 4

    def __init__(self):
        serial_device.Driver.__init__(self)
        self.high_power_laser = HighPowerLaser(self)
        self.low_power_laser = LowPowerLaser(self)

    def open(self) -> None:
        self.low_power_laser.initialize()
        self.high_power_laser.initialize()

    @property
    def device_id(self) -> bytes:
        return Driver.HARDWARE_ID

    @property
    def device_name(self) -> str:
        return Driver.NAME

    @property
    def end_data_frame(self) -> int:
        return 4

    def open(self) -> None:
        super().open()
        self.high_power_laser.initialize()
        self.low_power_laser.initialize()
        # Disable lasers, if they were enabled by default, for safety
        self.low_power_laser.enabled = False
        self.high_power_laser.enabled = False

    def _process_data(self) -> None:
        while self.connected.is_set():
            self._encode_data()

    def _encode_data(self) -> None:
        try:
            received_data: str = self.get_data()
        except OSError:
            return
        for received in received_data.split(Driver.TERMINATION_SYMBOL):
            if not received:
                continue
            if received[0] == "N":
                logging.error(f"Invalid command {received}")
                self.ready_write.set()
            elif received[0] == "S" or received[0] == "C":
                self._check_ack(received)
            elif received[0] == "L":
                data_frame = received.split("\t")[Driver._START_DATA_FRAME:self.end_data_frame]
                self.data.put(Data(high_power_laser_current=float(data_frame[0]),
                                   high_power_laser_voltage=float(data_frame[1]),
                                   low_power_laser_current=float(data_frame[2]),
                                   low_power_laser_enabled=self.low_power_laser.enabled,
                                   high_power_laser_enabled=self.high_power_laser.enabled))
            else:  # Broken data frame without header char
                logging.error("Received invalid package without header")
                self.ready_write.set()
                continue


@dataclass
class DAC:
    bit_value: int
    continuous_wave: Annotated[list[bool], 3]
    pulsed_mode: Annotated[list[bool], 3]


@dataclass
class HighPowerLaserConfig:
    _RESISTOR = 2.2e4
    _DIGITAL_POT = 1e4
    NUMBER_OF_STEPS = 1 << 7
    _PRE_RESISTOR = 1.6e3

    _NUMBER_OF_DIGITS = serial_device.Driver.NUMBER_OF_HEX_BYTES

    max_current_mA: float
    bit_value: int
    DAC: list[DAC, DAC]

    @staticmethod
    def bit_to_voltage(bits: int) -> float:
        # 0.8 is an interpolation constant without any practical meaning.
        return 0.8 * HighPowerLaserConfig._RESISTOR / (bits * HighPowerLaserConfig._DIGITAL_POT
                                                       / HighPowerLaserConfig.NUMBER_OF_STEPS
                                                       + HighPowerLaserConfig._PRE_RESISTOR) + 0.8

    @staticmethod
    def voltage_to_bit(voltage: float) -> int:
        return int((0.8 * HighPowerLaserConfig._RESISTOR / (voltage - 0.8) - HighPowerLaserConfig._PRE_RESISTOR)
                   * HighPowerLaserConfig.NUMBER_OF_STEPS / HighPowerLaserConfig._DIGITAL_POT)


@dataclass
class Mode:
    constant_current: bool
    constant_light: bool


@dataclass
class Current:
    max_mA: float
    bits: int


@dataclass
class LowPowerLaserConfig:
    current: Current
    mode: Mode
    photo_diode_gain: int

    @staticmethod
    def bit_to_current(bits: int) -> float:
        # Values and formula is given by hardware
        return (bits - 260.4) / (-5.335)

    @staticmethod
    def current_to_bit(current: float) -> int:
        return int(-5.335 * current + 260.4)


class Laser:
    _NUMBER_OF_DIGITS = 4

    def __init__(self, driver: Driver):
        self.config_path = ""
        self._driver = driver
        self._initialized = False
        self._enabled = False

    @abc.abstractmethod
    def initialize(self) -> None:
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


class LowPowerLaser(Laser):
    _CONSTANT_CURRENT = "0001"
    _CONSTANT_LIGHT = "0002"
    CURRENT_BITS: int = (1 << 8) - 1

    def __init__(self, driver: Driver):
        Laser.__init__(self, driver)
        self.config_path: str = f"{os.path.dirname(__file__)}/configs/laser/low_power.json"
        self.configuration: Union[None, LowPowerLaserConfig] = None
        self._init = serial_device.SerialStream("CLI0000")
        self.mode = serial_device.SerialStream("SLM0000")
        self.photo_diode_gain = serial_device.SerialStream("SLG0000")
        self._set_digpot = serial_device.SerialStream("SLS0000")
        self._enable = serial_device.SerialStream("SLE0001")
        self.load_configuration()

    @property
    def enabled(self) -> bool:
        return self._enabled

    @enabled.setter
    def enabled(self, enabled: bool) -> None:
        self._enabled = enabled
        self._enable.value = enabled
        self._driver.write(self._enable)

    def initialize(self) -> None:
        self._init.value = True
        self._initialized = True
        self._driver.write(self._init)

    def load_configuration(self) -> None:
        with open(self.config_path) as config:
            loaded_config = json.load(config)
            self.configuration = dacite.from_dict(LowPowerLaserConfig, loaded_config["Low Power Laser"])

    def save_configuration(self) -> None:
        with open(self.config_path, "w") as configuration:
            laser = {"Low Power Laser": dataclasses.asdict(self.configuration)}
            configuration.write(json_parser.to_json(laser) + "\n")
            logging.info("Saved low power laser configuration in %s", self.config_path)

    def apply_configuration(self) -> None:
        self.set_mode()
        self.set_current()
        # self.set_photo_diode_gain()

    def set_mode(self) -> None:
        if self.configuration.mode.constant_light:
            self.mode.value = LowPowerLaser._CONSTANT_LIGHT
        else:
            self.mode.value = LowPowerLaser._CONSTANT_CURRENT
        # self._driver.write(self.mode)

    def set_current(self) -> None:
        current = LowPowerLaserConfig.bit_to_current(self.configuration.current.bits)
        if current > self.configuration.current.max_mA:
            logging.error(f"Current exceeds maximum current of {self.configuration.current.max_mA} mA")
            logging.warning(f"Setting it to maximum value of {self.configuration.current.max_mA} mA")
            current = LowPowerLaserConfig.current_to_bit(self.configuration.current.max_mA)
        else:
            current = self.configuration.current.bits
        self._set_digpot.value = current
        self._driver.write(self._set_digpot)

    def set_photo_diode_gain(self) -> None:
        self.photo_diode_gain.value = self.configuration.photo_diode_gain
        # self._driver.write(self.photo_diode_gain)


class HighPowerLaser(Laser):
    _DAC_1_REGISTER: list[int] = [1 << 8, 1 << 9, 1 << 10, 1 << 11, 1 << 12, 1 << 13]
    _DAC_2_REGISTER: list[int] = [1 << 14, 1 << 15, 1 << 0, 1 << 1, 1 << 2, 1 << 3]
    _CHANNELS = 3
    _DAC_CHANNELS = 2

    def __init__(self, driver: Driver):
        Laser.__init__(self, driver)
        self.config_path: str = f"{os.path.dirname(__file__)}/configs/laser/high_power.json"
        self.configuration: Union[None, HighPowerLaserConfig] = None
        self._init = serial_device.SerialStream("CHI0000")
        self._set_voltage = serial_device.SerialStream("SHV0000")
        self._control_register = [serial_device.SerialStream("SC10000"), serial_device.SerialStream("SC20000")]
        self._set_dac = [serial_device.SerialStream("SC30000"), serial_device.SerialStream("SC40000")]
        self._enable = serial_device.SerialStream("SHE0001")
        self.load_configuration()

    def initialize(self) -> None:
        self._driver.write(self._init)

    @property
    def enabled(self) -> bool:
        return self._enable.value == 1

    @enabled.setter
    def enabled(self, enabled: bool) -> None:
        self._enable.value = enabled
        self._driver.write(self._enable)

    def load_configuration(self) -> None:
        with open(self.config_path) as config:
            loaded_config = json.load(config)
            self.configuration = dacite.from_dict(HighPowerLaserConfig, loaded_config["High Power Laser"])

    def save_configuration(self) -> None:
        with open(self.config_path, "w") as configuration:
            laser = {"High Power Laser": dataclasses.asdict(self.configuration)}
            configuration.write(json_parser.to_json(laser) + "\n")
            logging.info("Saved high power laser configuration in %s", self.config_path)

    def apply_configuration(self) -> None:
        self.set_dac(0)
        self.set_dac(1)
        self.set_voltage()
        self.set_dac_matrix()

    def set_voltage(self) -> None:
        self._set_voltage.value = self.configuration.bit_value
        self._driver.write(self._set_voltage)

    def set_dac(self, i: int) -> None:
        self._set_dac[i].value = self.configuration.DAC[i].bit_value
        self._driver.write(self._set_dac[i])

    def set_dac_matrix(self) -> None:
        matrix = 0
        for i in range(HighPowerLaser._CHANNELS):
            for j in range(HighPowerLaser._DAC_CHANNELS):
                if self.configuration.DAC[j].continuous_wave[i]:
                    matrix |= HighPowerLaser._DAC_1_REGISTER[2 * i]
                elif self.configuration.DAC[j].pulsed_mode[i]:
                    matrix |= HighPowerLaser._DAC_1_REGISTER[2 * i + 1]
        self._control_register[0].value = matrix
        self._driver.write(self._control_register[0])
