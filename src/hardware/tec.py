import dataclasses
import json
import typing

import dacite

import hardware
from dataclasses import dataclass

import json_parser


@dataclass
class Data:
    pass


@dataclass
class _PID:
    P_parameter: float
    I_parameter: typing.Annotated[list[float], 2]
    D_parameter: float


@dataclass
class _SystemParameter:
    setpoint_temperature: float
    loop_time: float
    reference_resistor: float
    max_power: float


@dataclass
class Tec:
    PID: _PID
    system_parameter: _SystemParameter


class Driver(hardware.serial.Driver):
    HARDWARE_ID = b"0003"
    NAME = "Tec"

    def __init__(self):
        hardware.serial.Driver.__init__(self)
        self.probe_laser = None  # type: None | Tec
        self.pump_laser = None  # type: None | Tec
        self.config_path = "hardware/configs/tec.json"

    @property
    def device_id(self):
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

    def set_pid_d_value(self):
        raise NotImplementedError("Implement me")

    @property
    def end_data_frame(self) -> int:
        return 0
