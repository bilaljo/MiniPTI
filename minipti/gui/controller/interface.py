from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Callable

from PyQt5 import QtWidgets

from minipti.gui import model


@dataclass
class Controllers(ABC):
    main_application: "MainApplication"
    toolbar: "Toolbar"
    statusbar: "Statusbar"
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
        self.configuration: model.configuration.GUI | None = None

    @property
    @abstractmethod
    def controllers(self) -> Controllers:
        ...

    @abstractmethod
    def emergency_stop(self) -> None:
        ...

    @abstractmethod
    def close(self) -> None:
        ...


class Toolbar(ABC):
    @abstractmethod
    def on_run(self) -> None:
        ...

    @abstractmethod
    def enable_daq(self) -> None:
        ...

    @abstractmethod
    def shutdown(self) -> None:
        ...

    @abstractmethod
    def init_devices(self) -> None:
        ...

    @abstractmethod
    def connect_devices(self) -> None:
        ...

    @abstractmethod
    def find_devices(self) -> None:
        ...

    @property
    @abstractmethod
    def destination_folder(self) -> model.processing.DestinationFolder:
        ...

    @abstractmethod
    def update_destination_folder(self) -> None:
        ...

    @abstractmethod
    def show_settings(self) -> None:
        ...

    @abstractmethod
    def show_utilities(self) -> None:
        ...

    @abstractmethod
    def change_valve(self) -> None:
        ...

    @abstractmethod
    def enable_pump(self) -> None:
        ...


class Statusbar(ABC):
    @property
    @abstractmethod
    def view(self) -> QtWidgets.QStatusBar:
        ...

    @abstractmethod
    def show_bms(self) -> None:
        ...

    @abstractmethod
    def update_destination_folder(self, folder: str) -> None:
        ...


class Settings(ABC):
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

    @abstractmethod
    def save_valve_settings(self) -> None:
        ...

    @abstractmethod
    def load_valve_settings(self) -> None:
        ...

    @abstractmethod
    def update_flow_rate(self, flow_rate: str) -> None:
        ...

    @abstractmethod
    def save_pump_settings(self) -> None:
        ...

    @abstractmethod
    def load_pump_settings(self) -> None:
        ...

    @abstractmethod
    def save_daq_settings(self) -> None:
        ...

    @abstractmethod
    def load_daq_settings(self) -> None:
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

    @abstractmethod
    def enable_pump(self, enable: bool) -> None:
        ...

    @abstractmethod
    def enable_pump_on_run(self) -> None:
        ...

    @abstractmethod
    def update_sample_setting(self) -> None:
        ...


class Utilities(ABC):
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
    def calculate_response_phases(self) -> None:
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
    def plot_lock_in_phases(self) -> None:
        ...

    @abstractmethod
    def calculate_characterisation(self) -> None:
        ...

    @abstractmethod
    def plot_characterisation(self) -> None:
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

    # @abstractmethod
    def find(self) -> None:
        ...

    # @abstractmethod
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
