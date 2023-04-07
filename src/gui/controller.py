import logging
import os
import threading
import typing

from PyQt5 import QtWidgets
from PyQt5.QtCore import Qt

import hardware
from gui import model
from gui import view


class MainApplication(QtWidgets.QApplication):
    def __init__(self, argv=""):
        QtWidgets.QApplication.__init__(self, argv)
        self.logging_model = model.Logging()
        self.view = view.MainWindow(self)
        # threading.excepthook = self.thread_exception

    def close(self) -> None:
        self.view.close()

    def thread_exception(self, args) -> None:
        if args.exc_type == KeyError:
            QtWidgets.QMessageBox.critical(self.view, "File Error", "Invalid file given or missing headers.")
        elif args.exc_type == TimeoutError:
            QtWidgets.QMessageBox.critical(self.view, "Timeout Error", "Timeout Error")
        else:
            QtWidgets.QMessageBox.critical(self.view, "Error", f"{args.exc_type} error occurred.")


class Home:
    def __init__(self, parent, main_app: QtWidgets.QApplication):
        self.view = parent
        self.main_app = main_app
        self.settings_model = model.SettingsTable()
        self.calculation_model = model.Calculation()
        self.pump_laser_enabled = False
        self.probe_laser_enabled = False
        self.daq_enabled = False
        self.last_file_path = os.getcwd()
        self.settings_model.setup_settings_file()
        self.laser = model.Laser()
        self.motherboard = model.Motherboard()
        self.tec = model.Tec()
        self.clean_air = False
        self.find_devices()

    def valve_change(self) -> None:
        if not self.clean_air:
            view.toggle_button(True, self.view.buttons["Clean Air"])
            self.clean_air = True
        else:
            view.toggle_button(False, self.view.buttons["Clean Air"])
            self.clean_air = False

    def set_destination_folder(self) -> None:
        destination_folder = QtWidgets.QFileDialog.getExistingDirectory(self.view, "Destination Folder",
                                                                        self.calculation_model.destination_folder)
        if destination_folder:
            self.calculation_model.destination_folder = destination_folder

    def get_file_path(self, dialog_name: str) -> str:
        file_path = QtWidgets.QFileDialog.getOpenFileName(self.view, directory=self.last_file_path, caption=dialog_name,
                                                          filter="All Files (*);; CSV File (*.csv);; TXT File (*.txt")
        if file_path[0]:
            self.last_file_path = file_path[0]
        return file_path[0]

    def save_settings(self) -> None:
        self.settings_model.save()

    def load_settings(self):
        file_path = QtWidgets.QFileDialog.getOpenFileName(self.view, caption="Load SettingsTable",
                                                          filter="All Files (*);; CSV File (*.csv);; TXT File (*.txt")
        if file_path:
            self.settings_model.file_path = file_path[0]  # The actual file path
            self.settings_model.load()

    def calculate_decimation(self) -> None:
        decimation_file_path = self.get_file_path("Decimation")
        if not decimation_file_path:
            return
        threading.Thread(target=self.calculation_model.calculate_decimation, args=[decimation_file_path]).start()

    def calculate_inversion(self) -> None:
        inversion_path = self.get_file_path("Inversion")
        if not inversion_path:
            return
        threading.Thread(target=self.calculation_model.calculate_inversion,
                         args=[self.settings_model.file_path, inversion_path]).start()

    def calculate_characterisation(self) -> None:
        characterisation_path = self.get_file_path("Characterisation")
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
            model.process_inversion_data(self.get_file_path("Inversion"))
        except KeyError:
            QtWidgets.QMessageBox.critical(self.view, "Plotting Error", "Invalid data given. Could not plot.")

    def plot_dc(self) -> None:
        try:
            model.process_dc_data(self.get_file_path("Decimation"))
        except KeyError:
            QtWidgets.QMessageBox.critical(self.view, "Plotting Error", "Invalid data given. Could not plot.")

    def plot_characterisation(self) -> None:
        try:
            model.process_characterization_data(self.get_file_path("Characterisation"))
        except KeyError:
            QtWidgets.QMessageBox.critical(self.view, "Plotting Error", "Invalid data given. Could not plot.")

    def find_devices(self) -> None:
        try:
            self.motherboard.driver.find_port()
        except OSError:
            logging.error("Could not find Motherboard")
        try:
            self.laser.driver.find_port()
        except OSError:
            logging.error("Could not find Laser Driver")
        try:
            self.tec.driver.find_port()
        except OSError:
            logging.error("Could not find TEC Driver")

    def shutdown(self) -> None:
        QtWidgets.QApplication.setOverrideCursor(Qt.WaitCursor)
        logging.warning("Shutdown started")
        model.shutdown_procedure()
        self.main_app.quit()

    def shutdown_by_button(self) -> None:
        close = QtWidgets.QMessageBox.question(
            self.view, "QUIT", "Are you sure you want to shutdown?",
            QtWidgets.QMessageBox.StandardButton.Yes | QtWidgets.QMessageBox.StandardButton.No)
        if close == QtWidgets.QMessageBox.StandardButton.Yes:
            self.shutdown()

    def await_shutdown(self):
        def shutdown_low_energy() -> None:
            self.motherboard.shutdown_event.wait()
            self.shutdown()
        threading.Thread(target=shutdown_low_energy).start()

    def connect_devices(self) -> None:
        try:
            self.motherboard.driver.open()
            self.await_shutdown()
        except OSError:
            logging.error("Could not connect with DAQ")
        try:
            self.laser.open()
            self.laser.process_measured_data()
        except OSError:
            logging.error("Could not connect with Laser Driver")
        try:
            self.tec.open()
            self.tec.process_measured_data()
        except OSError:
            logging.error("Could not connect with Laser Driver")

    def enable_probe_laser(self) -> None:
        if not self.probe_laser_enabled:
            self.laser.driver.enable_probe_laser()
            view.toggle_button(True, self.view.buttons["Enable Probe Laser"])
            self.probe_laser_enabled = True
        else:
            view.toggle_button(False, self.view.buttons["Enable Probe Laser"])
            self.laser.driver.disable_probe_laser()
            self.probe_laser_enabled = False

    def enable_pump_laser(self) -> None:
        if not self.pump_laser_enabled:
            self.laser.driver.enable_pump_laser()
            view.toggle_button(True, self.view.buttons["Enable Pump Laser"])
            self.pump_laser_enabled = True
        else:
            view.toggle_button(False, self.view.buttons["Enable Pump Laser"])
            self.laser.driver.disable_pump_laser()
            self.pump_laser_enabled = False

    def run_measurement(self) -> None:
        if not self.daq_enabled:
            self.motherboard.driver.run()
            self.calculation_model.live_calculation()
            view.toggle_button(True, self.view.buttons["Run Measurement"])
            self.daq_enabled = True
        else:
            view.toggle_button(False, self.view.buttons["Run Measurement"])
            self.daq_enabled = False


def _string_to_float(string_value: str) -> float:
    try:
        return float(string_value)
    except ValueError:
        logging.error("Could not apply new value. Invalid symbols encountered.")
        return 0


class Laser:
    def __init__(self):
        self.laser = model.Laser()

    def update_driver_voltage(self, bits: int) -> None:
        if bits != self.laser.driver_bits:
            self.laser.driver_bits = bits

    def update_current_dac1(self, bits: int) -> None:
        if self.laser.current_bits_dac_2 != bits:
            self.laser.current_bits_dac_1 = bits

    def update_current_dac2(self, bits: int) -> None:
        if self.laser.current_bits_dac_1 != bits:
            self.laser.current_bits_dac_2 = bits

    def save_configuration(self) -> None:
        self.laser.save_configuration()

    def load_configuration(self) -> None:
        self.laser.load_configuration()
        self.laser.driver_bits = self.laser.driver_bits
        self.laser.current_bits_dac_1 = self.laser.current_bits_dac_1
        self.laser.current_bits_dac_2 = self.laser.current_bits_dac_2
        self.laser.dac_1_matrix = self.laser.dac_1_matrix
        self.laser.dac_2_matrix = self.laser.dac_2_matrix
        self.laser.current_bits_probe_laser = self.laser.current_bits_probe_laser
        self.laser.probe_laser_mode = self.laser.probe_laser_mode
        self.laser.photo_diode_gain = self.laser.photo_diode_gain

    def apply_configuration(self) -> None:
        self.laser.apply_configuration()

    def update_dac1(self, channel: int) -> typing.Callable[[int], None]:
        def set_matrix(mode: int) -> None:
            self.laser.update_dac_mode(self.laser.dac_1_matrix, channel, mode)
        return set_matrix

    def update_dac2(self, channel: int) -> typing.Callable[[int], None]:
        def set_matrix(mode: int) -> None:
            self.laser.update_dac_mode(self.laser.dac_2_matrix, channel, mode)
        return set_matrix

    def update_max_current_probe_laser(self, max_current: str) -> None:
        self.laser.probe_laser_max_current = _string_to_float(max_current)

    def update_photo_gain(self, value: int) -> None:
        if self.laser.photo_diode_gain != value + 1:
            self.laser.photo_diode_gain = value + 1

    def update_probe_laser_mode(self, index: int) -> None:
        self.laser.probe_laser_mode = index

    def update_current_probe_laser(self, bits: int) -> None:
        effective_bits: int = hardware.laser.Driver.CURRENT_BITS - bits
        if effective_bits != self.laser.current_bits_probe_laser:
            self.laser.current_bits_probe_laser = effective_bits


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
        self.tec.load_configuration()
        self.tec.update_values()

    def apply_configuration(self) -> None:
        pass

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
        if not self.heating:
            self.tec.driver.set_mode(self.laser, mode="heating")
            view.toggle_button(True, self.view.buttons["Heat"])
            view.toggle_button(False, self.view.buttons["Cool"])
            self.heating = True
            self.cooling = False
        else:
            view.toggle_button(False, self.view.buttons["Heat"])
            self.tec.driver.disable(self.laser)
            self.heating = False

    def set_cooling(self) -> None:
        if not self.cooling:
            self.tec.driver.set_mode(self.laser, mode="cooling")
            view.toggle_button(False, self.view.buttons["Heat"])
            view.toggle_button(True, self.view.buttons["Cool"])
            self.heating = False
            self.cooling = True
        else:
            view.toggle_button(False, self.view.buttons["Cool"])
            self.tec.driver.disable(self.laser)
            self.cooling = False
