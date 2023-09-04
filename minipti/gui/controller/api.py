import abc
import logging
import os
import threading
import typing
from dataclasses import dataclass

from PyQt5 import QtWidgets, QtCore
from PyQt5.QtCore import Qt, QCoreApplication
from overrides import override

from minipti.gui import model
from minipti.gui import view
from minipti.gui.controller import interface


@dataclass
class Controllers(interface.Controllers):
    main_application: "MainApplication"
    home: "Home"
    settings: "Settings"
    utilities: "Utilities"
    pump_laser: "PumpLaser"
    probe_laser: "ProbeLaser"
    tec: list["Tec"]


class MainApplication(interface.MainApplication):
    def __init__(self, argv=""):
        interface.MainApplication.__init__(self, argv)
        self._controllers: Controllers = Controllers(main_application=self,
                                                     home=Home(),
                                                     settings=Settings(),
                                                     utilities=Utilities(),
                                                     pump_laser=PumpLaser(),
                                                     probe_laser=ProbeLaser(),
                                                     tec=[Tec(laser=model.Tec.PUMP_LASER),
                                                          Tec(laser=model.Tec.PUMP_LASER)])
        self.logging_model = model.Logging()
        self.view = view.api.MainWindow(self.controllers)
        self.motherboard = model.Motherboard()
        self.laser = model.Laser()
        self.tec = model.Tec()
        # threading.excepthook = self.thread_exception

    @property
    @override
    def controllers(self) -> Controllers:
        return self._controllers

    @override
    def close(self) -> None:
        self.motherboard.driver.running.clear()
        self.motherboard.driver.close()
        self.laser.driver.close()
        self.tec.close()
        self.view.close()
        QCoreApplication.quit()

    @override
    def await_shutdown(self):
        def shutdown_low_energy() -> None:
            self.motherboard.shutdown_event.wait()
            _shutdown(self)
        threading.Thread(target=shutdown_low_energy, daemon=True).start()

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


def _shutdown(controller) -> None:
    QtWidgets.QApplication.setOverrideCursor(Qt.WaitCursor)
    logging.warning("Shutdown started")
    model.shutdown_procedure()
    controller.view.close()
    controller.main_app.quit()


class Home(interface.Home):
    def __init__(self):
        self.view = view.api.Home(self)
        self.settings = view.settings.SettingsWindow(Settings())
        self.utilities = view.utilities.UtilitiesWindow(Utilities())
        self.calculation_model = model.LiveCalculation()
        self.motherboard = model.Motherboard()
        self.laser = model.Laser()
        self.pump_laser = model.PumpLaser()
        self.probe_laser = model.ProbeLaser()
        self.pump_laser_tec = model.Tec(model.Tec.PUMP_LASER)
        self.probe_laser_tec = model.Tec(model.Tec.PROBE_LASER)
        self.motherboard.initialize()

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
                                           "Cannot enable Motherboard. Probe Laser is not connected.")
            logging.error("Cannot enable Motherboard")
            logging.warning("Motherboard is not connected")
        else:
            if not self.motherboard.running:
                self.motherboard.running = True
                self.calculation_model.process_daq_data()
            else:
                self.motherboard.running = False
            logging.debug("%s Motherboard", "Enabled" if self.motherboard.running else "Disabled")


class Settings(interface.Settings):
    def __init__(self):
        interface.Settings.__init__(self)
        self._settings_table = model.SettingsTable()
        self.view = view.settings.SettingsWindow(self)
        self._destination_folder = model.DestinationFolder()
        self.last_file_path = os.getcwd()
        self.calculation_model = model.LiveCalculation()
        self.motherboard = model.Motherboard()
        self.laser = model.Laser()
        self.pump_laser = model.PumpLaser()
        self.probe_laser = model.ProbeLaser()
        self.pump_laser_tec = model.Tec(model.Tec.PUMP_LASER)
        self.probe_laser_tec = model.Tec(model.Tec.PROBE_LASER)
        self.raw_data_changed.connect(self.calculation_model.set_raw_data_saving)
        self.view.measurement_configuration.destination_folder_label.setText(self.destination_folder.folder)
        self.motherboard.fire_configuration_change()

    @property
    @override
    def settings_table_model(self) -> model.SettingsTable:
        return self._settings_table

    @property
    @override
    def destination_folder(self) -> model.DestinationFolder:
        return self._destination_folder

    @property
    def raw_data_changed(self) -> QtCore.pyqtSignal:
        return self.view.measurement_configuration.save_raw_data.stateChanged

    @override
    def update_average_period(self, samples: str) -> None:
        samples_number = samples.split(" Samples")[0]  # Value has the structure "X Samples"
        self.motherboard.number_of_samples = int(samples_number)

    def fire_mother_board_configuration(self) -> None:
        self.motherboard.fire_configuration_change()

    @override
    def save_settings(self) -> None:
        self.settings_table_model.save()

    @override
    def save_settings_as(self) -> None:
        file_path = save_as(parent=self.view, file_type="CSV File", file_extension="csv",
                            name="Algorithm Configuration")
        if file_path:
            self.settings_table_model.file_path = file_path
            self.settings_table_model.save()

    @override
    def load_settings(self):
        file_path, self.last_file_path = _get_file_path(self.view, "Load SettingsTable", self.last_file_path,
                                                        "CSV File (*.csv);;"
                                                        " TXT File (*.txt);; All Files (*);;")
        if file_path:
            self.settings_table_model.file_path = file_path
            self.settings_table_model.load()

    def apply_configurations(self) -> None:
        self.pump_laser.apply_configuration()
        self.probe_laser.apply_configuration()
        self.pump_laser_tec.apply_configuration()
        self.probe_laser_tec.apply_configuration()

    @override
    def set_destination_folder(self) -> None:
        destination_folder = QtWidgets.QFileDialog.getExistingDirectory(self.view, "Destination Folder",
                                                                        self.destination_folder.folder,
                                                                        QtWidgets.QFileDialog.ShowDirsOnly)
        if destination_folder:
            self.destination_folder.folder = destination_folder

    @override
    def update_valve_period(self, period: str) -> None:
        try:
            period = _string_to_number(self.view, period, cast=int)
        except ValueError:
            period = 600
        try:
            self.motherboard.valve_period = period
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
            self.motherboard.valve_duty_cycle = duty_cycle
        except ValueError as error:
            info_text = "Value must be an integer between 0 and 100"
            logging.error(str(error))
            logging.warning(info_text)
            QtWidgets.QMessageBox.critical(self.view, "Valve Error", f"{str(error)}. {info_text}")

    @override
    def update_automatic_valve_switch(self, automatic_valve_switch: bool) -> None:
        self.motherboard.automatic_valve_switch = automatic_valve_switch

    @override
    def save_motherboard_conifugration(self) -> None:
        self.motherboard.save_configuration()

    @override
    def load_motherboard_conifugration(self) -> None:
        file_path, self.last_file_path = _get_file_path(self.view, "Valve", self.last_file_path,
                                                        "INI File (*.ini);; All Files (*)")
        if file_path:
            try:
                self.motherboard.config_path = file_path
            except ValueError as error:
                logging.error(error)
            else:
                self.motherboard.load_configuration()

    @override
    def update_bypass(self) -> None:
        self.motherboard.bypass = not self.motherboard.bypass


class Utilities(interface.Utilities):
    def __init__(self):
        self.view = view.utilities.UtilitiesWindow(self)
        self.calculation_model = model.OfflineCalculation()
        self.last_file_path = os.getcwd()
        self._mother_board = model.Motherboard()
        self._laser = model.Laser()
        self._tec = model.Tec()

    @property
    @override
    def motherboard(self) -> model.Motherboard:
        return self._mother_board

    @property
    @override
    def laser(self) -> model.Laser:
        return self._laser

    @property
    @override
    def tec(self) -> model.Tec:
        return self._tec

    @override
    def set_clean_air(self, bypass: bool) -> None:
        self.motherboard.bypass = bypass

    @override
    def calculate_decimation(self) -> None:
        decimation_file_path, self.last_file_path = _get_file_path(self.view, "Decimation", self.last_file_path,
                                                                   "Binary File (*.bin);; All Files (*)")
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
                model.process_dc_data(decimation_path)
        except KeyError:
            QtWidgets.QMessageBox.critical(self.view, "Plotting Error", "Invalid data given. Could not plot.")

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
                model.process_inversion_data(inversion_path)
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
                model.process_characterization_data(characterization_path)
        except KeyError:
            QtWidgets.QMessageBox.critical(self.view, "Plotting Error", "Invalid data given. Could not plot.")

    @override
    def init_devices(self) -> None:
        self.find_devices()
        self.connect_devices()
        # self.apply_configurations()

    @override
    def find_devices(self) -> None:
        try:
            self.motherboard.find_port()
        except OSError:
            logging.error("Could not find Motherboard")
        try:
            self.laser.find_port()
        except OSError:
            logging.error("Could not find Laser Driver")
        try:
            self.tec.find_port()
        except OSError:
            logging.error("Could not find TEC Driver")

    @override
    def connect_devices(self) -> None:
        if self.motherboard.is_found:
            try:
                self.motherboard.open()
                self.motherboard.run()
                self.motherboard.process_measured_data()
                # self.await_shutdown()
            except OSError:
                logging.error("Could not connect with Motherboard")
        if self.laser.is_found:
            try:
                self.laser.open()
                self.laser.run()
                self.laser.process_measured_data()
            except OSError:
                logging.error("Could not connect with Laser Driver")
        if self.tec.is_found:
            try:
                self.tec.open()
                self.tec.run()
                self.tec.process_measured_data()
            except OSError:
                logging.error("Could not connect with TEC Driver")


T = typing.TypeVar("T")


def _string_to_number(parent: QtWidgets.QWidget, string_number: str, cast: typing.Callable[[str], T]) -> T:
    try:
        return cast(string_number)
    except ValueError:
        logging.error("Could not apply new value. Invalid symbols encountered.")
        QtWidgets.QMessageBox.critical(parent, "Value Error", "Could not apply new value. Invalid symbols encountered.")
        raise ValueError


class Laser:
    def __init__(self):
        self.laser = model.Laser()
        self.last_file_path = os.getcwd()

    @property
    @abc.abstractmethod
    def view(self) -> QtWidgets.QWidget:
        ...

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
        self.laser = model.PumpLaser()

    @property
    @override
    def view(self) -> view.hardware.PumpLaser:
        return self._view

    def enable_pump_laser(self) -> None:
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
        self.laser = model.ProbeLaser()
        self._view = view.hardware.ProbeLaser(self)

    @property
    @override
    def view(self) -> view.hardware.ProbeLaser:
        return self._view

    def enable_laser(self) -> None:
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
        effective_bits: int = model.CURRENT_BITS - bits
        if effective_bits != self.laser.current_bits_probe_laser:
            self.laser.current_bits_probe_laser = effective_bits

    def fire_configuration_change(self) -> None:
        self.laser.fire_configuration_change()


class Tec:
    def __init__(self, laser: int):
        self.tec = model.Tec(laser)
        self.laser = laser
        self.heating = False
        self.cooling = False
        self._view = view.hardware.Tec(self, laser)
        self.last_file_path = os.getcwd()

    @property
    @override
    def view(self) -> view.hardware.Tec:
        return self._view

    def save_configuration_as(self) -> None:
        file_path = save_as(parent=self.view, file_type="JSON File", file_extension="json", name="TEC Configuration")
        if file_path:
            self.tec.config_path = file_path  # The actual file path
            self.tec.save_configuration()

    def save_configuration(self) -> None:
        self.tec.save_configuration()

    def load_configuration(self) -> None:
        config_path, self.last_file_path = _get_file_path(self.view, "TEC Driver", self.last_file_path,
                                                          "JSON File (*.json);; All Files (*)")
        if config_path:
            self.tec.config_path = config_path
        else:
            return
        self.tec.load_configuration()
        self.fire_configuration_change()

    def apply_configuration(self) -> None:
        self.tec.apply_configuration()

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
                          "Pump Laser" if self.laser == model.Tec.PUMP_LASER else "Probe Laser")

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
            self.tec.setpoint_temperature = model.ROOM_TEMPERATURE

    def update_loop_time(self, loop_time: str) -> None:
        self.tec.loop_time = _string_to_number(self.view, loop_time, cast=int)

    def update_max_power(self, max_power: str) -> None:
        try:
            self.tec.max_power = _string_to_number(self.view, max_power, cast=float)
        except ValueError:
            self.tec.max_power = 0

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
