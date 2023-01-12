import csv
import logging
import os
import threading
from collections import namedtuple, deque



from PySide6 import QtWidgets, QtCore
from PySide6.QtWidgets import QMainWindow, QApplication, QFileDialog, QMessageBox


import driver

import view



Ports = namedtuple("Ports", ("daq", "laser", "tec"))


class Controller(QApplication):
    def __init__(self, argv=""):
        QApplication.__init__(self, argv)
        self.live_plot = None
        self.model = Model()
        self.ports = Ports(self.model.daq.port, "", "")
        self.view = View(self, self.model)
        self.running = False
        self.running = threading.Event()
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
        self.model.observers.inversion.connect(self.view.live_plot, QtCore.Qt.QueuedConnection)
        self.model.observers.characterisation.connect(self.view.live_plot_characterisation, QtCore.Qt.QueuedConnection)
        self.model.observers.logging_update.connect(self.view.logging_update, QtCore.Qt.QueuedConnection)
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

    @QtCore.Slot()
    def daq_firmware_version(self):
        return self.model.daq.get_firmware_version()

    @QtCore.Slot()
    def daq_hardware_version(self):
        return self.model.daq.get_hardware_version()

    @QtCore.Slot()
    def daq_id(self):
        return self.model.daq.get_hardware_id()

    @QtCore.Slot()
    def save_settings(self):
        self.model.save_settings()

    @QtCore.Slot()
    def load_settings(self):
        file_path = QFileDialog.getOpenFileName(self.view, caption="Load Settings",
                                                filter="All Files (*);; CSV File (*.csv);; TXT File (*.txt")
        if file_path:
            self.model.settings.file_path = file_path[0]  # The actual file path
            self.model.load_settings()

    def get_file_path(self, dialog_name):
        decimation_file_path = QFileDialog.getOpenFileName(self.view, caption=dialog_name,
                                                           filter="All Files (*);; CSV File (*.csv);; TXT File (*.txt")
        return decimation_file_path[0]

    def calculate_decimation(self):
        decimation_file_path = self.get_file_path("Decimation")
        if not decimation_file_path:
            return
        threading.Thread(target=self.model.calculate_decimation, args=[decimation_file_path]).start()

    def plot_inversion(self):
        inversion_file_path = self.get_file_path("Inversion")
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


Tabs = namedtuple("Tab", ["home", "daq", "laser_driver", "dc", "amplitudes", "output_phases", "interferometric_phase",
                          "sensitivity", "pti_signal"])


class View(QMainWindow):
    def __init__(self, controller, model):
        super().__init__()
        self.setWindowTitle("Passepartout")
        self.controller = controller
        self.model = model
        self.sheet = None
        self.tab_bar = QtWidgets.QTabWidget(self)
        self.logging = QtHandler(self.model)
        self.logging_window = QtWidgets.QLabel()
        self.setCentralWidget(self.tab_bar)
        self.tabs = Tabs(view.Home(self.logging_window, controller), view.DAQ(controller), view.LaserDriver(controller), view.DC(), view.Amplitudes(),
                         view.OutputPhases(), view.InterferometricPhase(), view.Sensitivity(), view.PTISignal())
        self.tabs.home.settings.setModel(self.model.settings)
        for tab in self.tabs:
            self.tab_bar.addTab(tab, tab.name)
        self.resize(900, 600)
        self.show()

    def closeEvent(self, close_event):
        close = QMessageBox.question(self, "QUIT", "Are you sure you want to close?", QMessageBox.No | QMessageBox.Yes)
        if close == QMessageBox.Yes:
            close_event.accept()
            self.model.stop_daq()
            self.controller.close()
        else:
            close_event.ignore()

    def logging_update(self):
        self.logging_window.setText("".join(self.logging.logging_messages))

    def draw_plot(self, data, tab):
        match tab:
            case "DC Signals":
                for channel in range(3):
                    self.tabs.dc.plot.curves[channel].setData(data[f"DC CH{channel + 1}"])
            case "Interferometric Phase":
                self.tabs.interferometric_phase.plot.curves.setData(data["Interferometric Phase"])
            case "Sensitivity":
                self.tabs.sensitivity.plot.curves.setData(data["Sensitivity"])
            case "PTI Signal":
                self.tabs.pti_signal.plot.curves["PTI Signal"].setData(data["PTI Signal"])
                self.tabs.pti_signal.plot.curves["PTI Signal Mean"].setData(data["PTI Signal 60 s Mean"])
            case "Amplitudes":
                for channel in range(3):
                    self.tabs.amplitudes.plot.curves[channel].setData(data[f"Amplitude CH{channel + 1}"])
            case "Output Phases":
                for channel in range(2):
                    self.tabs.output_phases.plot.curves[channel].setData(data[f"Output Phase CH{channel + 2}"])

    @QtCore.Slot()
    def live_plot(self):
        for channel in range(3):
            self.tabs.dc.plot.curves[channel].setData(self.model.buffered_data.time,
                                                      self.model.buffered_data.dc_values[channel])
        self.tabs.interferometric_phase.plot.curves.setData(self.model.buffered_data.time,
                                                            self.model.buffered_data.interferometric_phase)
        self.tabs.sensitivity.plot.curves.setData(self.model.buffered_data.time,
                                                  self.model.buffered_data.sensitivity)
        self.tabs.pti_signal.plot.curves["PTI Signal"].setData(self.model.buffered_data.time,
                                                          self.model.buffered_data.pti_signal)
        self.tabs.pti_signal.plot.curves["PTI Signal Mean"].setData(self.model.buffered_data.time,
                                                               self.model.buffered_data.pti_signal_mean)

    @QtCore.Slot()
    def live_plot_characterisation(self):
        for channel in range(3):
            self.tabs.amplitudes.curves[channel].setData(self.model.buffered_data.time_stamps,
                                                         self.model.buffered_data.amplitudes[channel])
        for channel in range(2):
            self.tabs.output_phases.curves[channel].setData(self.model.buffered_data.time_stamps,
                                                            self.model.buffered_data.output_phases[channel + 1])

    def button_checked(self, frame, button):
        return self.buttons[frame][button].isChecked()

    def toggle_button(self, state, frame, button):
        if state:
            self.buttons[frame][button].setStyleSheet("background-color : lightgreen")
        else:
            self.buttons[frame][button].setStyleSheet("background-color : light gray")
