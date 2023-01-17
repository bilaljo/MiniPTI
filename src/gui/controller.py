import logging
import threading

from PySide6 import QtCore
from PySide6.QtWidgets import QApplication, QFileDialog, QMessageBox


import hardware

import model
import view


class MainApplication(QApplication):
    def __init__(self, argv=""):
        QApplication.__init__(self, argv)
        self.live_plot = None
        self.view = view.MainWindow(self)
        self.driver = Driver(self.view)
        self.daq_measurement = DAQMeasurement(self.view, self.driver)
        self.closed = False
        threading.excepthook = self.thread_exception
        load_settings()
        self.driver.find_devices()

    def close(self):
        self.driver.driver_model.close()
        self.view.close()

    def thread_exception(self, args):
        if args.exc_type == KeyError:
            QMessageBox.critical(self.view, "File Error", "Invalid file given or missing headers.")
        elif args.exc_type == TimeoutError:
            QMessageBox.critical(self.view, "Timeout Error", "Timeout Error")
        else:
            QMessageBox.critical(self.view, "Error", f"{args.exc_type} error occurred.")


class Driver:
    def __init__(self, main_window):
        self.driver_model = model.Driver()
        self.view = main_window

    def find_devices(self):
        if device := self.driver_model.find_device() is not None:
            logging.error(f"Could not find {device}")
            QMessageBox.warning(self.view, "Driver Error", f"Could not find {device}")

    def connect_daq(self):
        try:
            self.driver_model.open_daq()
        except hardware.driver.SerialError:
            QMessageBox.warning(self.view, "Driver Error", f"Could not connect with DAQ")
            logging.error("Could not connect with DAQ")

    def connect_laser(self):
        try:
            self.driver_model.open_laser()
        except hardware.driver.SerialError:
            QMessageBox.warning(self.view, "Driver Error", "Could not connect with Laser")
            logging.error("Could not connect with Laser")

    def connect_tec(self):
        try:
            self.driver_model.open_tec()
        except hardware.driver.SerialError:
            QMessageBox.warning(self.view, "Driver Error", "Could not connect with Tec")
            logging.error("Could not connect with Tec")


class Calculation:
    def __init__(self, parent):
        self.model = model.Calculation()
        self.parent = parent

    def calculate_decimation(self):
        decimation_file_path = get_file_path(self.parent, "Decimation")
        if not decimation_file_path:
            return
        threading.Thread(target=self.model.calculate_decimation, args=[decimation_file_path]).start()

    def calculate_inversion(self):
        inversion_path = get_file_path(self.parent, "Inversion")
        if not inversion_path:
            return
        threading.Thread(target=self.model.calculate_inversion, args=[self.model.settings_path, inversion_path]).start()

    def calculate_characterisation(self):
        characterisation_path = get_file_path(self.parent, "Characterisation")
        if not characterisation_path:
            return
        use_settings = QMessageBox.question(self.parent, "Characterisation",
                                            "Do you want to use the settings values?",
                                            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        use_settings = use_settings == QMessageBox.StandardButton.Yes
        threading.Thread(target=self.model.calculate_characterisation,
                         args=[characterisation_path, use_settings, self.model.settings_path]).start()


def get_file_path(main_window, dialog_name):
    file_path = QFileDialog.getOpenFileName(main_window, caption=dialog_name,
                                            filter="All Files (*);; CSV File (*.csv);; TXT File (*.txt")
    return file_path[0]


def plot_inversion(parent):
    try:
        model.process_inversion_data(get_file_path(parent, "Inversion"))
    except KeyError:
        QMessageBox.critical(parent, "Plotting Error", "Invalid data given. Could not plot.")


def plot_dc(parent):
    try:
        model.process_dc_data(get_file_path(parent, "Decimation"))
    except KeyError:
        QMessageBox.critical(parent, title="Plotting Error", text="Invalid data given. Could not plot.")


def plot_characterisation(parent):
    try:
        model.process_characterization_data(get_file_path(parent, "Characterisation"))
    except KeyError:
        QMessageBox.critical(parent, "Plotting Error", "Invalid data given. Could not plot.")


@QtCore.Slot()
def save_settings(settings_model: model.SettingsTable):
    settings_model.save_settings()


@QtCore.Slot()
def load_settings(parent, settings_model: model.SettingsTable):
    file_path = QFileDialog.getOpenFileName(parent, caption="Load SettingsTable",
                                            filter="All Files (*);; CSV File (*.csv);; TXT File (*.txt")
    if file_path:
        settings_model.file_path = file_path[0]  # The actual file path
        settings_model.load_settings()


class DAQMeasurement:
    def __init__(self, parent, daq):
        self.daq_measurement = model.DAQMeasurement(daq)
        self.parent = parent

    def __call__(self):
        try:
            self.daq_measurement()
        except hardware.driver.SerialError:
            logging.error("Could not connect with DAQ")
            QMessageBox.warning(self.parent, title="IO Error", text="Could not connect to DAQ")
