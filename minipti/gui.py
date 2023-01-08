import csv
import logging
import os
import threading
from collections import namedtuple, deque
from dataclasses import dataclass

import numpy as np
import pandas as pd
from PySide6 import QtWidgets, QtCore
from PySide6.QtCore import QAbstractTableModel, Qt
from PySide6.QtWidgets import QMainWindow, QApplication, QFileDialog, QMessageBox
from scipy import ndimage

import driver
import interferometry
import pti
import tabs


@dataclass
class _Struct:
    def __getitem__(self, key):
        return getattr(self, key.casefold().replace(" ", "_"))

    def __setitem__(self, key, value):
        setattr(self, key.casefold().replace(" ", "_"), value)


class Controller(QApplication):
    def __init__(self, argv=""):
        QApplication.__init__(self, argv)
        self.live_plot = None
        self.model = Model()
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


Tabs = namedtuple("Tab", ["home", "daq", "dc", "amplitudes", "output_phases", "interferometric_phase", "sensitivity",
                          "pti_signal"])


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
        self.tabs = Tabs(tabs.Home(self.logging_window, controller), tabs.DAQ(), tabs.DC(), tabs.Amplitudes(),
                         tabs.OutputPhases(), tabs.InterferometricPhase(), tabs.Sensitivity(), tabs.PTISignal())
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


class _BufferedData(_Struct):
    _QUEUE_SIZE = 1000

    def __init__(self):
        self.time = deque(maxlen=_BufferedData._QUEUE_SIZE)
        self.dc_values = [deque(maxlen=_BufferedData._QUEUE_SIZE) for _ in range(3)]
        self.interferometric_phase = deque(maxlen=_BufferedData._QUEUE_SIZE)
        self.sensitivity = deque(maxlen=_BufferedData._QUEUE_SIZE)
        self.pti_signal = deque(maxlen=_BufferedData._QUEUE_SIZE)
        self.pti_signal_mean = deque(maxlen=_BufferedData._QUEUE_SIZE)
        self.amplitudes = [deque(maxlen=_BufferedData._QUEUE_SIZE) for _ in range(3)]
        self.output_phases = [deque(maxlen=_BufferedData._QUEUE_SIZE) for _ in range(3)]
        self.time_stamps = deque(maxlen=_BufferedData._QUEUE_SIZE)

    def clear_buffers(self):
        self.time = deque(maxlen=_BufferedData._QUEUE_SIZE)
        self.dc_values = [deque(maxlen=_BufferedData._QUEUE_SIZE) for _ in range(3)]
        self.interferometric_phase = deque(maxlen=_BufferedData._QUEUE_SIZE)
        self.sensitivity = deque(maxlen=_BufferedData._QUEUE_SIZE)
        self.pti_signal = deque(maxlen=_BufferedData._QUEUE_SIZE)
        self.pti_signal_mean = deque(maxlen=_BufferedData._QUEUE_SIZE)
        self.amplitudes = [deque(maxlen=_BufferedData._QUEUE_SIZE) for _ in range(3)]
        self.output_phases = [deque(maxlen=_BufferedData._QUEUE_SIZE) for _ in range(3)]
        self.time_stamps = deque(maxlen=_BufferedData._QUEUE_SIZE)


class _Settings(QAbstractTableModel):
    HEADERS = ["Detector 1", "Detector 2", "Detector 3"]
    INDEX = ["Amplitude [V]", "Offset [V]", "Output Phases [deg]", "Response Phases [deg]"]
    SIGNIFICANT_VALUES = 4

    def __init__(self):
        QAbstractTableModel.__init__(self)
        self._data = pd.DataFrame(columns=_Settings.HEADERS, index=_Settings.INDEX)
        self._file_path = "configs/settings.csv"
        self._observer_callbacks = []

    def rowCount(self, parent=None):
        return self._data.shape[0]

    def columnCount(self, parent=None):
        return self._data.shape[1]

    def data(self, index, role: int = ...):
        if index.isValid():
            if role == Qt.DisplayRole or role == Qt.EditRole:
                value = self._data.values[index.row()][index.column()]
                return str(round(value, _Settings.SIGNIFICANT_VALUES))

    def flags(self, index):
        return Qt.ItemIsSelectable | Qt.ItemIsEnabled | Qt.ItemIsEditable

    def setData(self, index, value, role: int = ...):
        if index.isValid():
            if role == Qt.EditRole:
                self._data.at[_Settings.INDEX[index.row()], _Settings.HEADERS[index.column()]] = value
                return True

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if orientation == Qt.Horizontal and role == Qt.DisplayRole:
            return _Settings.HEADERS[section]
        elif orientation == Qt.Vertical and role == Qt.DisplayRole:
            return _Settings.INDEX[section]
        return super().headerData(section, orientation, role)

    @property
    def table_data(self):
        return self._data

    @table_data.setter
    def table_data(self, data):
        self._data = data
        for observer in self._observer_callbacks:
            observer(self.table_data.values.tolist())

    def update_data(self, data):
        self._data = pd.DataFrame(data, columns=_Settings.HEADERS, index=_Settings.INDEX)

    @property
    def file_path(self):
        return self._file_path

    @file_path.setter
    def file_path(self, file_path):
        if os.path.exists(file_path):
            self._file_path = file_path

    @property
    def observer_callbacks(self):
        return self._observer_callbacks

    def add_observer(self, callback):
        self._observer_callbacks.append(callback)

    def save(self):
        self._data.to_csv(self.file_path, index_label="Setting", index=True)

    def load(self):
        self.table_data = pd.read_csv(self.file_path, index_col="Setting")


class Observers(QtCore.QObject):
    def __init__(self):
        QtCore.QObject.__init__(self)

    inversion = QtCore.Signal()
    characterisation = QtCore.Signal()
    pti_settings = QtCore.Signal()
    logging_update = QtCore.Signal()


class QtHandler(logging.Handler):
    _LOGGING_HISTORY = 20

    def __init__(self, model):
        logging.Handler.__init__(self)
        self.logging_messages = deque(maxlen=QtHandler._LOGGING_HISTORY)
        self.model = model
        self.formatter = logging.Formatter('%(levelname)s %(asctime)s: %(message)s\n', datefmt='%Y-%m-%d %H:%M:%S')

    def emit(self, record: logging.LogRecord):
        self.logging_messages.append(self.format(record))
        self.model.observers.logging_update.emit()


@dataclass
class Threads:
    inversion = threading.Thread()
    characterisation = threading.Thread()
    daq = threading.Thread()


class Model:
    MEAN_INTERVAL = 60

    def __init__(self, queue_size=1000):
        self.queue_size = queue_size
        self.buffered_data = _BufferedData()
        self.pti_signal_mean_queue = deque(maxlen=60)
        self.current_time = 0
        pti_calculations = namedtuple("PTI", ("decimation", "inversion", "characterization"))
        self.interferometry = interferometry.Interferometer()
        self.pti = pti_calculations(pti.Decimation(), pti.Inversion(interferometry=self.interferometry),
                                    interferometry.Characterization(interferometry=self.interferometry))
        self.decimation_path = ""
        self.settings = _Settings()
        self.daq = driver.DAQ()
        self.pti.decimation.daq = self.daq
        self.delimiter_sniffer = csv.Sniffer()
        self.live_measurement = pti.LiveMeasurement(self.interferometry,
                                                    self.pti.inversion, self.pti.characterization, self.pti.decimation)
        self.running = threading.Event()
        self.threads = Threads()
        self._inversion_flag = False
        self._characterisation_flag = False
        self.observers = Observers()
        self.pti.characterization.observers.append(self.update_parameter_buffer)
        self.pti.characterization.observers.append(self.update_settings_parameters)
        self.pti.characterization.observers.append(self.emit_parameter_plot_signal)
        self.logging = QtHandler(self)

    def init_settings(self):
        if not os.path.exists("configs/settings.csv"):  # If no settings found, a new empty file is created.
            self.settings.save()
        else:
            try:
                settings = pd.read_csv("configs/settings.csv", index_col="Setting")
            except FileNotFoundError:
                self.settings.save()
            else:
                if list(settings.columns) != _Settings.HEADERS or list(settings.index) != _Settings.INDEX:
                    self.settings.save()  # The file is in any way broken.

    def load_settings(self):
        try:
            self.settings.load()
        except (ValueError, PermissionError) as e:
            logging.error(f"Could not load settings. Exception was \"{e}\".")
            return

    def save_settings(self):
        self.settings.save()

    def emit_parameter_plot_signal(self):
        self.observers.characterisation.emit()

    @property
    def measurement_running(self):
        return self.live_measurement.running.is_set()

    def find_delimiter(self, file_path):
        if not file_path:
            return
        with open(file_path, "r") as file:
            delimiter = str(self.delimiter_sniffer.sniff(file.readline()).delimiter)
        return delimiter

    def update_parameter_buffer(self):
        self.buffered_data.time_stamps.append(self.pti.characterization.time_stamp)
        for i in range(3):
            amplitudes = self.interferometry.amplitudes
            self.buffered_data.amplitudes[i].append(amplitudes[i])
            output_phases = np.rad2deg(self.interferometry.output_phases)
            self.buffered_data.output_phases[i].append(output_phases[i])

    def update_settings_parameters(self):
        self.settings.table_data.loc["Output Phases [deg]"] = np.rad2deg(self.interferometry.output_phases)
        self.settings.table_data.loc["Amplitude [V]"] = self.interferometry.amplitudes
        self.settings.table_data.loc["Offset [V]"] = self.interferometry.offsets

    def update_settings(self):
        self.interferometry.settings_path = self.settings.file_path
        self.pti.inversion.settings_path = self.settings.file_path
        self.interferometry.init_settings()
        self.pti.inversion.load_response_phase()

    @staticmethod
    def calculate_mean(data):
        i = 1
        current_mean = data[0]
        result = [current_mean]
        while i < Model.MEAN_INTERVAL and i < len(data):
            current_mean += data[i]
            result.append(current_mean / i)
            i += 1
        result.extend(ndimage.uniform_filter1d(data[Model.MEAN_INTERVAL:], size=Model.MEAN_INTERVAL))
        return result

    def calculate_characterisation(self, dc_file_path, use_settings=False, settings_path=""):
        self.interferometry.decimation_filepath = dc_file_path
        self.interferometry.settings_path = settings_path
        self.pti.characterization.use_settings = use_settings
        self.pti.characterization(mode="offline")

    def calculate_decimation(self, decimation_path):
        self.pti.decimation.file_path = decimation_path
        self.pti.decimation(mode="offline")

    def calculate_inversion(self, settings_path, inversion_path):
        self.interferometry.decimation_filepath = inversion_path
        self.interferometry.settings_path = settings_path
        self.pti.inversion(mode="offline")

    def live_calculation(self):
        while self.running.is_set():
            self.live_measurement.calculate_inversion()
            self.pti.inversion.settings_path = self.settings.file_path
            for i in range(3):
                self.buffered_data.dc_values[i].append(self.pti.decimation.dc_signals[i])
            self.buffered_data.interferometric_phase.append(self.interferometry.phase)
            self.buffered_data.sensitivity.append(self.pti.inversion.sensitivity)
            self.buffered_data.pti_signal.append(self.pti.inversion.pti_signal)
            self.pti_signal_mean_queue.append(self.pti.inversion.pti_signal)
            self.buffered_data.pti_signal_mean.append(np.mean(self.pti_signal_mean_queue))
            self.current_time += 1
            self.buffered_data.time.append(self.current_time)
            self.observers.inversion.emit()

    def run_measurement(self):
        self.live_measurement.running.set()
        self.threads.characterisation = threading.Thread(target=self.live_measurement.calculate_characterization,
                                                         daemon=True)
        self.threads.inversion = threading.Thread(target=self.live_calculation, daemon=True)
        self.threads.inversion.start()
        self.threads.characterisation.start()

    def clear_all(self):
        self.daq.running.clear()
        self.buffered_data.clear_buffers()
        self.live_measurement.running.clear()
        self.current_time = 0
        self.pti.inversion.init_header = True
        self.pti.decimation.init_header = True
        self.pti.characterization.init_online = True

    def connect_daq(self):
        self.daq.open()

    def start_daq(self):
        self.daq.running.set()
        self.threads.daq = threading.Thread(target=self.daq, daemon=True)
        self.threads.daq.start()

    def stop_daq(self):
        self.daq.running.clear()
        self.daq.close()

    def stop_measurement(self):
        self.live_measurement.running.clear()
        self.clear_all()
        self.running.clear()
