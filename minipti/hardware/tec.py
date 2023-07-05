import dataclasses
import json
import logging
import os
import typing
from dataclasses import dataclass

import dacite

from . import serial_device
from .. import json_parser


ROOM_TEMPERATURE_CELSIUS = 23


@dataclass
class Data:
    set_point: [float, float]
    actual_temperature: [float, float]


class _TemperatureIndex(typing.NamedTuple):
    SET_POINT = [7, 8]
    PT100B = [0, 1]
    KT = [4, 5]
    NTC = [16, 17]


@dataclass(frozen=True)
class Status:
    VALUE = 0
    TEXT = 1
    ERROR = [(0x0010, "Chip Error"), (0x0020, "Kt1: Open"), (0x0040, "Kt1 VCC shorted"),
             (0x0080, "Kt1 GND shorted"), (0x2000, "Kt2 Open"), (0x4000, "Kt2 VCC shorted"),
             (0x8000, "Kt2 GND shorted"), (0x0100, "TEC overcurrent"), (0x0200, "TEC overtemperature"),
             (0x0400, "Pt100b chip error")]


class Driver(serial_device.Driver):
    _HARDWARE_ID = b"0003"
    NAME = "Tec"

    def __init__(self):
        serial_device.Driver.__init__(self)
        self.tec = [Tec(1, self), Tec(2, self)]

    @property
    def device_id(self) -> bytes:
        return Driver._HARDWARE_ID

    @property
    def device_name(self) -> str:
        return Driver.NAME

    def open(self) -> None:
        super().open()
        self.tec[0].set_ntc_dac()
        self.tec[1].set_ntc_dac()

    def _process_data(self) -> None:
        while self.connected.is_set():
            self._encode_data()

    @staticmethod
    def _bit_to_celsisus(bit_stream: str) -> float:
        return float(bit_stream) / 100

    def _encode_data(self) -> None:
        try:
            received_data: str = self.get_data()
        except OSError:
            return
        for received in received_data.split(Driver.TERMINATION_SYMBOL):
            if not received:
                continue
            identifier = received[0]
            if identifier == "N":
                logging.error("Invalid command %s", received)
                self.ready_write.set()
            elif identifier == "S" or identifier == "C":
                last_written = self.last_written_message[:-1]
                if received != last_written and received != last_written.capitalize():
                    logging.error("Received message %s message, expected %s", received, last_written)
                else:
                    logging.debug("Command %s successfully applied", received)
                self.ready_write.set()
            elif identifier == "T":
                data_frame = received.split("\t")[Driver._START_DATA_FRAME:]
                status_byte_frame = int(data_frame[13])  # 13 is the index according to the protocol
                for error in Status.ERROR:
                    if error[Status.VALUE] & status_byte_frame:
                        logging.error("Got \"%s\" from TEC Driver", error[Status.TEXT])
                set_point = [Driver._bit_to_celsisus(data_frame[_TemperatureIndex.SET_POINT[0]]),
                             Driver._bit_to_celsisus(data_frame[_TemperatureIndex.SET_POINT[1]])]
                if self.tec[0].configuration.temperature_element.PT1000:
                    actual_temperature = [float(data_frame[_TemperatureIndex.PT100B[0]]),
                                          float(data_frame[_TemperatureIndex.PT100B[1]])]
                elif self.tec[0].configuration.temperature_element.KT:
                    actual_temperature = [float(data_frame[_TemperatureIndex.KT[0]]),
                                          float(data_frame[_TemperatureIndex.KT[1]])]
                elif self.tec[0].configuration.temperature_element.NTC:
                    actual_temperature = [float(data_frame[_TemperatureIndex.NTC[0]]),
                                          float(data_frame[_TemperatureIndex.NTC[1]])]
                else:
                    raise ValueError("Invalid Temperature Element")
                self.data.put(Data(set_point, actual_temperature))
            else:  # Broken data frame without header char
                logging.error("Received invalid package without header")
                self.ready_write.set()
                continue


@dataclass
class _TemperatureElement:
    PT1000: bool
    KT: bool
    NTC: bool


@dataclass
class _Mode:
    heating: bool
    cooling: bool


@dataclass
class _PID:
    proportional_value: int
    integral_value: typing.Annotated[list[int], 2]
    derivative_value: int


@dataclass
class _SystemParameter:
    setpoint_temperature: float
    loop_time: int
    reference_resistor: float
    max_power: int


@dataclass
class Configuration:
    temperature_element: _TemperatureElement
    mode: _Mode
    pid: _PID
    system_parameter: _SystemParameter


class Commands:
    def __init__(self, channel_number: int):
        self.set_setpoint = serial_device.SerialStream(f"SS{channel_number}0000")
        self.set_p_value = serial_device.SerialStream(f"SP{channel_number}0000")
        self.set_i_value = [serial_device.SerialStream(f"SI{channel_number}0000"),
                            serial_device. SerialStream(f"SI{channel_number + 2}0000")]
        self.set_d_value = serial_device.SerialStream(f"SD{channel_number}0000")
        self.set_control_loop = serial_device.SerialStream(f"SL{channel_number}0000")
        self.set_fan_control = serial_device. SerialStream(f"SF{channel_number}0000")
        self.set_max_output_power = serial_device.SerialStream(f"SO{channel_number}0000")
        self.set_peltier_mode = serial_device.SerialStream(f"SM{channel_number}0000")
        self.set_loop_interval = serial_device.SerialStream(f"SR{channel_number}0000")
        self.set_ref_resistor = serial_device.SerialStream(f"SC{channel_number}0000")
        self.set_ntc_dac = serial_device.SerialStream(f"SN{channel_number}0000")


class Tec:
    _COOLING = 1
    _HEATING = 2
    _MIN_LOOP_TIME = 25  # 25 ms
    _MAX_LOOP_TIME = 5000  # 5 s
    MIN_PID_VALUE = 0
    MAX_PID_VALUE = 999
    _NTC_DAC_CALIBRATION_VALUE = 800

    def __init__(self, channel_number: int, driver: Driver):
        self.configuration: typing.Union[Configuration, None] = None
        self.channel_number = channel_number
        self.commands = Commands(self.channel_number)
        self.commands.set_ntc_dac.value = Tec._NTC_DAC_CALIBRATION_VALUE
        self.config_path: str = f"{os.path.dirname(__file__)}/configs/tec/channel_{self.channel_number}.json"
        self.driver = driver
        self._enabled = False
        self.load_configuration()

    @property
    def enabled(self) -> bool:
        return self._enabled

    @enabled.setter
    def enabled(self, enable: bool) -> None:
        self._enabled = enable
        self.commands.set_control_loop.value = enable
        self.commands.set_fan_control.value = enable
        self.driver.write(self.commands.set_control_loop)
        self.driver.write(self.commands.set_fan_control)

    def set_ntc_dac(self) -> None:
        self.driver.write(self.commands.set_ntc_dac)

    def load_configuration(self) -> None:
        if not os.path.exists(self.config_path):
            logging.warning("Config File not found")
            logging.info("Creating a new file")
            self._create_configuration()
            self.save_configuration()
        else:
            with open(self.config_path) as config:
                try:
                    loaded_config = json.load(config)
                    self.configuration = dacite.from_dict(Configuration, loaded_config["Tec"])
                except (json.decoder.JSONDecodeError, dacite.exceptions.WrongTypeError):
                    # Config file corrupted or types are wrong
                    logging.warning("Config File was corrupted or wrong")
                    logging.info("Creating a new file")
                    self._create_configuration()
                    self.save_configuration()

    def _create_configuration(self) -> None:
        self.configuration = Configuration(temperature_element=_TemperatureElement(PT1000=False, KT=False, NTC=True),
                                           mode=_Mode(heating=False, cooling=True),
                                           pid=_PID(proportional_value=0, integral_value=[0, 0], derivative_value=0),
                                           system_parameter=_SystemParameter(ROOM_TEMPERATURE_CELSIUS,
                                                                             Tec._MAX_LOOP_TIME, 0, 0))

    def save_configuration(self) -> None:
        with open(self.config_path, "w") as configuration:
            lasers = {f"Tec": dataclasses.asdict(self.configuration)}
            configuration.write(json_parser.to_json(lasers) + "\n")

    def apply_configuration(self) -> None:
        self.set_pid_d_value()
        self.set_pid_p_value()
        self.set_pid_i_value(i=0)
        self.set_pid_i_value(i=1)
        self.set_loop_time_value()
        if not self.configuration.temperature_element.NTC:
            self.set_reference_resistor_value()
        self.set_max_power_value()
        self.set_mode()
        self.set_setpoint_temperature_value()

    @staticmethod
    def _check_pid_boundaries(value: int) -> typing.Union[int, None]:
        if value < Tec.MIN_PID_VALUE:
            logging.error("%s falls below the minimum PID value of %s",
                          value, Tec.MIN_PID_VALUE)
            logging.warning("Setting it to minimum value of %s", Tec.MIN_PID_VALUE)
            return Tec.MIN_PID_VALUE
        elif value > Tec.MAX_PID_VALUE:
            logging.error("%s exceeds the maximum PID value of %s",
                          value, Tec.MAX_PID_VALUE)
            logging.warning("Setting it to minimum value of %s", Tec.MAX_PID_VALUE)
            return Tec.MAX_PID_VALUE
        return None

    def set_pid_d_value(self) -> None:
        if res := Tec._check_pid_boundaries(self.configuration.pid.derivative_value) is not None:
            self.configuration.pid.derivative_value = res
        self.commands.set_d_value.value = self.configuration.pid.derivative_value
        self.driver.write(self.commands.set_d_value)

    def set_pid_p_value(self) -> None:
        if res := Tec._check_pid_boundaries(self.configuration.pid.proportional_value) is not None:
            self.configuration.pid.proportional_value = res
        self.commands.set_p_value.value = self.configuration.pid.proportional_value
        self.driver.write(self.commands.set_p_value)

    def set_pid_i_value(self, i: int) -> None:
        if res := Tec._check_pid_boundaries(self.configuration.pid.integral_value[i]) is not None:
            self.configuration.pid.integral_value[i] = res
        self.commands.set_i_value[i].value = self.configuration.pid.integral_value[i]
        self.driver.write(self.commands.set_i_value[i])

    def set_setpoint_temperature_value(self,) -> None:
        # Given by hardware; °C -> Bit
        setpoint_temperature: int = int(self.configuration.system_parameter.setpoint_temperature * 100 + 32768)
        self.commands.set_setpoint.value = setpoint_temperature
        self.driver.write(self.commands.set_setpoint)

    def set_loop_time_value(self) -> None:
        if self.configuration.system_parameter.loop_time < Tec._MIN_LOOP_TIME:
            logging.error("%s ms falls below the minimum loop time of %s ms",
                          self.configuration.system_parameter.loop_time, Tec._MIN_LOOP_TIME)
            logging.warning("Setting it to minimum value of %s ms", Tec._MIN_LOOP_TIME)
            self.configuration.system_parameter.loop_time = Tec._MIN_LOOP_TIME
        elif self.configuration.system_parameter.loop_time > Tec._MAX_LOOP_TIME:
            logging.error("%s ms exceeds the maxium loop time of %s ms",
                          self.configuration.system_parameter.loop_time, Tec._MAX_LOOP_TIME)
            logging.warning("Setting it to maximum value of %s ms", Tec._MAX_LOOP_TIME)
            self.configuration.system_parameter.loop_time = Tec._MAX_LOOP_TIME
        self.commands.set_loop_interval.value = self.configuration.system_parameter.loop_time
        self.driver.write(self.commands.set_loop_interval)

    def set_reference_resistor_value(self) -> None:
        self.commands.set_ref_resistor.value = int(self.configuration.system_parameter.reference_resistor * 10)
        self.driver.write(self.commands.set_ref_resistor)

    def set_max_power_value(self) -> None:
        self.commands.set_max_output_power.value = self.configuration.system_parameter.max_power
        self.driver.write(self.commands.set_max_output_power)

    def set_mode(self) -> None:
        if self.configuration.mode.heating:
            self.commands.set_control_loop.value = Tec._HEATING
        else:
            self.commands.set_control_loop.value = Tec._COOLING
        self.driver.write(self.commands.set_control_loop)
