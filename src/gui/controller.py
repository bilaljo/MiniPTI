import logging
import threading
import typing

from PySide6 import QtWidgets

import hardware
from gui import model
from gui import view


class MainApplication(QtWidgets.QApplication):
    def __init__(self, argv=""):
        QtWidgets.QApplication.__init__(self, argv)
        self.driver_model = model.Hardware()
        self.settings_model = model.SettingsTable()
        self.logging_model = model.Logging()
        self.driver_controller = Hardware(self.driver_model)
        self.view = view.MainWindow(self, self.driver_controller)
        # threading.excepthook = self.thread_exception
        self.driver_model.find_device()
        self.settings_model.setup_settings_file()

    def close(self):
        self.driver_model.close()
        self.view.close()

    def thread_exception(self, args):
        if args.exc_type == KeyError:
            QtWidgets.QMessageBox.critical(self.view, "File Error", "Invalid file given or missing headers.")
        elif args.exc_type == TimeoutError:
            QtWidgets.QMessageBox.critical(self.view, "Timeout Error", "Timeout Error")
        else:
            QtWidgets.QMessageBox.critical(self.view, "Error", f"{args.exc_type} error occurred.")


class Hardware:
    def __init__(self, hardware_model: model.Hardware):
        self.hardware_model = hardware_model

    def update_driver_voltage(self, bits):
        self.hardware_model.laser.driver_bits = bits

    def update_current_dac1(self, bits):
        self.hardware_model.laser.current_bits_dac_1 = bits

    def update_current_dac2(self, bits):
        self.hardware_model.laser.current_bits_dac_2 = bits

    def update_current_probe_laser(self, bits):
        self.hardware_model.laser.current_bits_probe_laser = bits

    def update_configuration(self):
        self.hardware_model.laser.update_configuration()

    def mode_dac1(self, i) -> typing.Callable:
        return self.hardware_model.laser.mode_dac1(i)

    def mode_dac2(self, i) -> typing.Callable:
        return self.hardware_model.laser.mode_dac2(i)

    def update_photo_gain(self, value):
        self.hardware_model.laser.photo_diode_gain = value + 1

    def update_probe_laser_mode(self, index):
        match index:
            case view.ProbeLaser.CONSTANT_LIGHT:
                self.hardware_model.laser.probe_laser.constant_light = True
                self.hardware_model.laser.probe_laser.constant_current = False
            case view.ProbeLaser.CONSTANT_LIGHT:
                self.hardware_model.laser.probe_laser.constant_light = False
                self.hardware_model.laser.probe_laser.constant_current = True
            case _:
                self.hardware_model.laser.probe_laser.constant_light = False
                self.hardware_model.laser.probe_laser.constant_light = True

    def update_max_current_probe_laser(self, max_current):
        try:
            self.probe_laser.max_current_mA = float(max_current)
        except ValueError:
            logging.error("Could not apply new value. Invalid symbols encountered.")

    def load_config(self):
        self.hardware_model.laser.load_config()

    @property
    def pump_laser(self):
        return self.hardware_model.laser.driver.pump_laser

    @property
    def probe_laser(self):
        return self.hardware_model.laser.driver.probe_laser


class Home:
    def __init__(self, driver_controller: Hardware, main_controller: MainApplication, parent):
        self.view = parent
        self.calculation_model = model.Calculation()
        self.main_controller = main_controller
        self.driver_controller = driver_controller

    def get_file_path(self, dialog_name):
        file_path = QtWidgets.QFileDialog.getOpenFileName(self.view, caption=dialog_name,
                                                          filter="All Files (*);; CSV File (*.csv);; TXT File (*.txt")
        return file_path[0]

    def save_settings(self):
        self.main_controller.settings_model.save()

    def load_settings(self):
        file_path = QtWidgets.QFileDialog.getOpenFileName(self.view, caption="Load SettingsTable",
                                                          filter="All Files (*);; CSV File (*.csv);; TXT File (*.txt")
        if file_path:
            self.main_controller.settings_model.file_path = file_path[0]  # The actual file path
            self.main_controller.settings_model.load()

    def calculate_decimation(self):
        decimation_file_path = self.get_file_path("Decimation")
        if not decimation_file_path:
            return
        threading.Thread(target=self.calculation_model.calculate_decimation, args=[decimation_file_path]).start()

    def calculate_inversion(self):
        inversion_path = self.get_file_path("Inversion")
        if not inversion_path:
            return
        threading.Thread(target=self.calculation_model.calculate_inversion,
                         args=[self.main_controller.settings_model.file_path, inversion_path]).start()

    def calculate_characterisation(self):
        characterisation_path = self.get_file_path("Characterisation")
        if not characterisation_path:
            return
        use_settings = QtWidgets.QMessageBox.question(self.view, "Characterisation",
                                                      "Do you want to use the settings values?",
                                                      QtWidgets.QMessageBox.StandardButton.Yes
                                                      | QtWidgets.QMessageBox.StandardButton.No)
        use_settings = use_settings == QtWidgets.QMessageBox.StandardButton.Yes
        threading.Thread(target=self.calculation_model.calculate_characterisation,
                         args=[characterisation_path, use_settings,
                               self.main_controller.settings_model.file_path]).start()

    def plot_inversion(self):
        try:
            model.process_inversion_data(self.get_file_path("Inversion"))
        except KeyError:
            QtWidgets.QMessageBox.critical(self.view, "Plotting Error", "Invalid data given. Could not plot.")

    def plot_dc(self):
        try:
            model.process_dc_data(self.get_file_path("Decimation"))
        except KeyError:
            QtWidgets.QMessageBox.critical(self.view, "Plotting Error", "Invalid data given. Could not plot.")

    def plot_characterisation(self):
        try:
            model.process_characterization_data(self.get_file_path("Characterisation"))
        except KeyError:
            QtWidgets.QMessageBox.critical(self.view, "Plotting Error", "Invalid data given. Could not plot.")

    def find_devices(self):
        self.main_controller.driver_model.find_device()

    def connect_devices(self):
        for port in self.main_controller.driver_model.ports:
            try:
                port.open()
            except hardware.driver.SerialError:
                continue

    def enable_laser(self):
        self.driver_controller.hardware_model.open_laser()
        self.driver_controller.hardware_model.laser.enable_lasers()
        self.driver_controller.hardware_model.laser.process_measured_data()
