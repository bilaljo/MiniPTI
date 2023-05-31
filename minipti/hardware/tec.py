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


@dataclass
class Mode:
    heating: bool
    cooling: bool


@dataclass
class _PID:
    proportional_value: float
    integral_value: typing.Annotated[list[float], 2]
    derivative_value: float


@dataclass
class _SystemParameter:
    setpoint_temperature: float
    loop_time: float
    reference_resistor: float
    max_power: float


@dataclass
class Tec:
    mode: Mode
    pid: _PID
    system_parameter: _SystemParameter


class TemperatureElement(enum.Enum):
    PT1000 = 0
    KT = 1
    NTC = 2


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
    ERROR = [
        (0x0010, "Chip Error"), (0x0020, "Kt1: Open"), (0x0040, "Kt1 VCC shorted"),
        (0x0080, "Kt1 GND shorted"), (0x2000, "Kt2 Open"), (0x4000, "Kt2 VCC shorted"),
        (0x8000, "Kt2 GND shorted"), (0x0100, "TEC overcurrent"), (0x0200, "TEC overtemperature"),
        (0x0400, "Pt100b chip error")
    ]


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
        self.used_laser: str = laser
        self.config_path: str = f"{os.path.dirname(__file__)}/configs/tec.json"
        self.temperature_element: TemperatureElement = TemperatureElement.NTC
        self._tec_probe_laser_enabled: bool = False
        self._tec_pump_laser_enabled: bool = False
        self.load_config()

    def __getitem__(self, item: str):
        if item == "Pump Laser" or item == "Probe Laser":
            return getattr(self, item.replace(" ", "_").casefold())
        raise KeyError("Can only subscribe Pump Laser or Probe Laser")

    @property
    def device_id(self) -> bytes:
        return Driver.HARDWARE_ID

    @property
    def device_name(self):
        return Driver.NAME

    def load_config(self) -> None:
        with open(self.config_path) as config:
            loaded_config = json.load(config)
            self.pump_laser = dacite.from_dict(Tec, loaded_config["Pump Laser"])
            self.probe_laser = dacite.from_dict(Tec, loaded_config["Probe Laser"])

    def save_configuration(self) -> None:
        with open(self.config_path, "w") as configuration:
            lasers = {"Pump Laser": dataclasses.asdict(self.pump_laser),
                      "Probe Laser": dataclasses.asdict(self.probe_laser)}
            configuration.write(json_parser.to_json(lasers) + "\n")

    def apply_configuration(self) -> None:
        pass

    def set_pid_d_value(self, laser: str):
        tec: Tec = self[laser]
        d_value_hex = f"{tec.pid.derivative_value:0{Driver._NUMBER_OF_DIGITS}X}"
        channel = 1 if laser == "Pump Laser" else 2
        self.write(f"SD{channel}" + d_value_hex)

    def set_pid_p_value(self, laser: str):
        tec: Tec = self[laser]
        p_value_hex = f"{tec.pid.proportional_value:0{Driver._NUMBER_OF_DIGITS}X}"
        channel = 1 if laser == "Pump Laser" else 2
        self.write(f"SP{channel}" + p_value_hex)

    def set_pid_i_value(self, laser: str, i: int):
        tec: Tec = self[laser]
        i_value_hex = f"{tec.pid.integral_value[i]:0{Driver._NUMBER_OF_DIGITS}X}"
        # Formula is defined by hardware protocol
        channel = 1 + 2 * i if laser == "Pump Laser" else 2 + 2 * i
        self.write(f"SI{channel}" + i_value_hex)

    def set_setpoint_temperature_value(self, laser: str):
        tec: Tec = self[laser]
        setpoint_temperature: float = tec.system_parameter.setpoint_temperature
        # Given by hardware; °C -> Bit
        setpoint_temperature = setpoint_temperature * 100 + 32.768
        setpoint_temperature_hex = f"{setpoint_temperature:0{Driver._NUMBER_OF_DIGITS}X}"
        channel = 1 if laser == "Pump Laser" else 2
        self.write(f"SS{channel}" + setpoint_temperature_hex)

    def set_loop_time_value(self, laser: str):
        tec: Tec = self[laser]
        loop_time_value_hex = f"{tec.system_parameter.loop_time:0{Driver._NUMBER_OF_DIGITS}X}"
        channel = 1 if laser == "Pump Laser" else 2
        self.write(f"SR{channel}" + loop_time_value_hex)

    def set_reference_resistor_value(self, laser: str):
        tec: Tec = self[laser]
        reference_resistor_value = tec.system_parameter.reference_resistor * 10
        reference_resistor_value_hex = f"{reference_resistor_value:0{Driver._NUMBER_OF_DIGITS}X}"
        channel = 1 if laser == "Pump Laser" else 2
        self.write(f"SC{channel}" + reference_resistor_value_hex)

    def set_max_power_value(self, laser: str):
        tec: Tec = self[laser]
        max_power_value_hex = f"{tec.system_parameter.max_power:0{Driver._NUMBER_OF_DIGITS}X}"
        channel = 1 if laser == "Pump Laser" else 2
        self.write(f"SO{channel}" + max_power_value_hex)

    def set_mode(self, laser: str) -> None:
        channel = 1 if laser == "Pump Laser" else 2
        mode = 1 if self[laser].mode.cooling else 2
        self.write(f"SL{channel}000{mode}")

    @property
    def pump_laser_enabled(self) -> bool:
        return self._tec_pump_laser_enabled

    @pump_laser_enabled.setter
    def pump_laser_enabled(self, state: bool) -> None:
        if state:
            self.set_mode("Probe Laser")
            self.write(f"SL10001")
            self._tec_pump_laser_enabled = True
        else:
            self.write(f"SL10000")
            self._tec_pump_laser_enabled = False

    @property
    def probe_laser_enabled(self) -> bool:
        return self._tec_probe_laser_enabled

    @probe_laser_enabled.setter
    def probe_laser_enabled(self, state: bool) -> None:
        if state:
            self.set_mode("Probe Laser")
            self.write(f"SL20001")
            self._tec_probe_laser_enabled = True
        else:
            self.write(f"SL20000")
            self._tec_probe_laser_enabled = False

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
                logging.error(f"Invalid command {received}")
                self.ready_write.set()
            elif identifier == "S" or identifier == "C":
                last_written = self.last_written_message
                if received != last_written and received != last_written.capitalize():
                    logging.error(f"Received message {received} message, expected {last_written}")
                else:
                    logging.debug(f"Command {received} successfully applied")
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
                if self.temperature_element == TemperatureElement.PT1000:
                    actual_temperature: Temperature = Temperature(
                        pump_laser=float(data_frame[_TemperatureIndex.PT100B[Driver.PUMP_LASER]]),
                        probe_laser=float(data_frame[_TemperatureIndex.PT100B[Driver.PROBE_LASER]]))
                elif self.temperature_element == TemperatureElement.KT:
                    actual_temperature: Temperature = Temperature(
                        pump_laser=float(data_frame[_TemperatureIndex.KT[Driver.PUMP_LASER]]),
                        probe_laser=float(data_frame[_TemperatureIndex.KT[Driver.PROBE_LASER]]))
                elif self.temperature_element == TemperatureElement.NTC:
                    actual_temperature: Temperature = Temperature(
                        pump_laser=float(data_frame[_TemperatureIndex.NTC[Driver.PUMP_LASER]]),
                        probe_laser=float(data_frame[_TemperatureIndex.NTC[Driver.PROBE_LASER]]))
                else:
                    raise ValueError("Invalid Temperatur Element")
                actual_temperature.probe_laser = (actual_temperature.probe_laser - 32.768) / 100
                actual_temperature.pump_laser = (actual_temperature.probe_laser - 32.768) / 100
                self.data.put(Data(set_point, actual_temperature))
            else:  # Broken data frame without header char
                logging.error("Received invalid package without header")
                self.ready_write.set()
                continue
