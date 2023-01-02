import csv
import logging
import os
import threading
from collections import namedtuple, deque
from dataclasses import dataclass

import numpy as np
import pandas as pd
from PySide6 import QtWidgets, QtCore
import pyqtgraph as pg
from PySide6.QtCore import QAbstractTableModel, Qt
from PySide6.QtWidgets import QMainWindow, QApplication, QFileDialog, QMessageBox
from scipy import ndimage

import driver
import pti
import interferometry


@dataclass
class _Struct:
    def __getitem__(self, key):
        return getattr(self, key.casefold().replace(" ", "_"))

    def __setitem__(self, key, value):
        setattr(self, key.casefold().replace(" ", "_"), value)


@dataclass()
class _Tabs(_Struct):
    home = None
    drivers = None
    dc_signals = None
    interferometric_phase = None
    pti_signal = None
    output_phases = None
    amplitudes = None
    sensitivity = None


class Controller(QApplication):
    def __init__(self, argv):
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
            QMessageBox.critical(parent=self.view, title="File Error", text="Invalid file given or missing headers.")
        elif args.exc_type == TimeoutError:
            QMessageBox.critical(parent=self.view, title="Timeout Error", text="Timeout Error")
        else:
            QMessageBox.critical(parent=self.view, title="Error", text=f"{args.exc_type} error occurred.")

    def save_settings(self):
        self.model.save_settings()

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
        inversion_path = self.get_file_path("Inversion")
        if not inversion_path:
            return
        delimiter = self.model.find_delimiter(inversion_path)
        data = pd.read_csv(inversion_path, delimiter=delimiter, skiprows=[1], index_col="Time")
        try:
            self.view.draw_plot(data, tab="Interferometric Phase")
        except KeyError:
            QMessageBox.critical(parent=self.view, title="Plotting Error", text="Invalid data given. Could not plot.")
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
        data = pd.read_csv(decimation_file_path, delimiter=delimiter, skiprows=[1], index_col="Time")
        try:
            self.view.draw_plot(data, tab="DC Signals")
        except KeyError:
            QMessageBox.critical(parent=self.view, title="Plotting Error", text="Invalid data given. Could not plot.")
            return

    def plot_characterisation(self):
        characterisation_path = self.get_file_path("Characterisation")
        if not characterisation_path:
            return
        delimiter = self.model.find_delimiter(characterisation_path)
        data = pd.read_csv(characterisation_path, delimiter=delimiter, skiprows=[1])
        try:
            self.view.draw_plot(data, tab="Output Phases")
            self.view.draw_plot(data, tab="Amplitudes")
        except KeyError:
            QMessageBox.critical(parent=self.view, title="Plotting Error", text="Invalid data given. Could not plot.")
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


class View(QMainWindow):
    _SETTINGS_ROWS = 4
    _SETTINGS_COLUMNS = 3

    def __init__(self, controller, model):
        super().__init__()
        self.setWindowTitle("Passepartout")
        self.controller = controller
        self.model = model
        self.plotting = _Plotting()
        self.sheet = None
        self.help_screens = _Tabs()
        self.popup = None
        self.popup_frame = None
        self.tab_bar = QtWidgets.QTabWidget(self)
        self.tabs = _Tabs()
        self.frames = dict()
        self.tab_layouts = _Tabs()
        self.logging = QtHandler(self.model)
        self.logging_window = QtWidgets.QLabel()
        self.buttons = {}
        self.setCentralWidget(self.tab_bar)
        self.__init_tabs()
        self.__init_frames()
        self.settings_table = QtWidgets.QTableView(self.frames["Configuration"])
        self.settings_table.setModel(self.model.settings)
        self.__init_settings()
        self.__init_buttons()
        self.__init_plots()
        self.__init_logging()
        header = self.settings_table.horizontalHeader()
        header.setStretchLastSection(True)
        index = self.settings_table.verticalHeader()
        index.setSectionResizeMode(QtWidgets.QHeaderView.Stretch)
        header.setSectionResizeMode(QtWidgets.QHeaderView.Stretch)
        index.setStretchLastSection(True)

        self.resize(800, 600)
        self.show()

    def closeEvent(self, close_event):
        close = QMessageBox.question(self, "QUIT", "Are you sure you want to close?", QMessageBox.No | QMessageBox.Yes)
        if close == QMessageBox.Yes:
            close_event.accept()
            self.controller.close()
        else:
            close_event.ignore()

    def create_tab(self, text):
        self.tabs[text] = QtWidgets.QTabWidget()
        self.tabs[text].setLayout(QtWidgets.QGridLayout())
        self.tab_bar.addTab(self.tabs[text], text)

    def set_frame(self, master, title, x, y):
        self.frames[title] = QtWidgets.QGroupBox()
        self.frames[title].setTitle(title)
        layout = QtWidgets.QGridLayout()
        self.frames[title].setLayout(layout)
        self.tabs[master].layout().addWidget(self.frames[title], x, y)

    def __init_tabs(self):
        self.create_tab("Home")
        self.create_tab("DC Signals")
        self.create_tab("Amplitudes")
        self.create_tab("Output Phases")
        self.create_tab("Interferometric Phase")
        self.create_tab("Sensitivity")
        self.create_tab("PTI Signal")

    def __init_frames(self):
        self.set_frame("Home", "Configuration", 0, 0)
        self.set_frame("Home", "Offline", 1, 0)
        self.set_frame("Home", "Plotting", 2, 0)
        self.set_frame("Home", "Live Measurement", 3, 0)
        self.set_frame("Home", "Log", 0, 1)

    def __init_plots(self):
        self.plotting.init_dc_signals(parent=self.tabs["DC Signals"])
        self.plotting.init_interferometric_phase(parent=self.tabs["Interferometric Phase"])
        self.plotting.init_sensitivity(parent=self.tabs["Sensitivity"])
        self.plotting.init_pti_signal(parent=self.tabs["PTI Signal"])
        self.plotting.init_amplitudes(parent=self.tabs["Amplitudes"])
        self.plotting.init_output_phases(parent=self.tabs["Output Phases"])

    def __init_buttons(self):
        self.__init_configuration_buttons()
        self.__init_offline_buttons()
        self.__init_plotting_buttons()
        self.__init_live_buttons()

    def __init_configuration_buttons(self):
        self.buttons["Configuration"] = {}

        sub_layout = QtWidgets.QWidget()
        sub_layout.setLayout(QtWidgets.QHBoxLayout())

        self.buttons["Configuration"]["Save Settings"] = QtWidgets.QPushButton("Save Settings")
        self.buttons["Configuration"]["Save Settings"].clicked.connect(self.controller.save_settings)
        sub_layout.layout().addWidget(self.buttons["Configuration"]["Save Settings"])

        self.buttons["Configuration"]["Load Settings"] = QtWidgets.QPushButton("Load Settings")
        self.buttons["Configuration"]["Load Settings"].clicked.connect(self.controller.load_settings)
        sub_layout.layout().addWidget(self.buttons["Configuration"]["Load Settings"])

        button = QtWidgets.QPushButton("Help")
        sub_layout.layout().addWidget(button)
        self.frames["Configuration"].layout().addWidget(sub_layout, 2, 0)

    def __init_offline_buttons(self):
        self.buttons["Offline"] = {}

        self.buttons["Offline"]["Decimation"] = QtWidgets.QPushButton("Decimation")
        self.buttons["Offline"]["Decimation"].clicked.connect(self.controller.calculate_decimation)
        self.frames["Offline"].layout().addWidget(self.buttons["Offline"]["Decimation"], 0, 0)

        self.buttons["Offline"]["Inversion"] = QtWidgets.QPushButton("Inversion")
        self.buttons["Offline"]["Inversion"].clicked.connect(self.controller.calculate_inversion)
        self.frames["Offline"].layout().addWidget(self.buttons["Offline"]["Inversion"], 0, 1)

        self.buttons["Offline"]["Characterization"] = QtWidgets.QPushButton("Characterization")
        self.buttons["Offline"]["Characterization"].clicked.connect(self.controller.calculate_characterisation)

        self.frames["Offline"].layout().addWidget(self.buttons["Offline"]["Characterization"], 0, 2)

    def __init_plotting_buttons(self):
        self.buttons["Plotting"] = {}

        self.buttons["Plotting"]["Decimation"] = QtWidgets.QPushButton("Decimation")
        self.buttons["Plotting"]["Decimation"].clicked.connect(self.controller.plot_dc)
        self.frames["Plotting"].layout().addWidget(self.buttons["Plotting"]["Decimation"], 0, 0)

        self.buttons["Plotting"]["Inversion"] = QtWidgets.QPushButton("Inversion")
        self.frames["Plotting"].layout().addWidget(self.buttons["Plotting"]["Inversion"], 0, 1)
        self.buttons["Plotting"]["Inversion"].clicked.connect(self.controller.plot_inversion)

        self.buttons["Plotting"]["Characterization"] = QtWidgets.QPushButton("Characterization")
        self.buttons["Plotting"]["Characterization"].clicked.connect(self.controller.plot_characterisation)
        self.frames["Plotting"].layout().addWidget(self.buttons["Plotting"]["Characterization"], 0, 2)

    def __init_live_buttons(self):
        self.buttons["Live Measurement"] = {}

        self.buttons["Live Measurement"]["DAQ"] = QtWidgets.QPushButton("DAQ")
        self.buttons["Live Measurement"]["DAQ"].setCheckable(True)
        self.buttons["Live Measurement"]["DAQ"].clicked.connect(self.controller.live_measurement)
        self.frames["Live Measurement"].layout().addWidget(self.buttons["Live Measurement"]["DAQ"], 0, 0)

        self.buttons["Live Measurement"]["Pump Laser"] = QtWidgets.QPushButton("Pump Laser")
        self.buttons["Live Measurement"]["Pump Laser"].clicked.connect(self.controller.live_measurement)
        self.frames["Live Measurement"].layout().addWidget(self.buttons["Live Measurement"]["Pump Laser"], 0, 1)

        self.buttons["Live Measurement"]["Probe Laser"] = QtWidgets.QPushButton("Probe Laser")
        self.buttons["Live Measurement"]["Probe Laser"].clicked.connect(self.controller.live_measurement)
        self.frames["Live Measurement"].layout().addWidget(self.buttons["Live Measurement"]["Probe Laser"], 0, 2)

    def __init_settings(self):
        self.settings_table.resizeColumnsToContents()
        self.settings_table.resizeRowsToContents()
        self.frames["Configuration"].layout().addWidget(self.settings_table, 0, 0)

    def __init_logging(self):
        self.frames["Log"].layout().addWidget(self.logging_window)

    def logging_update(self):
        self.logging_window.setText("".join(self.logging.logging_messages))

    def draw_plot(self, data, tab):
        match tab:
            case "DC Signals":
                for channel in range(3):
                    self.plotting.curves.dc_signals[channel].setData(data[f"DC CH{channel + 1}"])
            case "Interferometric Phase":
                self.plotting.curves.interferometric_phase.setData(data["Interferometric Phase"])
            case "Sensitivity":
                self.plotting.curves.sensitivity.setData(data["Sensitivity"])
            case "PTI Signal":
                self.plotting.curves.pti_signal.setData(data["PTI Signal"])
                self.plotting.curves.pti_signal_mean.setData(data["PTI Signal 60 s Mean"])
            case "Amplitudes":
                for channel in range(3):
                    self.plotting.curves.amplitudes[channel].setData(data[f"Amplitude CH{channel + 1}"])
            case "Output Phases":
                for channel in range(2):
                    self.plotting.curves.output_phases[channel].setData(data[f"Output Phase CH{channel + 2}"])

    @QtCore.Slot()
    def live_plot(self):
        for channel in range(3):
            self.plotting.curves.dc_signals[channel].setData(self.model.buffered_data.time,
                                                             self.model.buffered_data.dc_values[channel])
        self.plotting.curves.interferometric_phase.setData(self.model.buffered_data.time,
                                                           self.model.buffered_data.interferometric_phase)
        self.plotting.curves.sensitivity.setData(self.model.buffered_data.time,
                                                 self.model.buffered_data.sensitivity)
        self.plotting.curves.pti_signal.setData(self.model.buffered_data.time,
                                                self.model.buffered_data.pti_signal)
        self.plotting.curves.pti_signal_mean.setData(self.model.buffered_data.time,
                                                     self.model.buffered_data.pti_signal_mean)

    @QtCore.Slot()
    def live_plot_characterisation(self):
        for channel in range(3):
            self.plotting.curves.amplitudes[channel].setData(self.model.buffered_data.time_stamps,
                                                             self.model.buffered_data.amplitudes[channel])
        for channel in range(2):
            self.plotting.curves.output_phases[channel].setData(self.model.buffered_data.time_stamps,
                                                                self.model.buffered_data.output_phases[channel + 1])

    def button_checked(self, frame, button):
        return self.buttons[frame][button].isChecked()

    def toggle_button(self, state, frame, button):
        if state:
            self.buttons[frame][button].setStyleSheet("background-color : lightgreen")
        else:
            self.buttons[frame][button].setStyleSheet("background-color : light gray")


class _MatplotlibColors:
    BLUE = "#045993"
    ORANGE = "#db6000"
    GREEN = "#118011"


class _Plots(_Tabs):
    pti_signal_mean = None


class _Plotting(pg.PlotWidget):
    def __init__(self):
        pg.PlotWidget.__init__(self)
        pg.setConfigOption('leftButtonPan', False)
        pg.setConfigOptions(antialias=True)
        pg.setConfigOption('background', "white")
        pg.setConfigOption('foreground', 'k')
        self.curves = _Plots()
        self.plot_windows = _Plots()

    def init_dc_signals(self, parent: QtWidgets):
        self.curves.dc_signals = []
        self.plot_windows.dc_signals = pg.GraphicsLayoutWidget()
        plot = self.plot_windows.dc_signals.addPlot()
        plot.addLegend()
        self.curves.dc_signals = [plot.plot(pen=pg.mkPen(_MatplotlibColors.BLUE), name="DC CH1"),
                                  plot.plot(pen=pg.mkPen(_MatplotlibColors.ORANGE), name="DC CH2"),
                                  plot.plot(pen=pg.mkPen(_MatplotlibColors.GREEN), name="DC CH3")]
        plot.setLabel(axis="bottom", text="Time [s]", size="200pt")
        plot.setLabel(axis="left", text="Intensity [V]", size="200pt")
        plot.showGrid(x=True, y=True)
        parent.layout().addWidget(self.plot_windows.dc_signals)

    def init_interferometric_phase(self, parent: QtWidgets):
        self.plot_windows.interferometric_phase = pg.GraphicsLayoutWidget()
        plot = self.plot_windows.interferometric_phase.addPlot()
        self.curves.interferometric_phase = plot.plot(pen=pg.mkPen(_MatplotlibColors.BLUE))
        plot.setLabel(axis="bottom", text="Time [s]")
        plot.setLabel(axis="left", text="Interferometric Phase [rad]")
        plot.showGrid(x=True, y=True)
        parent.layout().addWidget(self.plot_windows.interferometric_phase)

    def init_sensitivity(self, parent: QtWidgets):
        self.plot_windows.sensitivity = pg.GraphicsLayoutWidget()
        plot = self.plot_windows.sensitivity.addPlot()
        self.curves.sensitivity = plot.plot(pen=pg.mkPen(_MatplotlibColors.BLUE))
        plot.setLabel(axis="bottom", text="Time [s]")
        plot.setLabel(axis="left", text="Sensitivity [1/rad]")
        plot.showGrid(x=True, y=True)
        parent.layout().addWidget(self.plot_windows.sensitivity)

    def init_pti_signal(self, parent: QtWidgets):
        self.plot_windows.pti_signal = pg.GraphicsLayoutWidget()
        plot = self.plot_windows.pti_signal.addPlot()
        plot.addLegend()
        self.curves.pti_signal = plot.scatterPlot(pen=pg.mkPen(_MatplotlibColors.BLUE), name="1 s", size=6)
        self.curves.pti_signal_mean = plot.plot(pen=pg.mkPen(_MatplotlibColors.ORANGE), name="60 s Mean")
        plot.setLabel(axis="bottom", text="Time [s]")
        plot.setLabel(axis="left", text="PTI Signal [µrad]")
        plot.showGrid(x=True, y=True)
        parent.layout().addWidget(self.plot_windows.pti_signal)

    def init_amplitudes(self, parent: QtWidgets):
        self.plot_windows.amplitudes = pg.GraphicsLayoutWidget()
        plot = self.plot_windows.amplitudes.addPlot()
        plot.addLegend()
        self.curves.amplitudes = [plot.plot(pen=pg.mkPen(_MatplotlibColors.BLUE), name="Amplitude CH1"),
                                  plot.plot(pen=pg.mkPen(_MatplotlibColors.ORANGE), name="Amplitude CH2"),
                                  plot.plot(pen=pg.mkPen(_MatplotlibColors.GREEN), name="Amplitude CH3")]
        plot.setLabel(axis="bottom", text="Time [s]")
        plot.setLabel(axis="left", text="Amplitude [V]")
        plot.showGrid(x=True, y=True)
        parent.layout().addWidget(self.plot_windows.amplitudes)

    def init_output_phases(self, parent: QtWidgets):
        self.plot_windows.output_phases = pg.GraphicsLayoutWidget()
        plot = self.plot_windows.output_phases.addPlot()
        plot.addLegend()
        self.curves.output_phases = [plot.plot(pen=pg.mkPen(_MatplotlibColors.ORANGE), name="Output Phase CH2"),
                                     plot.plot(pen=pg.mkPen(_MatplotlibColors.GREEN), name="Output Phase CH3")]
        plot.setLabel(axis="bottom", text="Time [s]")
        plot.setLabel(axis="left", text="Output Phase [deg]")
        plot.showGrid(x=True, y=True)
        parent.layout().addWidget(self.plot_windows.output_phases)


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
                return str(value)

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
                    self.settings.save()   # The file is in any way broken.

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
        self.daq.open_port()

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
