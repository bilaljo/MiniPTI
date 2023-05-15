import abc
import logging
import os
import threading
import typing

from PyQt5 import QtWidgets
from PyQt5.QtCore import Qt, QCoreApplication

from .. import hardware
from . import model
from . import view


class MainApplication(QtWidgets.QApplication):
    def __init__(self, argv=""):
        QtWidgets.QApplication.__init__(self, argv)
        self.logging_model = model.Logging()
        self.view = view.MainWindow(self)
        #threading.excepthook = self.thread_exception

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


class Home:
    def __init__(self, parent: view.MainWindow, main_app: QtWidgets.QApplication):
        self.view = parent
        self.main_app = main_app
        self.settings_model = model.SettingsTable()
        self.calculation_model = model.Calculation()
        self.mother_board_model = model.Motherboard()
        self.pump_laser = model.PumpLaser()
        self.probe_laser = model.ProbeLaser()
        self.pump_laser_tec = model.Tec("Pump Laser")
        self.probe_laser_tec = model.Tec("Probe Laser")
        self.daq_enabled = False
        self.last_file_path = os.getcwd()
        self.settings_model.setup_settings_file()
        self.find_devices()

    def update_bypass(self) -> None:
        self.mother_board_model.bypass = not self.mother_board_model.bypass

    def update_valve_period(self, period: str) -> None:
        period = _string_to_int(period)
        try:
            self.mother_board_model.valve_period = period
        except ValueError as error:
            info_text = "Value must be a positive integer"
            logging.error(str(error))
            logging.warning(info_text)
            QtWidgets.QMessageBox.critical(self.view, "Valve Error", f"{str(error)}. {info_text}")

    def update_valve_duty_cycle(self, duty_cycle: str) -> None:
        duty_cycle = _string_to_int(duty_cycle)
        try:
            self.mother_board_model.valve_duty_cycle = duty_cycle
        except ValueError as error:
            info_text = "Value must be an integer between 0 and 100"
            logging.error(str(error))
            logging.warning(info_text)
            QtWidgets.QMessageBox.critical(self.view, "Valve Error", f"{str(error)}. {info_text}")

    def update_automatic_valve_switch(self, automatic_valve_switch: bool) -> None:
        self.mother_board_model.automatic_valve_switch = automatic_valve_switch

    def fire_motherboard_configuration_change(self) -> None:
        self.mother_board_model.fire_configuration_change()

    def set_destination_folder(self) -> None:
        destination_folder = QtWidgets.QFileDialog.getExistingDirectory(self.view, "Destination Folder",
                                                                        self.calculation_model.destination_folder,
                                                                        QtWidgets.QFileDialog.ShowDirsOnly
                                                                        )
        if destination_folder:
            self.calculation_model.destination_folder = destination_folder

    def get_file_path(self, dialog_name: str, files: str) -> str:
        file_path = QtWidgets.QFileDialog.getOpenFileName(self.view, directory=self.last_file_path,
                                                          caption=dialog_name, filter=files)
        if file_path[0]:
            self.last_file_path = file_path[0]
        return file_path[0]

    def save_settings(self) -> None:
        self.settings_model.save()

    def load_settings(self):
        file_path = QtWidgets.QFileDialog.getOpenFileName(self.view, caption="Load SettingsTable",
                                                          filter="CSV File (*.csv);;"
                                                                 " TXT File (*.txt);; All Files (*);;"
                                                          )
        if file_path:
            self.settings_model.file_path = file_path[0]  # The actual file path
            self.settings_model.load()

    @staticmethod
    def save_motherboard_configuration() -> None:
        model.Motherboard.save_configuration()

    def load_motherboard_configuration(self) -> None:
        if file_path := self.get_file_path("Valve", "CONF File (*.conf);; All Files (*)"):
            try:
                self.mother_board_model.config_path = file_path[0]
            except ValueError as error:
                logging.error(error)
            else:
                self.mother_board_model.load_configuration()

    def calculate_decimation(self) -> None:
        decimation_file_path = self.get_file_path("Decimation", "HDF5 File (*.hdf5);; All Files (*)")
        if not decimation_file_path:
            return
        threading.Thread(target=self.calculation_model.calculate_decimation,
                         args=[decimation_file_path]).start()

    def calculate_inversion(self) -> None:
        inversion_path = self.get_file_path("Inversion", "CSV File (*.csv);; TXT File (*.txt);; All Files (*)")
        if not inversion_path:
            return
        threading.Thread(target=self.calculation_model.calculate_inversion,
                         args=[self.settings_model.file_path, inversion_path]).start()

    def calculate_characterisation(self) -> None:
        characterisation_path = self.get_file_path(
            "Characterisation", "CSV File (*.csv);; TXT File (*.txt);; All Files (*)")
        if not characterisation_path:
            return
        use_settings = QtWidgets.QMessageBox.question(self.view, "Characterisation",
                                                      "Do you want to use the settings values?",
                                                      QtWidgets.QMessageBox.StandardButton.Yes
                                                      | QtWidgets.QMessageBox.StandardButton.No)
        use_settings = use_settings == QtWidgets.QMessageBox.StandardButton.Yes
        threading.Thread(target=self.calculation_model.calculate_characterisation,
                         args=[characterisation_path, use_settings, self.settings_model.file_path]).start()

    def plot_inversion(self) -> None:
        try:
            model.process_inversion_data(self.get_file_path("Inversion",
                                                            "CSV File (*.csv);; TXT File (*.txt);; All Files (*)")
                                         )
        except KeyError:
            QtWidgets.QMessageBox.critical(self.view, "Plotting Error", "Invalid data given. Could not plot.")

    def plot_dc(self) -> None:
        try:
            model.process_dc_data(self.get_file_path("Decimation",
                                                     "CSV File (*.csv);; TXT File (*.txt);; All Files (*)"))
        except KeyError:
            QtWidgets.QMessageBox.critical(self.view, "Plotting Error", "Invalid data given. Could not plot.")

    def plot_characterisation(self) -> None:
        try:
            model.process_characterization_data(
                self.get_file_path("Characterisation", "CSV File (*.csv);; TXT File (*.txt);; All Files (*)"))
        except KeyError:
            QtWidgets.QMessageBox.critical(self.view, "Plotting Error", "Invalid data given. Could not plot.")

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

    def shutdown(self) -> None:
        QtWidgets.QApplication.setOverrideCursor(Qt.WaitCursor)
        logging.warning("Shutdown started")
        model.shutdown_procedure()
        self.view.close()
        self.main_app.quit()

    def shutdown_by_button(self) -> None:
        close = QtWidgets.QMessageBox.question(self.view, "QUIT", "Are you sure you want to shutdown?",
                                               QtWidgets.QMessageBox.StandardButton.Yes
                                               | QtWidgets.QMessageBox.StandardButton.No)
        if close == QtWidgets.QMessageBox.StandardButton.Yes:
            self.shutdown()

    def await_shutdown(self):
        def shutdown_low_energy() -> None:
            self.mother_board_model.shutdown_event.wait()
            self.shutdown()

        threading.Thread(target=shutdown_low_energy, daemon=True).start()

    def connect_devices(self) -> None:
        try:
            model.Motherboard.open()
            self.await_shutdown()
        except OSError:
            logging.error("Could not connect with Motherboard")
        try:
            model.Laser.open()
            model.Laser.process_measured_data()
        except OSError:
            logging.error("Could not connect with Laser Driver")
        try:
            model.Tec.open()
            model.Tec.process_measured_data()
        except OSError:
            logging.error("Could not connect with Tec Driver")

    def enable_probe_laser(self) -> None:
        if not self.probe_laser.connected:
            QtWidgets.QMessageBox.critical(self.view, "IO Error",
                                           "Cannot enable Probe Laser. Probe Laser is not connected.")
            logging.error("Cannot enable Probe Laser")
            logging.warning("Probe Laser is not connected")
        else:
            if not self.probe_laser.enabled:
                self.view.current_probe_laser.clear()
                self.probe_laser.enabled = True
            else:
                self.probe_laser.enabled = False
            logging.debug(f"{'Enabled' if self.probe_laser.enabled else 'Disabled'} Probe Laser")

    def enable_pump_laser(self) -> None:
        if not self.pump_laser.connected:
            QtWidgets.QMessageBox.critical(self.view, "IO Error",
                                           "Cannot enable Pump Laser. Pump Laser is not connected.")
            logging.error("Cannot enable Pump Laser")
            logging.warning("Pump Laser is not connected")
        else:
            if not self.pump_laser.enabled:
                self.view.current_pump_laser.clear()
                self.pump_laser.enabled = True
            else:
                self.pump_laser.enabled = False
                logging.debug(f"{'Enabled' if self.pump_laser.enabled else 'Disabled'} Probe Laser")

    def enable_tec_pump_laser(self) -> None:
        if not self.pump_laser_tec.connected:
            QtWidgets.QMessageBox.critical(self.view, "IO Error",
                                           "Cannot enable Tec Driver of Pump Laser. Tec Driver is not connected.")
            logging.error("Cannot enable Tec Driver of Pump Laser")
            logging.warning("Tec Driver is not connected")
        else:
            if not self.pump_laser_tec.enabled:
                self.view.temperature_pump_laser.clear()
                self.pump_laser_tec.enabled = True
            else:
                self.pump_laser_tec.enabled = False
            logging.debug(f"{'Enabled' if self.pump_laser_tec.enabled else 'Disabled'} Tec Driver of Pump Laser")

    def enable_tec_probe_laser(self) -> None:
        if not self.probe_laser_tec.connected:
            QtWidgets.QMessageBox.critical(self.view, "IO Error",
                                           "Cannot enable Tec Driver of Probe Laser. Tec Driver is not connected.")
            logging.error("Cannot enable Tec Driver of Probe Laser")
            logging.warning("Tec Driver is not connected")
        else:
            if not self.probe_laser_tec.enabled:
                self.view.temperature_probe_laser.clear()
                self.probe_laser_tec.enabled = True
            else:
                self.probe_laser_tec.enabled = False
            logging.debug(f"{'Enabled' if self.probe_laser_tec.enabled else 'Disabled'} Tec Driver of Probe Laser")

    def run_measurement(self) -> None:
        if not self.daq_enabled:
            if not self.mother_board_model.run():
                QtWidgets.QMessageBox.critical(self.view, "IO Error",
                                               "Cannot run measurement. Motherboard is not connected.")
                return
            # Reset all measurement plots
            self.view.dc.clear()
            self.view.amplitudes.clear()
            self.view.output_phases.clear()
            self.view.interferometric_phase.clear()
            self.view.sensitivity.clear()
            self.view.symmetry.clear()
            self.view.pti_signal.clear()
            self.calculation_model.live_calculation()
            view.toggle_button(True, self.view.buttons["Run Measurement"])
            self.daq_enabled = True
        else:
            view.toggle_button(False, self.view.buttons["Run Measurement"])
            self.mother_board_model.stop()
            self.daq_enabled = False

    def set_clean_air(self, bypass: bool) -> None:
        self.mother_board_model.bypass = bypass


def _string_to_float(string_value: str) -> float:
    try:
        return float(string_value)
    except ValueError:
        logging.error("Could not apply new value. Invalid symbols encountered.")
        return -1


def _string_to_int(string_value: str) -> int:
    try:
        return int(string_value)
    except ValueError:
        logging.error("Could not apply new value. Invalid symbols encountered.")
        return 0


def _driver_config_file_path(last_directory: str, parent: QtWidgets.QWidget, device: str) -> str:
    file_path = QtWidgets.QFileDialog.getOpenFileName(parent, directory=last_directory,
                                                      caption=f"{device} config file",
                                                      filter="All Files (*);; JSON (.json)")
    return file_path[0]


class Laser:
    def __init__(self, parent):
        self.parent = parent
        self.laser = model.Laser()

    def load_configuration(self) -> None:
        if filepath := _driver_config_file_path(last_directory=self.laser.config_path,
                                                parent=self.parent, device="Laser Driver"):
            self.laser.config_path = filepath
        else:
            return
        self.laser.load_configuration()
        self.fire_configuration_change()

    def save_configuration(self) -> None:
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

    def update_max_current_probe_laser(self, max_current: str) -> None:
        new_max_current = _string_to_float(max_current)
        if new_max_current == -1:
            return
        self.laser.probe_laser_max_current = new_max_current

    def update_photo_gain(self, value: int) -> None:
        if self.laser.photo_diode_gain != value + 1:
            self.laser.photo_diode_gain = value + 1

    def update_probe_laser_mode(self, index: int) -> None:
        self.laser.probe_laser_mode = index

    def update_current_probe_laser(self, bits: int) -> None:
        effective_bits: int = hardware.laser.Driver.CURRENT_BITS - bits
        if effective_bits != self.laser.current_bits_probe_laser:
            self.laser.current_bits_probe_laser = effective_bits

    def fire_configuration_change(self) -> None:
        self.laser.fire_configuration_change()


class Tec:
    def __init__(self, laser: str, parent):
        self.tec = model.Tec(laser)
        self.heating = False
        self.cooling = False
        self.view = parent
        self.laser = laser

    def save_configuration(self) -> None:
        self.tec.save_configuration()

    def load_configuration(self) -> None:
        if filepath := _driver_config_file_path(last_directory=self.tec.config_path, parent=self.view,
                                                device="Tec Driver"):
            self.tec.config_path = filepath
        else:
            return
        self.tec.load_configuration()
        self.fire_configuration_change()

    def apply_configuration(self) -> None:
        self.tec.apply_configuration()

    def update_d_value(self, d_value: str) -> None:
        self.tec.d_value = _string_to_float(d_value)

    def update_i_1_value(self, i_1_value: str) -> None:
        self.tec.i_1_value = _string_to_float(i_1_value)

    def update_i_2_value(self, i_2_value: str) -> None:
        self.tec.i_2_value = _string_to_float(i_2_value)

    def update_p_value(self, p_value: str) -> None:
        self.tec.p_value = _string_to_float(p_value)

    def update_setpoint_temperature(self, setpoint_temperature: str) -> None:
        self.tec.setpoint_temperature = _string_to_float(setpoint_temperature)

    def update_loop_time(self, loop_time: str) -> None:
        self.tec.loop_time = _string_to_float(loop_time)

    def update_reference_resistor(self, reference_resistor: str) -> None:
        self.tec.reference_resistor = _string_to_float(reference_resistor)

    def update_max_power(self, max_power: str) -> None:
        self.tec.max_power = _string_to_float(max_power)

    def set_heating(self) -> None:
        self.tec.heating = True

    def set_cooling(self) -> None:
        self.tec.cooling = True

    def fire_configuration_change(self) -> None:
        self.tec.fire_configuration_change()
