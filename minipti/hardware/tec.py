import dataclasses
import enum
import json
import logging
import os
import time
from dataclasses import dataclass

import dacite
from overrides import override

import minipti
from . import protocolls
from . import serial_device, _json_parser

ROOM_TEMPERATURE_CELSIUS = 23
ROOM_TEMPERATURE_KELVIN = 283.15


@dataclass
class Data:
    set_point: list[float]
    actual_temperature: list[float]


class Status:
    VALUE: int = 0
    TEXT: int = 1
    ERROR = [(0x0010, "Chip Error"),
             (0x0020, "Kt1: Open"),
             (0x0040, "Kt1 VCC shorted"),
             (0x0080, "Kt1 GND shorted"),
             (0x2000, "Kt2 Open"),
             (0x4000, "Kt2 VCC shorted"),
             (0x8000, "Kt2 GND shorted"),
             (0x0100, "TEC overcurrent"),
             (0x0200, "TEC overtemperature"),
             (0x0400, "PT1000 chip error")]


class TecDataIndex(enum.IntEnum):
    PELTIER_STATUS = 0
    PT1000_STATUS = 6
    SET_POINT = 7
    TEMPERATURE = 16


class Driver(serial_device.Driver):
    _HARDWARE_ID = b"0003"
    NAME = "Tec"
    CHANNELS = 2

    KEY_SLICE = 3

    def __init__(self):
        serial_device.Driver.__init__(self)
        self.tec = [Tec(1, self), Tec(2, self)]

    def startup(self):
        self.tec[0].apply_configuration()
        self.tec[1].apply_configuration()

    def clear(self):
        self.tec[0].enabled = False
        self.tec[1].enabled = False
        super().clear()

    @property
    @override
    def device_id(self) -> bytes:
        return Driver._HARDWARE_ID

    @property
    @override
    def device_name(self) -> str:
        return Driver.NAME

    @override
    def _process_data(self) -> None:
        while self.connected.is_set():
            self.encode_data()

    @override
    def _encode(self, data: str) -> None:
        if data[0] == "S":
            written = protocolls.ASCIIMultimap(self.last_written_message)
            data = protocolls.ASCIIMultimap(data + "\n")
            if data.key != written.key:
                logging.error("Received message with as key %s, expected key %s", data.key, data.key)
            elif data.value == "PARAMERROR":
                logging.error("Value %s is not valid", data.value)
            elif data.value == "INDEXERROR":
                logging.error("Index %s is not valid", written.index)
            else:
                logging.debug("Command %s successfully applied", data)
            self._ready_write.set()
        elif data[0] == "T":
            data_frame = data.split("\t")[Driver._START_DATA_FRAME:]
            status_byte_frame = int(data_frame[TecDataIndex.PT1000_STATUS])
            for error in Status.ERROR:
                if error[Status.VALUE] & status_byte_frame:
                    logging.error("Got \"%s\" from TEC Driver", error[Status.TEXT])
            actual_temperature: list[float] = [0, 0]
            setpoint_temperature: list[float] = [0, 0]
            for i in range(Driver.CHANNELS):
                actual_temperature[i] = Tec.kelvin_to_celsisus(float(data_frame[TecDataIndex.TEMPERATURE + i]))
                setpoint_temperature[i] = Tec.kelvin_to_celsisus(float(data_frame[TecDataIndex.SET_POINT + i]))
            self.data.put(Data(setpoint_temperature, actual_temperature))


class Commands:
    def __init__(self, channel: int):
        self.set_setpoint = protocolls.ASCIIMultimap(key="SetT_InK", index=channel, value=ROOM_TEMPERATURE_KELVIN)
        self.set_p_gain = protocolls.ASCIIMultimap(key="SetPID_KP", index=channel, value=0)
        self.set_i_gain = protocolls.ASCIIMultimap(key="SetPID_KI", index=channel, value=0)
        self.set_d_gain = protocolls.ASCIIMultimap(key="SetPID_KD", index=channel, value=0)
        self.set_max_output_power = protocolls.ASCIIMultimap(key="SetPID_MaxPWM", index=channel, value=0)
        self.set_loop_time_ms = protocolls.ASCIIMultimap(key="SetPID_LoopTimeMSecs", index=channel, value=0)
        self.set_ntc_dac = protocolls.ASCIIMultimap(key="SetNTCDAC_CurSetpoint", index=channel, value=0)
        self.set_enable = protocolls.ASCIIMultimap(key="SetPID_Active", index=channel, value=0)


class Tec:
    _NTC_DAC_CALIBRATION_VALUE = 800

    MIN_LOOP_TIME = 10
    MAX_LOOP_TIME = 5000
    MIN_POWER = 0
    MAX_POWER = 1

    def __init__(self, channel: int, driver: Driver):
        self.commands = Commands(channel - 1)
        self.channel = channel
        self.commands.set_ntc_dac.value = Tec._NTC_DAC_CALIBRATION_VALUE
        self.config_path = f"{minipti.module_path}/hardware/configs/tec/channel_{channel}.json"
        self.driver = driver
        self._enabled = False
        self.configuration = Configuration(pid=_PID(0, 0, 0),
                                           system_parameter=_SystemParameter(ROOM_TEMPERATURE_CELSIUS,
                                                                             Tec.MAX_LOOP_TIME, 0))
        self.load_configuration()

    @property
    def enabled(self) -> bool:
        return self._enabled

    @enabled.setter
    def enabled(self, enable: bool) -> None:
        self._enabled = enable
        self.commands.set_enable.value = int(enable)
        self.driver.write(self.commands.set_enable)

    def set_ntc_dac(self) -> None:
        self.driver.write(self.commands.set_ntc_dac)

    def load_configuration(self) -> None:
        if not os.path.exists(self.config_path):
            logging.warning("Config File not found")
            logging.info("Creating a new file")
            self.configuration = Configuration(pid=_PID(0, 0, 0),
                                               system_parameter=_SystemParameter(ROOM_TEMPERATURE_CELSIUS,
                                                                                 Tec.MAX_LOOP_TIME, 0))
            self.save_configuration()
        else:
            with open(self.config_path) as config:
                try:
                    loaded_config = json.load(config)
                    self.configuration = dacite.from_dict(Configuration, loaded_config["Tec"])
                except (json.decoder.JSONDecodeError, dacite.WrongTypeError, dacite.exceptions.MissingValueError):
                    # Config file corrupted or types are wrong
                    logging.warning("Config File was corrupted or wrong")
                    logging.info("Creating a new file")
                    self.configuration = Configuration(pid=_PID(0, 0, 0),
                                                       system_parameter=_SystemParameter(ROOM_TEMPERATURE_CELSIUS,
                                                                                         Tec.MAX_LOOP_TIME, 0))
                    self.save_configuration()

    def save_configuration(self) -> None:
        with open(self.config_path, "w") as configuration:
            tec = {f"Tec": dataclasses.asdict(self.configuration)}
            configuration.write(_json_parser.to_json(tec) + "\n")
            logging.info("Saved TEC configuration of channel %d in %s", self.channel, self.config_path)

    def apply_configuration(self) -> None:
        self.set_pid_d_gain()
        self.set_pid_p_gain()
        self.set_pid_i_gain()
        self.set_loop_time_ms()
        self.set_max_power()
        self.set_setpoint_temperature_value()

    def set_pid_d_gain(self) -> None:
        self.commands.set_d_gain.value = self.configuration.pid.derivative_value
        self.driver.write(self.commands.set_d_gain)

    def set_pid_p_gain(self) -> None:
        self.commands.set_p_gain.value = self.configuration.pid.proportional_value
        self.driver.write(self.commands.set_p_gain)

    def set_pid_i_gain(self) -> None:
        self.commands.set_i_gain.value = self.configuration.pid.integral_value
        self.driver.write(self.commands.set_i_gain)

    def set_setpoint_temperature_value(self) -> None:
        setpoint_temperature: float = Tec.celsius_to_kelvin(self.configuration.system_parameter.setpoint_temperature)
        self.commands.set_setpoint.value = setpoint_temperature
        self.driver.write(self.commands.set_setpoint)

    def set_loop_time_ms(self) -> None:
        if self.configuration.system_parameter.loop_time < Tec.MIN_LOOP_TIME:
            logging.error("%s ms falls below the minimum loop time of %s ms",
                          self.configuration.system_parameter.loop_time, Tec.MIN_LOOP_TIME)
            logging.warning("Setting it to minimum value of %s ms", Tec.MIN_LOOP_TIME)
            self.configuration.system_parameter.loop_time = Tec.MIN_LOOP_TIME
        elif self.configuration.system_parameter.loop_time > Tec.MAX_LOOP_TIME:
            logging.error("%s ms exceeds the maxium loop time of %s ms",
                          self.configuration.system_parameter.loop_time, Tec.MAX_LOOP_TIME)
            logging.warning("Setting it to maximum value of %s ms", Tec.MAX_LOOP_TIME)
            self.configuration.system_parameter.loop_time = Tec.MAX_LOOP_TIME
        self.commands.set_loop_time_ms.value = self.configuration.system_parameter.loop_time
        self.driver.write(self.commands.set_loop_time_ms)

    def set_max_power(self) -> None:
        if self.configuration.system_parameter.max_power > Tec.MAX_POWER:
            self.configuration.system_parameter.max_power = Tec.MAX_POWER
        elif self.configuration.system_parameter.max_power < Tec.MIN_POWER:
            self.configuration.system_parameter.max_power = Tec.MIN_POWER
        self.commands.set_max_output_power.value = self.configuration.system_parameter.max_power
        self.driver.write(self.commands.set_max_output_power)

    @staticmethod
    def kelvin_to_celsisus(temperature_K: float) -> float:
        """
        Formula follows from definition, see also here
        https://en.wikipedia.org/wiki/Conversion_of_scales_of_temperature#Kelvin_scale
        "Celsius to Kelvin"
        """
        return temperature_K - 273.15

    @staticmethod
    def celsius_to_kelvin(temperature_C: float) -> float:
        """
        Formula follows from definition, see also here
        https://en.wikipedia.org/wiki/Conversion_of_scales_of_temperature#Celsius_scale
        "Kelvin to Celsius"
        """
        return temperature_C + 273.15


@dataclass
class _PID:
    proportional_value: float
    integral_value: float
    derivative_value: float


@dataclass
class _SystemParameter:
    setpoint_temperature: float
    loop_time: int
    max_power: float


@dataclass
class Configuration:
    pid: _PID
    system_parameter: _SystemParameter
