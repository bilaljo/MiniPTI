import logging
import threading

from PySide6 import QtWidgets

import hardware
from gui import model
from gui import view


class MainApplication(QtWidgets.QApplication):
    def __init__(self, argv=""):
        QtWidgets.QApplication.__init__(self, argv)
        self.driver_model = model.Driver()
        self.settings_model = model.SettingsTable()
        self.logging_model = model.Logging()
        self.view = view.MainWindow(self)
        threading.excepthook = self.thread_exception
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


class Home:
    def __init__(self, main_controller: MainApplication, parent):
        self.view = parent
        self.calculation_model = model.Calculation()
        self.main_controller = main_controller
        self.daq_model = model.DAQMeasurement(device=main_controller.driver_model.ports.daq)

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
        if device := self.main_controller.driver_model.find_device() is not None:
            logging.error(f"Could not find {device}")
            QtWidgets.QMessageBox.warning(self.view, "Driver Error", f"Could not find {device}")

    def connect_daq(self):
        try:
            self.main_controller.driver_model.open_daq()
        except hardware.driver.SerialError:
            QtWidgets.QMessageBox.warning(self.view, "Driver Error", f"Could not connect with DAQ")
            logging.error("Could not connect with DAQ")

    def connect_laser(self):
        try:
            self.main_controller.driver_model.open_laser()
        except hardware.driver.SerialError:
            QtWidgets.QMessageBox.warning(self.view, "Driver Error", "Could not connect with Laser")
            logging.error("Could not connect with Laser")

    def connect_tec(self):
        try:
            self.main_controller.driver_model.open_tec()
        except hardware.driver.SerialError:
            QtWidgets.QMessageBox.warning(self.view, "Driver Error", "Could not connect with Tec")
            logging.error("Could not connect with Tec")


class Laser:
    def __init__(self):
        raise NotImplementedError("Will be implemented in version 1.2.0")


class Tec:
    def __init__(self):
        raise NotImplementedError("Will be implemented in version 1.2.0")
