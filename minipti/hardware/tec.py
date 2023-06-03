import dataclasses
import enum
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
class Tec:
    temperature_element: _TemperatureElement
    mode: _Mode
    pid: _PID
    system_parameter: _SystemParameter


@dataclass
class Temperature:
    pump_laser: float
    probe_laser: float

    def __getitem__(self, item: str):
        if item == "Pump Laser" or item == "Probe Laser":
            return getattr(self, item.replace(" ", "_").casefold())
        else:
            raise KeyError("Can only subscribe Pump Laser or Probe Laser")


@dataclass
class Data:
    set_point: Temperature
    actual_temperature: Temperature


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


class TecChannel(enum.IntEnum):
    PUMP_LASER = 1
    PROBE_LASER = 2


class TecMode(enum.IntEnum):
    COOLING = 1
    HEATING = 2


class Driver(serial_device.Driver):
    HARDWARE_ID = b"0003"
    NAME = "Tec"
    PROBE_LASER = 0
    PUMP_LASER = 1
    MIN_LOOP_TIME = 25  # 25 ms
    MAX_LOOP_TIME = 5000  # 5 s
    _NUMBER_OF_DIGITS = serial_device.Driver.NUMBER_OF_HEX_BYTES

    def __init__(self, laser=""):
        serial_device.Driver.__init__(self)
        self.probe_laser: typing.Union[Tec, None] = None
        self.pump_laser: typing.Union[Tec, None] = None
        self.laser: str = laser
        self.tec_channel = TecChannel.PUMP_LASER if self.laser == "Pump Laser" else TecChannel.PROBE_LASER
        self.config_path: str = f"{os.path.dirname(__file__)}/configs/tec.json"
        self._tec_probe_laser_enabled: bool = False
        self._tec_pump_laser_enabled: bool = False
        self.load_configuration()

    def __getitem__(self, laser: str):
        if laser == "Pump Laser" or laser == "Probe Laser":
            return getattr(self, laser.replace(" ", "_").casefold())
        raise KeyError("Can only subscribe Pump Laser or Probe Laser")

    def __setitem__(self, laser: str, value: Tec):
        if laser == "Pump Laser" or laser == "Probe Laser":
            return setattr(self, laser.replace(" ", "_").casefold(), value)
        raise KeyError("Can only subscribe Pump Laser or Probe Laser")

    @property
    def device_id(self) -> bytes:
        return Driver.HARDWARE_ID

    @property
    def device_name(self):
        return Driver.NAME

    def load_configuration(self) -> None:
        if not os.path.exists(self.config_path):
            logging.warning("Config File not found")
            logging.info("Creating a new file")
            self._create_configuration("Pump Laser")
            self._create_configuration("Probe Laser")
            self.save_configuration()
        else:
            with open(self.config_path) as config:
                try:
                    loaded_config = json.load(config)
                    self.pump_laser = dacite.from_dict(Tec, loaded_config["Pump Laser"])
                    self.probe_laser = dacite.from_dict(Tec, loaded_config["Probe Laser"])
                except (json.decoder.JSONDecodeError, dacite.exceptions.WrongTypeError):
                    # Config file corrupted or types are wrong
                    logging.warning("Config File was corrupted or wrong")
                    logging.info("Creating a new file")
                    self._create_configuration("Pump Laser")
                    self._create_configuration("Probe Laser")
                    self.save_configuration()

    def _create_configuration(self, laser: str) -> None:
        self[laser] = Tec(mode=_Mode(heating=False, cooling=True),
                          pid=_PID(proportional_value=0, integral_value=[0, 0], derivative_value=0),
                          system_parameter=_SystemParameter(ROOM_TEMPERATURE_CELSIUS, Driver.MAX_LOOP_TIME, 0, 0))

    def save_configuration(self) -> None:
        with open(self.config_path, "w") as configuration:
            lasers = {"Pump Laser": dataclasses.asdict(self.pump_laser),
                      "Probe Laser": dataclasses.asdict(self.probe_laser)}
            configuration.write(json_parser.to_json(lasers) + "\n")

    def apply_configuration(self) -> None:
        for laser in ["Pump Laser", "Probe Laser"]:
            self.set_pid_d_value()
            self.set_pid_p_value()
            self.set_pid_i_value(i=0)
            self.set_pid_i_value(i=1)
            self.set_loop_time_value()
            if not self[self.laser].temperature_element.NTC:
                self.set_reference_resistor_value()
            self.set_max_power_value()
            self.set_mode()
            self.set_setpoint_temperature_value()

    def set_pid_d_value(self) -> None:
        tec: Tec = self[self.laser]
        d_value_hex = f"{tec.pid.derivative_value:0{Driver._NUMBER_OF_DIGITS}X}"
        self.write(f"SD{self.tec_channel}" + d_value_hex)

    def set_pid_p_value(self) -> None:
        tec: Tec = self[self.laser]
        p_value_hex = f"{tec.pid.proportional_value:0{Driver._NUMBER_OF_DIGITS}X}"
        self.write(f"SP{self.tec_channel}" + p_value_hex)

    def set_pid_i_value(self, i: int) -> None:
        tec: Tec = self[self.laser]
        i_value_hex = f"{tec.pid.integral_value[i]:0{Driver._NUMBER_OF_DIGITS}X}"
        self.write(f"SI{self.tec_channel}" + i_value_hex)

    def set_setpoint_temperature_value(self,) -> None:
        tec: Tec = self[self.laser]
        # Given by hardware; °C -> Bit
        setpoint_temperature: int = int(tec.system_parameter.setpoint_temperature * 100 + 32.768)
        setpoint_temperature_hex: str = f"{setpoint_temperature:0{Driver._NUMBER_OF_DIGITS}X}"
        self.write(f"SS{self.tec_channel}" + setpoint_temperature_hex)

    def set_loop_time_value(self) -> None:
        tec: Tec = self[self.laser]
        loop_time_value_hex: str = f"{tec.system_parameter.loop_time:0{Driver._NUMBER_OF_DIGITS}X}"
        self.write(f"SR{self.tec_channel}" + loop_time_value_hex)

    def set_reference_resistor_value(self) -> None:
        tec: Tec = self[self.laser]
        reference_resistor_value = int(tec.system_parameter.reference_resistor * 10)
        reference_resistor_value_hex = f"{reference_resistor_value:0{Driver._NUMBER_OF_DIGITS}X}"
        self.write(f"SC{self.tec_channel}" + reference_resistor_value_hex)

    def set_max_power_value(self) -> None:
        tec: Tec = self[self.laser]
        max_power_value_hex = f"{tec.system_parameter.max_power:0{Driver._NUMBER_OF_DIGITS}X}"
        self.write(f"SO{self.tec_channel}" + max_power_value_hex)

    def set_mode(self) -> None:
        if self[self.laser].mode.heating:
            self.write(f"SL{self.tec_channel}" + f"000{TecMode.HEATING}")
        else:
            self.write(f"SL{self.tec_channel}" + f"000{TecMode.COOLING}")

    @property
    def enabled(self) -> bool:
        if self.laser == "Pump Laser":
            return self._tec_pump_laser_enabled
        else:
            return self._tec_probe_laser_enabled

    @enabled.setter
    def enabled(self, enable) -> None:
        if self.laser == "Pump Laser":

    @property
    def pump_laser_enabled(self) -> bool:
        return self._tec_pump_laser_enabled


    def _enable(self, state: bool) -> None:
        if state:
            self.set_mode()
            self.write(f"SL{self.tec_channel}0001")
            self._enabled = True
        else:
            self.write(f"SL{self.tec_channel}0000")
            self._enabled = False

    def _process_data(self) -> None:
        while self.connected.is_set():
            self.encode_data()

    def encode_data(self) -> None:
        received_data: str = self.received_data.get(block=True)
        for received in received_data.split(Driver.TERMINATION_SYMBOL):
            if not received:
                continue
            identifier = received[0]
            if identifier == "N":
                logging.error("Invalid command %s", received)
                self.ready_write.set()
            elif identifier == "S" or identifier == "C":
                last_written = self.last_written_message
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
                set_point: Temperature = Temperature(
                    pump_laser=float(data_frame[_TemperatureIndex.SET_POINT[Driver.PUMP_LASER]]),
                    probe_laser=float(data_frame[_TemperatureIndex.SET_POINT[Driver.PROBE_LASER]]))
                if self.pump_laser.temperature_element.PT1000:
                    actual_temperature: Temperature = Temperature(
                        pump_laser=float(data_frame[_TemperatureIndex.PT100B[Driver.PUMP_LASER]]),
                        probe_laser=float(data_frame[_TemperatureIndex.PT100B[Driver.PROBE_LASER]]))
                elif self.pump_laser.temperature_element.KT:
                    actual_temperature: Temperature = Temperature(
                        pump_laser=float(data_frame[_TemperatureIndex.KT[Driver.PUMP_LASER]]),
                        probe_laser=float(data_frame[_TemperatureIndex.KT[Driver.PROBE_LASER]]))
                elif not self.pump_laser.temperature_element.NTC:
                    actual_temperature: Temperature = Temperature(
                        pump_laser=float(data_frame[_TemperatureIndex.NTC[Driver.PUMP_LASER]]),
                        probe_laser=float(data_frame[_TemperatureIndex.NTC[Driver.PROBE_LASER]]))
                else:
                    raise ValueError("Invalid Temperature Element")
                actual_temperature.probe_laser /= 100
                actual_temperature.pump_laser /= 100
                self.data.put(Data(set_point, actual_temperature))
            else:  # Broken data frame without header char
                logging.error("Received invalid package without header")
                self.ready_write.set()
                continue
