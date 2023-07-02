import abc
import logging
import os
import threading
import typing

from PyQt5 import QtWidgets, QtCore
from PyQt5.QtCore import Qt, QCoreApplication

from .. import hardware
from . import model
from . import view


class MainApplication(QtWidgets.QApplication):
    def __init__(self, argv=""):
        QtWidgets.QApplication.__init__(self, argv)
        self.logging_model = model.Logging()
        self.view = view.MainWindow(self)
        # threading.excepthook = self.thread_exception

    def close(self) -> None:
        model.Motherboard.driver.running.clear()
        model.Motherboard.driver.close()
        model.PumpLaser.driver.close()
        model.Tec.close()
        self.view.close()
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


def _shutdown(controller) -> None:
    QtWidgets.QApplication.setOverrideCursor(Qt.WaitCursor)
    logging.warning("Shutdown started")
    model.shutdown_procedure()
    controller.view.close()
    controller.main_app.quit()


class Home:
    def __init__(self, parent, main_app: QtWidgets.QApplication, settings_controller: "Settings"):
        self.view = parent
        self.main_app = main_app
        self.calculation_model = model.LiveCalculation()
        self.motherboard = model.Motherboard()
        self.laser = model.Laser()
        self.pump_laser = model.PumpLaser()
        self.probe_laser = model.ProbeLaser()
        self.pump_laser_tec = model.Tec(model.Tec.PUMP_LASER)
        self.probe_laser_tec = model.Tec(model.Tec.PROBE_LASER)
        settings_controller.raw_data_changed.connect(self.calculation_model.set_raw_data_saving)

    def fire_motherboard_configuration_change(self) -> None:
        self.motherboard.fire_configuration_change()

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

    def enable_probe_laser(self) -> None:
        if not self.probe_laser.connected:
            QtWidgets.QMessageBox.critical(self.view, "IO Error",
                                           "Cannot enable Probe Laser. Probe Laser is not connected.")
            logging.error("Cannot enable Probe Laser")
            logging.warning("Probe Laser is not connected")
        else:
            if not self.probe_laser.enabled:
                self.probe_laser.enabled = True
            else:
                self.probe_laser.enabled = False
            logging.debug(f"{'Enabled' if self.probe_laser.enabled else 'Disabled'} Probe Laser")

    def enable_tec_pump_laser(self) -> None:
        if not self.pump_laser_tec.connected:
            QtWidgets.QMessageBox.critical(self.view, "IO Error",
                                           "Cannot enable Tec Driver of Pump Laser. Tec Driver is not connected.")
            logging.error("Cannot enable Tec Driver of Pump Laser")
            logging.warning("Tec Driver is not connected")
        else:
            if not self.pump_laser_tec.enabled:
                self.pump_laser_tec.enabled = True
            else:
                self.pump_laser_tec.enabled = False
            logging.debug(f"{'Enabled' if self.pump_laser_tec.enabled else 'Disabled'} Tec Driver of Pump Laser")

    def set_clean_air(self, bypass: bool) -> None:
        self.motherboard.bypass = bypass


class Settings:
    def __init__(self, main_app, parent):
        self.settings_table_model = model.SettingsTable()
        self.main_app = main_app
        self.view = parent
        self.motherboard = model.Motherboard()
        self.destination_folder = model.DestinationFolder()
        self.last_file_path = os.getcwd()
        self.motherboard = model.Motherboard()
        self.laser = model.Laser()
        self.pump_laser = model.PumpLaser()
        self.probe_laser = model.ProbeLaser()
        self.pump_laser_tec = model.Tec(model.Tec.PUMP_LASER)
        self.probe_laser_tec = model.Tec(model.Tec.PROBE_LASER)
        self.motherboard.fire_configuration_change()
        threading.Thread(target=self.init_devices, daemon=True, name="Init Devices Thread").start()

    @property
    def raw_data_changed(self) -> QtCore.pyqtSignal:
        return self.view.save_raw_data.stateChanged

    def fire_mother_board_configuration(self) -> None:
        self.motherboard.fire_configuration_change()

    def save_settings(self) -> None:
        self.settings_table_model.save()

    def save_settings_as(self) -> None:
        file_path = save_as(parent=self.view, file_type="CSV File", file_extension="csv",
                            name="Algorithm Configuration")
        if file_path:
            self.settings_table_model.file_path = file_path
            self.settings_table_model.save()

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

    def init_devices(self) -> None:
        try:
            self.find_devices()
        except OSError:
            return
        self.connect_devices()
        self.apply_configurations()

    @staticmethod
    def find_devices() -> None:
        try:
            model.Motherboard.find_port()
        except OSError:
            logging.error("Could not find Motherboard")
        try:
            model.Laser.find_port()
        except OSError:
            logging.error("Could not find Laser Driver")
        try:
            model.Tec.find_port()
        except OSError:
            logging.error("Could not find TEC Driver")
        else:
            return
        raise OSError

    def await_shutdown(self):
        def shutdown_low_energy() -> None:
            self.motherboard.shutdown_event.wait()
            _shutdown(self)
        threading.Thread(target=shutdown_low_energy, daemon=True).start()

    def update_bypass(self) -> None:
        self.motherboard.bypass = not self.motherboard.bypass

    def connect_devices(self) -> None:
        try:
            self.motherboard.open()
            self.motherboard.run()
            self.motherboard.process_measured_data()
            self.await_shutdown()
        except OSError:
            logging.error("Could not connect with Motherboard")
        try:
            self.laser.open()
            self.laser.run()
            self.laser.process_measured_data()
        except OSError:
            logging.error("Could not connect with Laser Driver")
        try:
            self.pump_laser_tec.open()
            self.pump_laser_tec.run()
            self.pump_laser_tec.process_measured_data()
        except OSError:
            logging.error("Could not connect with TEC Driver")

    def shutdown_by_button(self) -> None:
        close = QtWidgets.QMessageBox.question(self.view, "QUIT", "Are you sure you want to shutdown?",
                                               QtWidgets.QMessageBox.StandardButton.Yes
                                               | QtWidgets.QMessageBox.StandardButton.No)
        if close == QtWidgets.QMessageBox.StandardButton.Yes:
            _shutdown(self)

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

    def update_automatic_valve_switch(self, automatic_valve_switch: bool) -> None:
        self.motherboard.automatic_valve_switch = automatic_valve_switch

    def set_destination_folder(self) -> None:
        destination_folder = QtWidgets.QFileDialog.getExistingDirectory(self.view, "Destination Folder",
                                                                        self.destination_folder.folder,
                                                                        QtWidgets.QFileDialog.ShowDirsOnly)
        if destination_folder:
            self.destination_folder.folder = destination_folder

    @staticmethod
    def save_motherboard_configuration() -> None:
        model.Motherboard.save_configuration()

    def load_motherboard_configuration(self) -> None:
        file_path, self.last_file_path = _get_file_path(self.view, "Valve", self.last_file_path,
                                                        "INI File (*.ini);; All Files (*)")
        if file_path:
            try:
                self.motherboard.config_path = file_path
            except ValueError as error:
                logging.error(error)
            else:
                self.motherboard.load_configuration()


class Utilities:
    def __init__(self, parent, settings: "Settings"):
        self.view = parent
        self.calculation_model = model.OfflineCalculation()
        self.last_file_path = os.getcwd()
        self.settings_controller = settings

    def calculate_decimation(self) -> None:
        decimation_file_path, self.last_file_path = _get_file_path(self.view, "Decimation", self.last_file_path,
                                                                   "Binary File (*.bin);; All Files (*)")
        if not decimation_file_path:
            return
        threading.Thread(target=self.calculation_model.calculate_decimation,
                         args=[decimation_file_path]).start()

    def plot_dc(self) -> None:
        try:
            decimation_path, self.last_file_path = _get_file_path(self.view, "Decimation", self.last_file_path,
                                                                  "CSV File (*.csv);; TXT File (*.txt);; All Files (*)")
            if decimation_path:
                model.process_dc_data(decimation_path)
        except KeyError:
            QtWidgets.QMessageBox.critical(self.view, "Plotting Error", "Invalid data given. Could not plot.")

    def calculate_pti_inversion(self) -> None:
        inversion_path, self.last_file_path = _get_file_path(self.view, "Inversion", self.last_file_path,
                                                             "CSV File (*.csv);; TXT File (*.txt);; All Files (*)")
        if not inversion_path:
            return
        threading.Thread(target=self.calculation_model.calculate_inversion,
                         args=[self.settings_controller.settings_table_model.file_path, inversion_path]).start()

    def plot_inversion(self) -> None:
        try:
            inversion_path, self.last_file_path = _get_file_path(self.view, "Inversion", self.last_file_path,
                                                                 "CSV File (*.csv);; TXT File (*.txt);; All Files (*)")
            if inversion_path:
                model.process_inversion_data(inversion_path)
        except KeyError:
            QtWidgets.QMessageBox.critical(self.view, "Plotting Error", "Invalid data given. Could not plot.")

    def calculate_characterisation(self) -> None:
        characterisation_path, self.last_file_path = _get_file_path(self.view, "Characterisation", self.last_file_path,
                                                                    "CSV File (*.csv);; TXT File (*.txt);;"
                                                                    " All Files (*)")
        if not characterisation_path:
            return
        use_settings = QtWidgets.QMessageBox.question(self.view, "Characterisation",
                                                      "Do you want to use the settings values?",
                                                      QtWidgets.QMessageBox.StandardButton.Yes
                                                      | QtWidgets.QMessageBox.StandardButton.No)
        use_settings = use_settings == QtWidgets.QMessageBox.StandardButton.Yes
        threading.Thread(target=self.calculation_model.calculate_characterisation,
                         args=[characterisation_path, use_settings,
                               self.settings_controller.settings_table_model.file_path]).start()

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


T = typing.TypeVar("T")


def _string_to_number(parent: QtWidgets.QWidget, string_number: str, cast: typing.Callable[[str], T]) -> T:
    try:
        return cast(string_number)
    except ValueError:
        logging.error("Could not apply new value. Invalid symbols encountered.")
        QtWidgets.QMessageBox.critical(parent, "Value Error", "Could not apply new value. Invalid symbols encountered.")
        raise ValueError


class Laser:
    def __init__(self, parent):
        self.view = parent
        self.laser = model.Laser()
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
    def __init__(self, parent):
        Laser.__init__(self, parent)
        self.laser = model.PumpLaser()

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
    def __init__(self, parent):
        Laser.__init__(self, parent)
        self.laser = model.ProbeLaser()
        self.view = parent

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
        effective_bits: int = hardware.laser.LowPowerLaser.CURRENT_BITS - bits
        if effective_bits != self.laser.current_bits_probe_laser:
            self.laser.current_bits_probe_laser = effective_bits

    def fire_configuration_change(self) -> None:
        self.laser.fire_configuration_change()


class Tec:
    def __init__(self, laser: int, parent):
        self.tec = model.Tec(laser)
        self.heating = False
        self.cooling = False
        self.view = parent
        self.last_file_path = os.getcwd()

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

    def update_d_value(self, d_value: str) -> None:
        try:
            self.tec.d_value = _string_to_number(self.view, d_value, cast=int)
        except ValueError:
            self.tec.d_value = 0

    def update_i_1_value(self, i_1_value: str) -> None:
        try:
            self.tec.i_1_value = _string_to_number(self.view, i_1_value, cast=int)
        except ValueError:
            self.tec.i_1_value = 0

    def update_i_2_value(self, i_2_value: str) -> None:
        try:
            self.tec.i_2_value = _string_to_number(self.view, i_2_value, cast=int)
        except ValueError:
            self.tec.i_2_value = 0

    def update_p_value(self, p_value: str) -> None:
        try:
            self.tec.p_value = _string_to_number(self.view, p_value, cast=int)
        except ValueError:
            self.tec.p_value = 0

    def update_setpoint_temperature(self, setpoint_temperature: str) -> None:
        try:
            self.tec.setpoint_temperature = _string_to_number(self.view, setpoint_temperature, cast=float)
        except ValueError:
            self.tec.setpoint_temperature = hardware.tec.ROOM_TEMPERATURE_CELSIUS

    def update_loop_time(self, loop_time: str) -> None:
        self.tec.loop_time = _string_to_number(self.view, loop_time, cast=int)

    def update_reference_resistor(self, reference_resistor: str) -> None:
        try:
            self.tec.reference_resistor = _string_to_number(self.view, reference_resistor, cast=float)
        except ValueError:
            self.tec.reference_resistor = 0

    def update_max_power(self, max_power: str) -> None:
        try:
            self.tec.max_power = _string_to_number(self.view, max_power, cast=int)
        except ValueError:
            self.tec.max_power = 0

    def set_heating(self) -> None:
        self.tec.heating = True

    def set_cooling(self) -> None:
        self.tec.cooling = True

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
