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


class Struct:
    def __getitem__(self, item: str):
        return getattr(self, item.replace(" ", "_").casefold())


@dataclass
class _PID(Struct):
    P_parameter: float
    I_parameter: typing.Annotated[list[float], 2]
    D_parameter: float


@dataclass
class _SystemParameter(Struct):
    setpoint_temperature: float
    loop_time: float
    reference_resistor: float
    max_power: float


@dataclass
class Tec(Struct):
    PID: _PID
    system_parameter: _SystemParameter

    def __getitem__(self, item: str):
        return getattr(self, item.replace(" ", "_"))  # For convience allow spaces in [] notation


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

    def set_pid_d_value(self, laser: str):
        d_value = 0
        match laser:
            case "Pump Laser":
                d_value = self.pump_laser.PID.D_parameter
            case "Probe Laser":
                d_value = self.probe_laser.PID.D_parameter
        d_value_hex = f"{d_value:0{hardware.serial.Driver._NUMBER_OF_HEX_BYTES}X}"
        self.write(d_value_hex)

    def set_pid_p_value(self, laser: str):
        p_value = 0
        match laser:
            case "Pump Laser":
                p_value = self.pump_laser.PID.P_parameter
            case "Probe Laser":
                p_value = self.probe_laser.PID.P_parameter
        p_value_hex = f"{p_value:0{hardware.serial.Driver._NUMBER_OF_HEX_BYTES}X}"
        self.write(p_value_hex)

    def set_pid_i_1_value(self, laser: str):
        match laser:
            case "Pump Laser":
                i_1_value = self.pump_laser.PID.I_parameter[0]
                i_1_value_hex = f"{i_1_value:0{hardware.serial.Driver._NUMBER_OF_HEX_BYTES}X}"
            case "Probe Laser":
                i_1_value = self.probe_laser.PID.I_parameter[0]
                i_1_value_hex = f"{i_1_value:0{hardware.serial.Driver._NUMBER_OF_HEX_BYTES}X}"
                i_1_value_hex[0] = "1"
            case _:
                i_1_value = 0
                i_1_value_hex = f"{i_1_value:0{hardware.serial.Driver._NUMBER_OF_HEX_BYTES}X}"
        self.write(i_1_value_hex)

    def set_pid_i_2_value(self, laser: str):
        i_2_value = 0
        match laser:
            case "Pump Laser":
                i_2_value = self.pump_laser.PID.I_parameter[0]
            case "Probe Laser":
                i_2_value = self.probe_laser.PID.I_parameter[0]
        i_2_value_hex = f"{i_2_value:0{hardware.serial.Driver._NUMBER_OF_HEX_BYTES}X}"
        self.write(i_2_value_hex)

    def set_setpoint_temperature_value(self, laser: str):
        setpoint_temperature_value = 0
        match laser:
            case "Pump Laser":
                setpoint_temperature_value = self.pump_laser.system_parameter.setpoint_temperature
            case "Probe Laser":
                setpoint_temperature_value = self.probe_laser.system_parameter.setpoint_temperature
        setpoint_temperature_value_hex = f"{setpoint_temperature_value:0{hardware.serial.Driver._NUMBER_OF_HEX_BYTES}X}"
        self.write(setpoint_temperature_value_hex)

    def set_loop_time_value(self, laser: str):
        loop_time_value = 0
        match laser:
            case "Pump Laser":
                loop_time_value = self.pump_laser.system_parameter.setpoint_temperature
            case "Probe Laser":
                loop_time_value = self.probe_laser.system_parameter.setpoint_temperature
        loop_time_value_hex = f"{loop_time_value:0{hardware.serial.Driver._NUMBER_OF_HEX_BYTES}X}"
        self.write(loop_time_value_hex)

    def set_reference_resistor_value(self, laser: str):
        reference_resistor_value = 0
        match laser:
            case "Pump Laser":
                reference_resistor_value = self.pump_laser.system_parameter.reference_resistor
            case "Probe Laser":
                reference_resistor_value = self.probe_laser.system_parameter.reference_resistor
        reference_resistor_value_hex = f"{reference_resistor_value:0{hardware.serial.Driver._NUMBER_OF_HEX_BYTES}X}"
        self.write(reference_resistor_value_hex)

    def set_max_power_value(self, laser: str):
        max_power_value = 0
        match laser:
            case "Pump Laser":
                max_power_value = self.pump_laser.system_parameter.max_power
            case "Probe Laser":
                max_power_value = self.probe_laser.system_parameter.max_power
        max_power_value_hex = f"{max_power_value:0{hardware.serial.Driver._NUMBER_OF_HEX_BYTES}X}"
        self.write(max_power_value_hex)

    @property
    def end_data_frame(self) -> int:
        return 0
