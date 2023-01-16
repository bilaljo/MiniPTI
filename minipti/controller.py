import csv
import logging
import os
import threading
from collections import namedtuple, deque

import pandas as pd
from PySide6 import QtWidgets, QtCore
from PySide6.QtWidgets import QMainWindow, QApplication, QFileDialog, QMessageBox


import driver

import view


Ports = namedtuple("Ports", ("daq", "laser", "tec"))


class Driver:
    def __init__(self, driver_model, main_window):
        self.daq = driver.DAQ()
        self.model = driver_model
        self.view = main_window

    def find_devices(self):
        try:
            self.model.daq.find_port()
        except driver.SerialError:
            logging.error("Could not find DAQ")
            QMessageBox.warning(self.view, "Driver Error", "Could not find DAQ")

    def connect_devices(self):
        try:
            self.model.daq.open()
        except driver.SerialError:
            QMessageBox.warning(self.view, "Driver Error", "Could not connect with DAQ")


class Calculation:
    def __init__(self):
        pass

    def calculate_decimation(self):
        decimation_file_path = self.get_file_path("Decimation")
        if not decimation_file_path:
            return
        threading.Thread(target=self.model.calculate_decimation, args=[decimation_file_path]).start()

    def calculate_inversion(self):
        inversion_path = self.get_file_path("Inversion")
        if not inversion_path:
            return
        threading.Thread(target=self.model.calculate_inversion,
                         args=[self.model.settings.file_path, inversion_path]).start()

    def calculate_characterisation(self):
        characterisation_path = self.get_file_path("Characterisation")
        if not characterisation_path:
            return
        use_settings = QMessageBox.question(self.view, "Characterisation",
                                            "Do you want to use the settings values?", QMessageBox.Yes | QMessageBox.No)
        use_settings = use_settings == QMessageBox.Yes
        threading.Thread(target=self.model.calculate_characterisation,
                         args=[characterisation_path, use_settings, self.model.settings.file_path]).start()


def get_file_path(main_window, dialog_name):
    decimation_file_path = QFileDialog.getOpenFileName(main_window, caption=dialog_name,
                                                       filter="All Files (*);; CSV File (*.csv);; TXT File (*.txt")
    return decimation_file_path[0]


class Plotting:
    def __init__(self):
        pass

    def plot_inversion(self):
        inversion_file_path = get_file_path("Inversion")
        if not inversion_file_path:
            return
        delimiter = self.model.find_delimiter(inversion_file_path)
        try:
            data = pd.read_csv(inversion_file_path, delimiter=delimiter, skiprows=[1], index_col="Time")
        except ValueError:  # Data isn't saved with any index
            data = pd.read_csv(inversion_file_path, delimiter=delimiter, skiprows=[1])
        try:
            self.view.draw_plot(data, tab="Interferometric Phase")
        except KeyError:
            QMessageBox.critical(self.view, "Plotting Error", "Invalid data given. Could not plot.")
            return
        try:
            self.view.draw_plot(data, tab="Sensitivity")
            pti_mean = Model.calculate_mean(data["PTI Signal"])
            data["PTI Signal 60 s Mean"] = pti_mean
            self.view.draw_plot(data, tab="PTI Signal")
        except KeyError:
            return  # No PTI data, only phase data

    def plot_dc(self):
        decimation_file_path = self.get_file_path("Decimation")
        if not decimation_file_path:
            return
        delimiter = self.model.find_delimiter(decimation_file_path)
        try:
            data = pd.read_csv(decimation_file_path, delimiter=delimiter, skiprows=[1], index_col="Time")
        except ValueError:  # Data isn't saved with any index
            data = pd.read_csv(decimation_file_path, delimiter=delimiter, skiprows=[1])
        try:
            self.view.draw_plot(data, tab="DC Signals")
        except KeyError:
            QMessageBox.critical(parent=self.view, title="Plotting Error", text="Invalid data given. Could not plot.")
            return

    def plot_characterisation(self):
        characterisation_file_path = self.get_file_path("Characterisation")
        if not characterisation_file_path:
            return
        delimiter = self.model.find_delimiter(characterisation_file_path)
        try:
            data = pd.read_csv(characterisation_file_path, delimiter=delimiter, skiprows=[1], index_col="Time")
        except ValueError:  # Data isn't saved with any index
            data = pd.read_csv(characterisation_file_path, delimiter=delimiter, skiprows=[1])
        try:
            self.view.draw_plot(data, tab="Output Phases")
            self.view.draw_plot(data, tab="Amplitudes")
        except KeyError:
            QMessageBox.critical(self.view, "Plotting Error", "Invalid data given. Could not plot.")
            return


class MainApplication(QApplication):
    def __init__(self, argv=""):
        QApplication.__init__(self, argv)
        self.live_plot = None
        self.model = Model()
        self.ports = Ports(self.model.daq.port, "", "")
        self.view = View(self, self.model)
        self.file_path = ""
        self.pti_measurement_thread = None
        self.phase_scan_thread = None
        self.delimiter_sniffer = csv.Sniffer()
        self.closed = False
        threading.excepthook = self.thread_exception
        if not os.path.exists("data"):
            os.mkdir("data")
        if not os.path.exists("data/raw_data"):
            os.mkdir("data/raw_data")
        logging.getLogger().addHandler(self.view.logging)
        self.model.settings.load()
        self.find_devices()

    def close(self):
        self.model.stop_daq()
        self.model.stop_measurement()
        self.running.clear()
        self.view.close()

    def thread_exception(self, args):
        if args.exc_type == KeyError:
            QMessageBox.critical(self.view, "File Error", "Invalid file given or missing headers.")
        elif args.exc_type == TimeoutError:
            QMessageBox.critical(self.view, "Timeout Error", "Timeout Error")
        else:
            QMessageBox.critical(self.view, "Error", f"{args.exc_type} error occurred.")

    @QtCore.Slot()
    def save_settings(self):
        self.model.save_settings()

    @QtCore.Slot()
    def load_settings(self):
        file_path = QFileDialog.getOpenFileName(self.view, caption="Load SettingsTable",
                                                filter="All Files (*);; CSV File (*.csv);; TXT File (*.txt")
        if file_path:
            self.model.settings.file_path = file_path[0]  # The actual file path
            self.model.load_settings()

    def init_live(self):
        self.running.set()
        try:
            self.model.connect_daq()
        except IOError:
            QMessageBox.warning(parent=self.view, title="IO Error", text="Could not connect to DAQ")
            self.running.clear()
            return False
        self.model.start_daq()
        if os.path.exists("data/Decimation.csv"):
            os.remove("data/Decimation.csv")
        if os.path.exists("data/PTI_Inversion.csv"):
            os.remove("data/PTI_Inversion.csv")
        if os.path.exists("data/raw_data.tar"):
            os.remove("data/raw_data.tar")
        return True

    @QtCore.Slot()
    def live_measurement(self):
        if self.view.button_checked("Live Measurement", "PTI"):
            self.view.toggle_button(True, "Live Measurement", "PTI")
            if self.init_live():
                self.model.running.set()
                self.model.run_measurement()
            if not self.running.is_set():
                self.view.toggle_button(False, "Live Measurement", "PTI")
                self.view.buttons["Live Measurement"]["PTI"].setChecked(False)
        else:
            self.view.toggle_button(False, "Live Measurement", "PTI")
            self.stop_live_measurement()

    def stop_live_measurement(self):
        logging.info("Stopped running.")
        self.running.clear()
        self.model.running.clear()
        self.model.stop_measurement()
        self.model.stop_daq()
