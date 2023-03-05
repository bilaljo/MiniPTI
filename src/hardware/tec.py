import typing

import hardware
from dataclasses import dataclass


@dataclass
class Data:
    pass


@dataclass
class _PID:
    p_parameter: float
    i_parameter: typing.Annotated[list[float], 2]
    d_parameter: float


@dataclass
class _SystemParameter:
    setpoint_temperatur: float
    loop_time: float
    reference_resistor: float
    max_power: float


@dataclass
class Tec:
    pid: _PID
    sytem_parameter: _SystemParameter


class Driver(hardware.serial.Driver):
    HARDWARE_ID = b"0003"
    NAME = "Tec"

    def __init__(self):
        hardware.serial.Driver.__init__(self)

    @property
    def device_id(self):
        return Driver.HARDWARE_ID

    @property
    def device_name(self):
        return Driver.NAME

    def set_pid_d_value(self):
        raise NotImplementedError("Implement me")

    @property
    def end_data_frame(self) -> int:
        return 0
