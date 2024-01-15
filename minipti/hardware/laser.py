import dataclasses
import json
import logging
import typing
from abc import abstractmethod
from dataclasses import dataclass
from typing import Annotated, Final, Union

import dacite
from overrides import override

import minipti
from . import protocolls
from . import serial_device, _json_parser


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
        self.encode = False

    def startup(self):
        self.high_power_laser.initialize()
        self.low_power_laser.initialize()
        self.high_power_laser.apply_configuration()
        self.low_power_laser.apply_configuration()
        # Disable lasers, if they were enabled by default, for safety
        self.low_power_laser.enabled = False
        self.high_power_laser.enabled = False

    def clear(self):
        self.low_power_laser.enabled = False
        self.high_power_laser.enabled = False
        super().clear()

    @property
    def device_id(self) -> bytes:
        return Driver.HARDWARE_ID

    @property
    def device_name(self) -> str:
        return Driver.NAME

    @property
    def end_data_frame(self) -> int:
        return 4

    def _process_data(self) -> None:
        while self.connected.is_set():
            self.encode_data()

    @override
    def _encode(self, data: str) -> None:
        if data[0] == "N":
            logging.error(f"Invalid command {data}")
            self._ready_write.set()
        elif data[0] == "S" or data[0] == "C":
            self._check_ack(data)
        elif data[0] == "L":
            data_frame = data.split("\t")[Driver._START_DATA_FRAME:self.end_data_frame]
            self.data.put(Data(high_power_laser_current=float(data_frame[0]),
                               high_power_laser_voltage=float(data_frame[1]),
                               low_power_laser_current=float(data_frame[2]),
                               low_power_laser_enabled=self.low_power_laser.enabled,
                               high_power_laser_enabled=self.high_power_laser.enabled))


@dataclass
class DAC:
    bit_value: int = 0
    continuous_wave: list[bool] = dataclasses.field(
        default_factory=lambda: [False, False, False]
    )
    pulsed_mode: list[bool] = dataclasses.field(
        default_factory=lambda: [False, False, False])


@dataclass
class HighPowerLaserConfig:
    max_current_mA: float = 0
    bit_value: int = 255
    DAC: list[DAC, DAC] = dataclasses.field(default_factory=lambda: [DAC(), DAC()])


@dataclass
class Mode:
    constant_current: bool = True
    constant_light: bool = False


@dataclass
class Current:
    max_mA: float = 0
    bits: int = 127


@dataclass
class LowPowerLaserConfig:
    current: Current = dataclasses.field(
        default_factory=lambda: Current())
    mode: Mode = dataclasses.field(
        default_factory=lambda: Mode())
    photo_diode_gain: int = 1

    @staticmethod
    def bit_to_current(bits: int) -> float:
        # Values and formula is given by hardware
        return (bits - 260.4) / (-5.335)

    @staticmethod
    def current_to_bit(current: float) -> int:
        # Values and formula is given by hardware
        return int(-5.335 * current + 260.4)


class Laser:
    def __init__(self, driver: Driver):
        self.config_path = ""
        self._driver = driver
        self._initialized = False
        self._enabled = False

    @abstractmethod
    def initialize(self) -> None:
        ...

    @property
    @abstractmethod
    def enabled(self) -> bool:
        ...

    @enabled.setter
    @abstractmethod
    def enabled(self, enabled: bool) -> None:
        ...

    @abstractmethod
    def load_configuration(self) -> bool:
        ...

    @abstractmethod
    def save_configuration(self) -> None:
        ...

    @abstractmethod
    def apply_configuration(self) -> None:
        ...


class LowPowerLaser(Laser):
    _CONSTANT_CURRENT: Final[str] = "0001"
    _CONSTANT_LIGHT: Final[str] = "0002"
    CURRENT_BITS: Final[int] = (1 << 8) - 1

    def __init__(self, driver: Driver):
        Laser.__init__(self, driver)
        self.config_path: str = f"{minipti.module_path}/hardware/configs/laser/low_power.json"
        self.configuration: Union[None, LowPowerLaserConfig] = None
        self._init = protocolls.ASCIIHex("CLI0000")
        self.mode = protocolls.ASCIIHex("SLM0000")
        self.photo_diode_gain = protocolls.ASCIIHex("SLG0000")
        self._set_digpot = protocolls.ASCIIHex("SLS0000")
        self._enable = protocolls.ASCIIHex("SLE0001")
        self.load_configuration()

    @property
    @override
    def enabled(self) -> bool:
        return self._enabled

    @enabled.setter
    @override
    def enabled(self, enabled: bool) -> None:
        self._enabled = enabled
        self._enable.value = enabled
        self._driver.write(self._enable)

    def initialize(self) -> None:
        self._init.value = True
        self._initialized = True
        self._driver.write(self._init)

    @override
    def load_configuration(self) -> bool:
        with open(self.config_path) as config:
            try:
                loaded_config = json.load(config)
                self.configuration = dacite.from_dict(LowPowerLaserConfig,
                                                      loaded_config["Low Power Laser"])
                return True
            except (dacite.DaciteError, json.decoder.JSONDecodeError):
                self.configuration = LowPowerLaserConfig()
                return False

    @override
    def save_configuration(self) -> None:
        with open(self.config_path, "w") as configuration:
            laser = {"Low Power Laser": dataclasses.asdict(self.configuration)}
            configuration.write(_json_parser.to_json(laser) + "\n")
            logging.info("Saved low power laser configuration in %s", self.config_path)

    @override
    def apply_configuration(self) -> None:
        self.set_mode()
        self.set_current()
        self.set_photo_diode_gain()

    def set_mode(self) -> None:
        if self.configuration.mode.constant_light:
            self.mode.value = LowPowerLaser._CONSTANT_LIGHT
        else:
            self.mode.value = LowPowerLaser._CONSTANT_CURRENT
        self._driver.write(self.mode)

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
        self._driver.write(self.photo_diode_gain)


class HighPowerLaser(Laser):
    _CHANNELS: Final[int] = 3
    _DAC_CHANNELS: Final[int] = 2
    _DAC = typing.Annotated[tuple[int], 6]
    _DAC_REGISTER: Final[tuple[_DAC, _DAC]] = ((1 << 8, 1 << 9, 1 << 10, 1 << 11, 1 << 12, 1 << 13),
                                               (1 << 14, 1 << 15, 1 << 0, 1 << 1, 1 << 2, 1 << 3))
    _RESISTOR: Final[float] = 2.2e4
    _DIGITAL_POT: Final[float] = 1e4
    NUMBER_OF_STEPS: Final[int] = 1 << 7
    _PRE_RESISTOR: Final[float] = 1.6e3

    def __init__(self, driver: Driver):
        Laser.__init__(self, driver)
        self.config_path: str = f"{minipti.module_path}/hardware/configs/laser/high_power.json"
        self.configuration: Union[None, HighPowerLaserConfig] = None
        self._init = protocolls.ASCIIHex("CHI0000")
        self._set_voltage = protocolls.ASCIIHex("SHV0000")
        self._control_register = protocolls.ASCIIHex("SC10000")
        self._set_dac = [protocolls.ASCIIHex("SC30000"), protocolls.ASCIIHex("SC40000")]
        self._enable = protocolls.ASCIIHex("SHE0001")
        self.load_configuration()

    def initialize(self) -> None:
        self._init.value = 1
        self._initialized = True
        self._driver.write(self._init)

    @property
    def enabled(self) -> bool:
        return bool(self._enable.value)

    @enabled.setter
    def enabled(self, enabled: bool) -> None:
        self._enable.value = enabled
        self._driver.write(self._enable)

    @override
    def load_configuration(self) -> bool:
        with open(self.config_path) as config:
            try:
                loaded_config = json.load(config)
                self.configuration = dacite.from_dict(HighPowerLaserConfig, loaded_config["High Power Laser"])
                return True
            except (dacite.DaciteError, json.decoder.JSONDecodeError):
                self.configuration = HighPowerLaserConfig()
                return False

    @override
    def save_configuration(self) -> None:
        with open(self.config_path, "w") as configuration:
            laser = {"High Power Laser": dataclasses.asdict(self.configuration)}
            configuration.write(_json_parser.to_json(laser) + "\n")
            logging.info("Saved high power laser configuration in %s", self.config_path)

    @override
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
                    matrix |= HighPowerLaser._DAC_REGISTER[j][2 * i]
                elif self.configuration.DAC[j].pulsed_mode[i]:
                    matrix |= HighPowerLaser._DAC_REGISTER[j][2 * i + 1]
        self._control_register.value = matrix
        self._driver.write(self._control_register)

    @staticmethod
    def bit_to_voltage(bits: int) -> float:
        # 0.8 is an interpolation constant without any practical meaning.
        return 0.8 * HighPowerLaser._RESISTOR / (bits * HighPowerLaser._DIGITAL_POT / HighPowerLaser.NUMBER_OF_STEPS
                                                 + HighPowerLaser._PRE_RESISTOR) + 0.8

    @staticmethod
    def voltage_to_bit(voltage: float) -> int:
        return int((0.8 * HighPowerLaser._RESISTOR / (voltage - 0.8) - HighPowerLaser._PRE_RESISTOR)
                   * HighPowerLaser.NUMBER_OF_STEPS / HighPowerLaser._DIGITAL_POT)
