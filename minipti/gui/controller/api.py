import abc
import logging
import os
import threading
import time
import typing
from dataclasses import dataclass

import qdarktheme
from PyQt5 import QtWidgets, QtCore
from PyQt5.QtCore import QCoreApplication
from overrides import override

from minipti.gui import model
from minipti.gui import view
from minipti.gui.controller import interface
from minipti.gui.view import plots


@dataclass
class Controllers(interface.Controllers):
    main_application: "MainApplication"
    home: "Home"
    settings: "Settings"
    utilities: "Utilities"
    pump_laser: "PumpLaser"
    probe_laser: "ProbeLaser"
    tec: list["Tec"]

    @property
    def configuration(self) -> model.configuration.GUI:
        return self.main_application.configuration


class MainApplication(interface.MainApplication):
    def __init__(self, argv=""):
        interface.MainApplication.__init__(self, argv)
        settings_controller = Settings()
        utilities_controller = Utilities()
        self._controllers: Controllers = Controllers(main_application=self,
                                                     home=Home(settings_controller, utilities_controller),
                                                     settings=settings_controller,
                                                     utilities=utilities_controller,
                                                     pump_laser=PumpLaser(),
                                                     probe_laser=ProbeLaser(),
                                                     tec=[Tec(laser=model.serial_devices.Tec.PUMP_LASER),
                                                          Tec(laser=model.serial_devices.Tec.PROBE_LASER)])
        self.logging_model = model.general_purpose.Logging()
        self.view = view.api.MainWindow(self.controllers)
        self.motherboard = model.serial_devices.Motherboard()
        self.laser = model.serial_devices.Laser()
        self.tec = model.serial_devices.Tec()
        model.signals.GENERAL_PURPORSE.theme_changed.connect(self.update_theme)
        threading.Thread(target=model.general_purpose.theme_observer, daemon=True).start()
        self.controllers.home.init_devices()
        # threading.excepthook = self.thread_exception

    @QtCore.pyqtSlot(str)
    def update_theme(self, theme: str) -> None:
        qdarktheme.setup_theme(theme.casefold())
        for plot in self.view.plots:  # type: typing.Union[view.plots.Plotting, list]
            try:
                plot.update_theme(theme)
            except AttributeError:  # list of plots
                for sub_plot in plot:  # type: view.plots.Plotting
                    sub_plot.update_theme(theme)
        self.view.home.dc.update_theme(theme)
        self.view.home.interferometric_phase.update_theme(theme)
        self.view.home.pti_signal.update_theme(theme)

    @property
    @override
    def controllers(self) -> Controllers:
        return self._controllers

    @override
    def close(self) -> None:
        self.motherboard.driver.daq.running.clear()
        self.motherboard.driver.bms.running.clear()
        self.motherboard.driver.close()
        self.laser.driver.close()
        self.tec.close()
        self.view.close()
        time.sleep(0.1)
        QCoreApplication.quit()

    def thread_exception(self, args) -> None:
        if args.exc_type == KeyError:
            QtWidgets.QMessageBox.critical(self.view, "File Error", "Invalid file given or missing headers.")
        elif args.exc_type == TimeoutError:
            QtWidgets.QMessageBox.critical(self.view, "Timeout Error", "Timeout Error")
        else:
            QtWidgets.QMessageBox.critical(self.view, "Error", f"{args.exc_type} error occurred.")


def _get_file_path(parent, dialog_name: str, last_file_path: str, files: str) -> tuple[str, str]:
    file_path = QtWidgets.QFileDialog.getOpenFileName(parent, directory=last_file_path,
                                                      caption=dialog_name, filter=files)
    if file_path[0]:
        last_file_path = file_path[0]
    return file_path[0], last_file_path


class Home(interface.Home):
    def __init__(self, settings_controller: "Settings", utilities_controller: "Utilities"):
        self.view = view.api.Home(self)
        self.settings = view.settings.SettingsWindow(settings_controller)
        settings_controller.fire_configuration_change()
        self.utilities = view.utilities.UtilitiesWindow(utilities_controller)
        self.calculation_model = settings_controller.calculation_model
        self.motherboard = model.serial_devices.Motherboard()
        self.valve = model.serial_devices.Valve()
        self.pump_laser = model.serial_devices.PumpLaser()
        self.probe_laser = model.serial_devices.ProbeLaser()
        self.tec = [model.serial_devices.Tec(model.serial_devices.Tec.PUMP_LASER),
                    model.serial_devices.Tec(model.serial_devices.Tec.PROBE_LASER)]
        self.running = False
        self._destination_folder = model.processing.DestinationFolder()

    @override
    def update_destination_folder(self) -> None:
        destination_folder = QtWidgets.QFileDialog.getExistingDirectory(self.view, "Destination Folder",
                                                                        self.destination_folder.folder,
                                                                        QtWidgets.QFileDialog.ShowDirsOnly)
        if destination_folder:
            self.destination_folder.folder = destination_folder

    @property
    @override
    def destination_folder(self) -> model.processing.DestinationFolder:
        return self._destination_folder

    @override
    def init_devices(self) -> None:
        def find_and_connect():
            self.find_devices()
            self.connect_devices()
        threading.Thread(target=find_and_connect, name="Find and Connect Devices Thread", daemon=True).start()

    @override
    def find_devices(self) -> None:
        if model.configuration.GUI.home.connect.devices.motherboard:
            try:
                self.motherboard.find_port()
            except OSError:
                logging.error("Could not find Motherboard")
        if model.configuration.GUI.home.connect.devices.laser_driver:
            try:
                self.pump_laser.find_port()
            except OSError:
                logging.error("Could not find Laser Driver")
        if model.configuration.GUI.home.connect.devices.tec_driver:
            try:
                self.tec[0].find_port()
            except OSError:
                logging.error("Could not find TEC Driver")

    @override
    def connect_devices(self) -> None:
        if self.motherboard.is_found:
            try:
                self.motherboard.open()
                self.motherboard.run()
                self.motherboard.process_measured_data()
            except OSError:
                logging.error("Could not connect with Motherboard")
        if self.pump_laser.is_found:
            try:
                self.pump_laser.open()
                self.pump_laser.run()
                self.pump_laser.process_measured_data()
            except OSError:
                logging.error("Could not connect with Laser Driver")
        if self.tec[0].is_found:
            try:
                self.tec[0].open()
                self.tec[0].run()
                self.tec[0].process_measured_data()
            except OSError:
                logging.error("Could not connect with TEC Driver")

    @override
    def on_run(self) -> None:
        self.running = not self.running
        if model.configuration.GUI.home.on_run.pump_laser.laser_driver:
            self.pump_laser.enabled = self.running
        if model.configuration.GUI.home.on_run.probe_laser.laser_driver:
            self.probe_laser.enabled = self.running
        if model.configuration.GUI.home.on_run.pump_laser.tec_driver:
            self.tec[model.serial_devices.Tec.PUMP_LASER].enabled = self.running
        if model.configuration.GUI.home.on_run.probe_laser.tec_driver:
            self.tec[model.serial_devices.Tec.PROBE_LASER].enabled = self.running
        if model.configuration.GUI.home.on_run.DAQ:
            self.enable_motherboard()

    @override
    def show_settings(self) -> None:
        self.settings.show()

    @override
    def show_utilities(self) -> None:
        self.utilities.show()

    @override
    def fire_motherboard_configuration_change(self) -> None:
        self.motherboard.fire_configuration_change()

    @override
    def enable_motherboard(self) -> None:
        if not self.motherboard.connected:
            QtWidgets.QMessageBox.critical(self.view, "IO Error",
                                           "Cannot enable Motherboard. Motherboard is not connected.")
            logging.error("Cannot enable Motherboard")
            logging.warning("Motherboard is not connected")
        else:
            if self.running:
                self.motherboard.running = True
                self.calculation_model.process_daq_data()
            else:
                self.motherboard.running = False

            logging.debug("%s Motherboard", "Enabled" if self.motherboard.running else "Disabled")

    @override
    def shutdown(self) -> None:
        self.motherboard.shutdown_procedure()

    @override
    def toggle_valve(self) -> None:
        self.valve.bypass = not self.valve.bypass


class Settings(interface.Settings):
    def __init__(self):
        interface.Settings.__init__(self)
        self.daq = model.serial_devices.DAQ()
        self.calculation_model = model.processing.LiveCalculation()
        self.valve = model.serial_devices.Valve()
        self.motherboard = model.serial_devices.Motherboard()
        self._settings_table = model.processing.SettingsTable()
        self.view = view.settings.SettingsWindow(self)
        self.last_file_path = os.getcwd()

    @override
    def fire_configuration_change(self) -> None:
        self.daq.fire_configuration_change()
        self.valve.fire_configuration_change()

    @property
    @override
    def settings_table_model(self) -> model.processing.SettingsTable:
        return self._settings_table

    @override
    def update_common_mode_noise_reduction(self, state: bool):
        self.calculation_model.set_common_mode_noise_reduction(state)

    @override
    def update_save_raw_data(self, state: bool):
        self.calculation_model.set_raw_data_saving(state)

    @override
    def update_average_period(self, samples: str) -> None:
        samples_number = samples.split(" Samples")[0]  # Value has the structure "X Samples"
        self.daq.number_of_samples = int(samples_number)
        self.calculation_model.pti.decimation.average_period = int(samples_number)

    @override
    def save_pti_settings(self) -> None:
        self.settings_table_model.save()

    @override
    def save_pti_settings_as(self) -> None:
        file_path = save_as(parent=self.view, file_type="CSV File", file_extension="csv",
                            name="Algorithm Configuration")
        if file_path:
            self.settings_table_model.file_path = file_path
            self.settings_table_model.save()

    @override
    def load_pti_settings(self):
        file_path, self.last_file_path = _get_file_path(self.view, "Load SettingsTable", self.last_file_path,
                                                        "CSV File (*.csv);;"
                                                        " TXT File (*.txt);; All Files (*);;")
        if file_path:
            self.settings_table_model.file_path = file_path
            self.settings_table_model.load()

    @override
    def save_daq_settings(self) -> None:
        self.daq.save_configuration()

    def save_daq_settings_as(self) -> None:
        file_path = save_as(parent=self.view, file_type="JSON", file_extension="json",
                            name="DAQ Configuration")
        if file_path:
            self.daq.config_path = file_path
            self.daq.save_configuration()

    @override
    def load_daq_settings(self) -> None:
        config_path, self.last_file_path = _get_file_path(self.view, "Laser Driver", self.last_file_path,
                                                          "JSON File (*.json);; All Files (*)")
        if config_path:
            self.daq.config_path = config_path
        else:
            return
        self.daq.load_configuration()

    @override
    def save_valve_settings(self) -> None:
        self.valve.save_configuration()

    def save_valve_settings_as(self) -> None:
        file_path = save_as(parent=self.view, file_type="JSON", file_extension="json",
                            name="Valve Configuration")
        if file_path:
            self.valve.config_path = file_path
            self.valve.save_configuration()

    @override
    def load_valve_settings(self) -> None:
        config_path, self.last_file_path = _get_file_path(self.view, "Valve", self.last_file_path,
                                                          "JSON File (*.json);; All Files (*)")
        if config_path:
            self.valve.config_path = config_path
        else:
            return
        self.valve.load_configuration()

    @override
    def update_valve_period(self, period: str) -> None:
        try:
            period = _string_to_number(self.view, period, cast=int)
        except ValueError:
            period = 600
        try:
            self.valve.valve_period = period
        except ValueError as error:
            info_text = "Value must be a positive integer"
            logging.error(str(error))
            logging.warning(info_text)
            QtWidgets.QMessageBox.critical(self.view, "Valve Error", f"{str(error)}. {info_text}")

    @override
    def update_valve_duty_cycle(self, duty_cycle: str) -> None:
        try:
            duty_cycle = _string_to_number(self.view, duty_cycle, cast=int)
        except ValueError:
            duty_cycle = 50
        try:
            self.valve.duty_cycle = duty_cycle
        except ValueError as error:
            info_text = "Value must be an integer between 0 and 100"
            logging.error(str(error))
            logging.warning(info_text)
            QtWidgets.QMessageBox.critical(self.view, "Valve Error", f"{str(error)}. {info_text}")

    @override
    def update_automatic_valve_switch(self, automatic_valve_switch: bool) -> None:
        self.valve.automatic_valve_switch = automatic_valve_switch

    @override
    def update_bypass(self) -> None:
        self.motherboard.bypass = not self.motherboard.bypass


class Utilities(interface.Utilities):
    def __init__(self):
        self.view = view.utilities.UtilitiesWindow(self)
        self.calculation_model = model.processing.OfflineCalculation()
        self.last_file_path = os.getcwd()
        self._mother_board = model.serial_devices.Motherboard()
        self._laser = model.serial_devices.Laser()
        self._tec = model.serial_devices.Tec()
        self.interferometric_phase_offline = plots.InterferometricPhaseOffline()
        self.dc_offline = plots.DCOffline()
        model.signals.CALCULATION.dc_signals.connect(self.dc_offline.plot)
        model.signals.CALCULATION.inversion.connect(plots.pti_signal_offline)
        model.signals.CALCULATION.interferometric_phase.connect(self.interferometric_phase_offline.plot)
        # model.theme_signal.changed.connect(view.utilities.update_matplotlib_theme)

    @property
    @override
    def configuration(self) -> model.configuration.Utilities:
        return self._configuration

    @property
    @override
    def motherboard(self) -> model.serial_devices.Motherboard:
        return self._mother_board

    @property
    @override
    def laser(self) -> model.serial_devices.Laser:
        return self._laser

    @property
    @override
    def tec(self) -> model.serial_devices.Tec:
        return self._tec

    @override
    def set_clean_air(self, bypass: bool) -> None:
        self.motherboard.bypass = bypass

    @override
    def calculate_decimation(self) -> None:
        decimation_file_path, self.last_file_path = _get_file_path(self.view, "Decimation", self.last_file_path,
                                                                   "HDF5 File (*.hdf5);; All Files (*)")
        if not decimation_file_path:
            return
        threading.Thread(target=self.calculation_model.calculate_decimation,
                         args=[decimation_file_path]).start()

    @override
    def plot_dc(self) -> None:
        try:
            decimation_path, self.last_file_path = _get_file_path(self.view, "Decimation", self.last_file_path,
                                                                  "CSV File (*.csv);; TXT File (*.txt);; All Files (*)")
            if decimation_path:
                model.processing.process_dc_data(decimation_path)
        except KeyError:
            QtWidgets.QMessageBox.critical(self.view, "Plotting Error", "Invalid data given. Could not plot.")

    @override
    def calculate_interferometry(self) -> None:
        interferometry_path, self.last_file_path = _get_file_path(self.view, "Interferometry",
                                                                  self.last_file_path,
                                                                  "CSV File (*.csv);; TXT File (*.txt);; All Files (*)")
        if not interferometry_path:
            return
        threading.Thread(target=self.calculation_model.calculate_interferometry, args=[interferometry_path]).start()

    @override
    def calculate_pti_inversion(self) -> None:
        inversion_path, self.last_file_path = _get_file_path(self.view, "Inversion", self.last_file_path,
                                                             "CSV File (*.csv);; TXT File (*.txt);; All Files (*)")
        if not inversion_path:
            return
        threading.Thread(target=self.calculation_model.calculate_inversion, args=[inversion_path]).start()

    @override
    def plot_inversion(self) -> None:
        try:
            inversion_path, self.last_file_path = _get_file_path(self.view, "Inversion", self.last_file_path,
                                                                 "CSV File (*.csv);; TXT File (*.txt);;"
                                                                 " All Files (*)")
            if inversion_path:
                model.processing.process_inversion_data(inversion_path)
        except KeyError:
            QtWidgets.QMessageBox.critical(self.view, "Plotting Error", "Invalid data given. Could not plot.")

    @override
    def plot_interferometric_phase(self) -> None:
        try:
            interferometric_phase_path, self.last_file_path = _get_file_path(self.view, "Inversion",
                                                                             self.last_file_path,
                                                                             "CSV File (*.csv);; TXT File (*.txt);;"
                                                                             " All Files (*)")
            if interferometric_phase_path:
                model.processing.process_interferometric_phase_data(interferometric_phase_path)
        except KeyError:
            QtWidgets.QMessageBox.critical(self.view, "Plotting Error", "Invalid data given. Could not plot.")

    @override
    def calculate_characterisation(self) -> None:
        characterisation_path, self.last_file_path = _get_file_path(self.view, "Characterisation",
                                                                    self.last_file_path,
                                                                    "CSV File (*.csv);; TXT File (*.txt);;"
                                                                    " All Files (*)")
        if not characterisation_path:
            return
        use_settings = QtWidgets.QMessageBox.question(self.view, "Characterisation",
                                                      "Do you want to use the algorithm_settings values?",
                                                      QtWidgets.QMessageBox.StandardButton.Yes
                                                      | QtWidgets.QMessageBox.StandardButton.No)
        use_settings = use_settings == QtWidgets.QMessageBox.StandardButton.Yes
        threading.Thread(target=self.calculation_model.calculate_characterisation,
                         args=[characterisation_path, use_settings]).start()

    @override
    def plot_characterisation(self) -> None:
        try:
            characterization_path, self.last_file_path = _get_file_path(self.view, "Characterization",
                                                                        self.last_file_path,
                                                                        "CSV File (*.csv);; TXT File (*.txt);;"
                                                                        " All Files (*)")
            if characterization_path:
                model.processing.process_characterization_data(characterization_path)
        except KeyError:
            QtWidgets.QMessageBox.critical(self.view, "Plotting Error", "Invalid data given. Could not plot.")


T = typing.TypeVar("T")


def _string_to_number(parent: QtWidgets.QWidget, string_number: str, cast: typing.Callable[[str], T]) -> T:
    try:
        return cast(string_number)
    except ValueError:
        logging.error("Could not apply new value. Invalid symbols encountered.")
        QtWidgets.QMessageBox.critical(parent, "Value Error", "Could not apply new value. Invalid symbols encountered.")
        raise ValueError


class Laser(interface.Driver):
    def __init__(self):
        interface.Driver.__init__(self)
        self.laser = model.serial_devices.Laser()
        self.last_file_path = os.getcwd()

    def load_configuration(self) -> None:
        config_path, self.last_file_path = _get_file_path(self.view, "Laser Driver", self.last_file_path,
                                                          "JSON File (*.json);; All Files (*)")
        if config_path:
            self.laser.config_path = config_path
        else:
            return
        self.laser.load_configuration()
        self.fire_configuration_change()

    def save_configuration(self) -> None:
        self.laser.save_configuration()

    def save_configuration_as(self) -> None:
        file_path = save_as(parent=self.view, file_type="JSON File", file_extension="json",
                            name="Laser Configuration")
        if file_path:
            self.laser.config_path = file_path  # The actual file path
            self.laser.save_configuration()

    def apply_configuration(self) -> None:
        self.laser.apply_configuration()

    @abc.abstractmethod
    def fire_configuration_change(self) -> None:
        """
        By initialisation of the Laser Driver Object (on which the laser model relies) the
        configuration is already set and do not fire events to update the GUI. This function is
        hence only called once to manually activate the firing.
        """


class PumpLaser(Laser):
    def __init__(self):
        Laser.__init__(self)
        self._view = view.hardware.PumpLaser(self)
        self.laser = model.serial_devices.PumpLaser()

    @property
    @override
    def view(self) -> view.hardware.PumpLaser:
        return self._view

    @override
    def enable(self) -> None:
        if not self.laser.connected:
            QtWidgets.QMessageBox.critical(self.view, "IO Error",
                                           "Cannot enable Pump Laser. Pump Laser is not connected.")
            logging.error("Cannot enable Pump Laser")
            logging.warning("Pump Laser is not connected")
        else:
            if not self.laser.enabled:
                self.laser.enabled = True
            else:
                self.laser.enabled = False
            logging.debug(f"{'Enabled' if self.laser.enabled else 'Disabled'} Pump Laser")

    def update_driver_voltage(self, bits: int) -> None:
        if bits != self.laser.driver_bits:
            self.laser.driver_bits = bits

    def update_current_dac1(self, bits: int) -> None:
        if self.laser.current_bits_dac_2 != bits:
            self.laser.current_bits_dac_1 = bits

    def update_current_dac2(self, bits: int) -> None:
        if self.laser.current_bits_dac_1 != bits:
            self.laser.current_bits_dac_2 = bits

    def update_dac1(self, channel: int) -> typing.Callable[[int], None]:
        def set_matrix(mode: int) -> None:
            self.laser.update_dac_mode(self.laser.dac_1_matrix, channel, mode)

        return set_matrix

    def update_dac2(self, channel: int) -> typing.Callable[[int], None]:
        def set_matrix(mode: int) -> None:
            self.laser.update_dac_mode(self.laser.dac_2_matrix, channel, mode)

        return set_matrix

    def fire_configuration_change(self) -> None:
        self.laser.fire_configuration_change()


class ProbeLaser(Laser):
    def __init__(self):
        Laser.__init__(self)
        self.laser = model.serial_devices.ProbeLaser()
        self._view = view.hardware.ProbeLaser(self)

    @property
    @override
    def view(self) -> view.hardware.ProbeLaser:
        return self._view

    @override
    def enable(self) -> None:
        if not self.laser.connected:
            QtWidgets.QMessageBox.critical(self.view, "IO Error",
                                           "Cannot enable Tec Driver of Probe Laser. Tec Driver is not connected.")
            logging.error("Cannot enable Tec Driver of Probe Laser")
            logging.warning("Tec Driver is not connected")
        else:
            if not self.laser.enabled:
                self.laser.enabled = True
            else:
                self.laser.enabled = False
            logging.debug(f"{'Enabled' if self.laser.enabled else 'Disabled'} Tec Driver of Probe Laser")

    def update_max_current_probe_laser(self, max_current: str) -> None:
        try:
            new_max_current = _string_to_number(self.view, max_current, cast=float)
        except ValueError:
            return
        self.laser.probe_laser_max_current = new_max_current

    def update_photo_gain(self, value: int) -> None:
        if self.laser.photo_diode_gain != value + 1:
            self.laser.photo_diode_gain = value + 1

    def update_probe_laser_mode(self, index: int) -> None:
        self.laser.probe_laser_mode = index

    def update_current_probe_laser(self, bits: int) -> None:
        effective_bits: int = model.serial_devices.ProbeLaser.CURRENT_BITS - bits
        if effective_bits != self.laser.current_bits_probe_laser:
            self.laser.current_bits_probe_laser = effective_bits

    def fire_configuration_change(self) -> None:
        self.laser.fire_configuration_change()


class Tec(interface.Driver):
    def __init__(self, laser: int):
        self.tec = model.serial_devices.Tec(laser)
        self.laser = laser
        self._view = view.hardware.Tec(self, laser)
        self.last_file_path = os.getcwd()

    @property
    @override
    def view(self) -> view.hardware.Tec:
        return self._view

    @override
    def save_configuration_as(self) -> None:
        file_path = save_as(parent=self.view, file_type="JSON File", file_extension="json", name="TEC Configuration")
        if file_path:
            self.tec.config_path = file_path  # The actual file path
            self.tec.save_configuration()

    @override
    def save_configuration(self) -> None:
        self.tec.save_configuration()

    @override
    def load_configuration(self) -> None:
        config_path, self.last_file_path = _get_file_path(self.view, "TEC Driver", self.last_file_path,
                                                          "JSON File (*.json);; All Files (*)")
        if config_path:
            self.tec.config_path = config_path
        else:
            return
        self.tec.load_configuration()
        self.fire_configuration_change()

    @override
    def apply_configuration(self) -> None:
        self.tec.apply_configuration()

    @override
    def enable(self) -> None:
        if not self.tec.connected:
            QtWidgets.QMessageBox.critical(self.view, "IO Error",
                                           "Cannot enable Tec Driver of Pump Laser. Tec Driver is not connected.")
            logging.error("Cannot enable Tec Driver of Pump Laser")
            logging.warning("Tec Driver is not connected")
        else:
            if not self.tec.enabled:
                self.tec.enabled = True
            else:
                self.tec.enabled = False
            logging.debug(f"{'Enabled' if self.tec.enabled else 'Disabled'} Tec Driver of %s",
                          "Pump Laser" if self.laser == model.serial_devices.Tec.PUMP_LASER else "Probe Laser")

    def update_d_gain(self, d_gain: str) -> None:
        try:
            self.tec.d_gain = _string_to_number(self.view, d_gain, cast=float)
        except ValueError:
            self.tec.d_gain = 0

    def update_i_gain(self, i_gain: str) -> None:
        try:
            self.tec.i_gain = _string_to_number(self.view, i_gain, cast=float)
        except ValueError:
            self.tec.i_gain = 0

    def update_p_gain(self, p_gain: str) -> None:
        try:
            self.tec.p_value = _string_to_number(self.view, p_gain, cast=float)
        except ValueError:
            self.tec.p_value = 0

    def update_setpoint_temperature(self, setpoint_temperature: str) -> None:
        try:
            self.tec.setpoint_temperature = _string_to_number(self.view, setpoint_temperature, cast=float)
        except ValueError:
            self.tec.setpoint_temperature = model.serial_devices.Tec.ROOM_TEMPERATURE

    def update_loop_time(self, loop_time: str) -> None:
        self.tec.loop_time = _string_to_number(self.view, loop_time, cast=int)

    def update_max_power(self, max_power: str) -> None:
        try:
            self.tec.max_power = _string_to_number(self.view, max_power, cast=float)
        except ValueError:
            self.tec.max_power = 0

    @override
    def fire_configuration_change(self) -> None:
        self.tec.fire_configuration_change()


def save_as(parent, file_type, file_extension, name) -> str:
    file_path = QtWidgets.QFileDialog.getSaveFileName(parent, caption=f"{name} Path",
                                                      filter=f"{file_type} (*.{file_extension});; All Files (*);;")[0]
    if file_path:
        _, old_file_extension = os.path.splitext(file_path)
        if not old_file_extension:
            file_path = file_path + "." + file_extension
        if os.path.exists(file_path):
            answer = QtWidgets.QMessageBox.question(parent, f"{name} Path",
                                                    f"File {file_path} exists already. Do you want to replace it?",
                                                    QtWidgets.QMessageBox.StandardButton.Yes
                                                    | QtWidgets.QMessageBox.StandardButton.No)
            if answer == QtWidgets.QMessageBox.StandardButton.Yes:
                logging.warning("Overriding %s", file_path)
            else:
                file_path = ""
            if file_path:
                logging.info("Saved %s into %s", name, file_path)
    return file_path
