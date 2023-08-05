from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Callable

from PyQt5 import QtCore

from minipti.gui import model


@dataclass
class Controllers:
    main_controller: "MainController"
    home: "Home"
    settings: "Settings"
    utilities: "Utilities"
    pump_laser: "PumpLaser"
    probe_laser: "ProbeLaser"
    tec: list["Tec"]


class Home(ABC):
    def __init__(self):
        ABC.__init__(self)

    @abstractmethod
    def fire_motherboard_configuration_change(self) -> None:
        ...

    @abstractmethod
    def enable_motherboard(self) -> None:
        ...

    @abstractmethod
    def shutdown_by_button(self) -> None:
        ...

    @abstractmethod
    def set_clean_air(self, bypass: bool) -> None:
        ...


class Settings(ABC):
    def __init__(self):
        ABC.__init__(self)
        self.motherboard = MotherBoard()

    @property
    @abstractmethod
    def destination_folder(self) -> model.DestinationFolder:
        ...

    @property
    @abstractmethod
    def settings_table_model(self) -> model.SettingsTable:
        ...

    @abstractmethod
    def set_destination_folder(self) -> None:
        ...

    @abstractmethod
    def save_settings(self) -> None:
        ...

    @abstractmethod
    def save_settings_as(self) -> None:
        ...

    @abstractmethod
    def load_settings(self) -> None:
        ...


class Utilities(ABC):
    def __init__(self):
        ABC.__init__(self)

    @property
    @abstractmethod
    def motherboard(self) -> model.Motherboard:
        ...

    @property
    @abstractmethod
    def laser(self) -> model.Laser:
        ...

    @property
    @abstractmethod
    def tec(self) -> model.Tec:
        ...

    @abstractmethod
    def init_devices(self) -> None:
        ...

    @abstractmethod
    def find_devices(self) -> None:
        ...

    @abstractmethod
    def connect_devices(self) -> None:
        ...

    @abstractmethod
    def calculate_decimation(self) -> None:
        ...

    @abstractmethod
    def plot_dc(self) -> None:
        ...

    @abstractmethod
    def calculate_pti_inversion(self) -> None:
        ...

    @abstractmethod
    def plot_inversion(self) -> None:
        ...

    @abstractmethod
    def calculate_characterisation(self) -> None:
        ...

    @abstractmethod
    def plot_characterisation(self) -> None:
        ...


class Driver(ABC):
    def __int__(self):
        ABC.__init__(self)

    @abstractmethod
    def save_configurations(self) -> None:
        ...

    @abstractmethod
    def save_configuration_as(self) -> None:
        ...

    @abstractmethod
    def load_configuration(self) -> None:
        ...

    @abstractmethod
    def apply_configuration(self) -> None:
        ...

    @abstractmethod
    def find(self) -> None:
        ...

    @abstractmethod
    def connect(self) -> None:
        ...

    @abstractmethod
    def enable(self) -> None:
        ...

    @abstractmethod
    def fire_configuration_change(self) -> None:
        ...


class MotherBoard(ABC, Driver):
    def __init__(self):
        ABC.__init__(self)
        Driver.__init__(self)

    @abstractmethod
    def shutdown_by_button(self) -> None:
        ...

    def set_clean_air(self, bypass: bool) -> None:
        ...

    @abstractmethod
    def update_average_period(self) -> None:
        ...

    @abstractmethod
    def update_valve_period(self) -> None:
        ...

    @abstractmethod
    def update_bypass(self) -> None:
        ...

    @abstractmethod
    def update_valve_duty_cycle(self, duty_cycle: str) -> None:
        ...

    @abstractmethod
    def update_automatic_valve_switch(self, automatic_valve_switch: bool) -> None:
        ...


class PumpLaser(ABC, Driver):
    def __init__(self):
        ABC.__init__(self)
        Driver.__init__(self)

    @abstractmethod
    def update_driver_voltage(self, bits: int) -> None:
        ...

    @abstractmethod
    def update_current_dac1(self, bits: int) -> None:
        ...

    @abstractmethod
    def update_current_dac2(self, bits: int) -> None:
        ...

    @abstractmethod
    def update_dac1(self, channel: int) -> Callable[[int], None]:
        ...

    @abstractmethod
    def update_dac2(self, channel: int) -> Callable[[int], None]:
        ...


class ProbeLaser(ABC, Driver):
    def __init__(self):
        ABC.__init__(self)
        Driver.__init__(self)

    @abstractmethod
    def update_max_current_probe_laser(self, max_current: str) -> None:
        ...

    @abstractmethod
    def update_photo_gain(self, value: int) -> None:
        ...

    @abstractmethod
    def update_probe_laser_mode(self, index: int) -> None:
        ...

    @abstractmethod
    def update_current_probe_laser(self, bits: int) -> None:
        ...

    @abstractmethod
    def fire_configuration_change(self) -> None:
        ...


class Tec(Driver, ABC):
    def __init__(self):
        Driver.__init__(self)
        ABC.__init__(self)

    @abstractmethod
    def update_d_gain(self, d_gain: str) -> None:
        ...

    @abstractmethod
    def update_i_gain(self, i_gain: str) -> None:
        ...

    @abstractmethod
    def update_p_gain(self, p_gain: str) -> None:
        ...

    @abstractmethod
    def update_setpoint_temperature(self, setpoint_temperature: str) -> None:
        ...

    @abstractmethod
    def update_loop_time(self, loop_time: str) -> None:
        ...

    @abstractmethod
    def update_max_power(self, max_power: str) -> None:
        ...
