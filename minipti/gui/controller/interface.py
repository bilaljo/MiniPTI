from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Callable, Union

from PyQt5 import QtWidgets

from minipti.gui import model


@dataclass
class Controllers(ABC):
    main_application: "MainApplication"
    home: "Home"
    settings: "Settings"
    utilities: "Utilities"
    pump_laser: "PumpLaser"
    probe_laser: "ProbeLaser"
    tec: list["Tec"]

    @property
    @abstractmethod
    def configuration(self) -> model.configuration.GUI:
        ...


class MainApplication(QtWidgets.QApplication):
    def __init__(self, argv=""):
        QtWidgets.QApplication.__init__(self, argv)
        self.configuration: Union[None, model.configuration.GUI] = None

    @property
    @abstractmethod
    def controllers(self) -> Controllers:
        ...

    @abstractmethod
    def close(self) -> None:
        ...

    @abstractmethod
    def await_shutdown(self):
        ...


class Home(ABC):
    def __init__(self):
        self.configuration: Union[None, model.configuration.Home] = None

    @abstractmethod
    def init_devices(self) -> None:
        ...

    @abstractmethod
    def connect_devices(self) -> None:
        ...

    @abstractmethod
    def find_devices(self) -> None:
        ...

    @abstractmethod
    def on_run(self) -> None:
        ...

    @abstractmethod
    def fire_motherboard_configuration_change(self) -> None:
        ...

    @abstractmethod
    def enable_motherboard(self) -> None:
        ...

    @abstractmethod
    def show_settings(self) -> None:
        ...

    @abstractmethod
    def show_utilities(self) -> None:
        ...

    @property
    @abstractmethod
    def destination_folder(self) -> model.processing.DestinationFolder:
        ...

    @abstractmethod
    def update_destination_folder(self) -> None:
        ...


class Settings(ABC):
    def __init__(self):
        self.configuration: Union[None, model.configuration.Settings] = None

    @abstractmethod
    def fire_configuration_change(self) -> None:
        ...

    @abstractmethod
    def update_common_mode_noise_reduction(self, state: bool) -> None:
        ...

    @abstractmethod
    def update_save_raw_data(self, state: bool) -> None:
        ...

    @property
    @abstractmethod
    def settings_table_model(self) -> model.processing.SettingsTable:
        ...

    @abstractmethod
    def save_pti_settings(self) -> None:
        ...

    @abstractmethod
    def save_pti_settings_as(self) -> None:
        ...

    @abstractmethod
    def load_pti_settings(self) -> None:
        ...

    #@abstractmethod
    #def save_valve_settings_as(self) -> None:
    #    ...

    @abstractmethod
    def save_valve_settings(self) -> None:
        ...

    @abstractmethod
    def load_valve_settings(self) -> None:
        ...

    @abstractmethod
    def save_daq_settings(self) -> None:
        ...

    @abstractmethod
    def load_daq_settings(self) -> None:
        ...

    @abstractmethod
    def update_average_period(self, samples: str) -> None:
        ...

    @abstractmethod
    def update_automatic_valve_switch(self, automatic_valve_switch: bool) -> None:
        ...

    @abstractmethod
    def update_valve_period(self, period: str) -> None:
        ...

    @abstractmethod
    def update_bypass(self) -> None:
        ...

    @abstractmethod
    def update_valve_duty_cycle(self, duty_cycle: str) -> None:
        ...


class Utilities(ABC):
    @property
    @abstractmethod
    def motherboard(self) -> model.serial_devices.Motherboard:
        ...

    @property
    @abstractmethod
    def laser(self) -> model.serial_devices.Laser:
        ...

    @property
    @abstractmethod
    def tec(self) -> model.serial_devices.Tec:
        ...

    @property
    @abstractmethod
    def configuration(self) -> model.configuration.Utilities:
        ...

    @abstractmethod
    def calculate_decimation(self) -> None:
        ...

    @abstractmethod
    def plot_dc(self) -> None:
        ...

    @abstractmethod
    def calculate_interferometry(self) -> None:
        ...

    @abstractmethod
    def calculate_pti_inversion(self) -> None:
        ...

    @abstractmethod
    def plot_inversion(self) -> None:
        ...

    @abstractmethod
    def plot_interferometric_phase(self) -> None:
        ...

    @abstractmethod
    def calculate_characterisation(self) -> None:
        ...

    @abstractmethod
    def plot_characterisation(self) -> None:
        ...

    @abstractmethod
    def set_clean_air(self, bypass: bool) -> None:
        ...


class Driver(ABC):
    @abstractmethod
    def enable(self) -> None:
        ...

    @property
    @abstractmethod
    def view(self) -> QtWidgets.QWidget:
        ...

    @abstractmethod
    def save_configuration(self) -> None:
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

    #@abstractmethod
    def find(self) -> None:
        ...

    #@abstractmethod
    def connect(self) -> None:
        ...

    @abstractmethod
    def fire_configuration_change(self) -> None:
        ...


class PumpLaser(Driver):
    def __init__(self):
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


class ProbeLaser(Driver):
    def __init__(self):
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


class Tec(Driver):
    def __init__(self):
        Driver.__init__(self)

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
