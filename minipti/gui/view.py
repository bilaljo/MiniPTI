import abc
import collections
import platform
from dataclasses import dataclass
from typing import NamedTuple

import pandas as pd
import pyqtgraph as pg
from PyQt5 import QtWidgets, QtCore, QtGui
from PyQt5.QtCore import Qt

from .. import hardware
from . import controller
from . import model


class MainWindow(QtWidgets.QMainWindow):
    HORIZONTAL_SIZE = 1200
    VERTICAL_SIZE = 1000

    def __init__(self, main_controller):
        QtWidgets.QMainWindow.__init__(self)
        self.setWindowTitle("MiniPTI")
        self.setWindowIcon(QtGui.QIcon("images/icon.png"))
        self.main_controller = main_controller
        self.tab_bar = QtWidgets.QTabWidget(self)
        self.setCentralWidget(self.tab_bar)
        self.current_pump_laser = PumpLaserCurrent()
        self.current_probe_laser = ProbeLaserCurrent()
        self.temperature_probe_laser = TecTemperature(channel=model.Tec.PROBE_LASER)
        self.temperature_pump_laser = TecTemperature(channel=model.Tec.PUMP_LASER)
        self.dc = DC()
        self.amplitudes = Amplitudes()
        self.output_phases = OutputPhases()
        self.interferometric_phase = InterferometricPhase()
        self.sensitivity = Sensitivity()
        self.symmetry = Symmetry()
        self.pti_signal = PTISignal()
        self.logging_window = QtWidgets.QLabel()
        settings = Settings(self.main_controller)
        settings.controller.fire_mother_board_configuration()
        utilities = Utilities(settings.controller)
        self.tabs = Tab(Home(self.main_controller, settings.controller),
                        settings,
                        utilities,
                        pump_laser=self._init_pump_laser_tab(),
                        probe_laser=self._init_probe_laser_tab(),
                        dc=QtWidgets.QTabWidget(),
                        amplitudes=QtWidgets.QTabWidget(),
                        output_phases=QtWidgets.QTabWidget(),
                        sensitivity=QtWidgets.QTabWidget(),
                        symmetry=QtWidgets.QTabWidget(),
                        interferometric_phase=QtWidgets.QTabWidget(),
                        pti_signal=QtWidgets.QTabWidget())
        self.log = QtWidgets.QDockWidget("Log", self)
        self.scroll = QtWidgets.QScrollArea(widgetResizable=True)
        self.battery = QtWidgets.QDockWidget("Battery", self)
        self.charge_level = QtWidgets.QLabel("NaN % left")
        self.minutes_left = QtWidgets.QLabel("NaN Minutes left")
        self._init_tabs()
        self._init_dock_widgets()
        self.setCorner(Qt.BottomRightCorner, Qt.RightDockWidgetArea)
        self.resize(MainWindow.HORIZONTAL_SIZE, MainWindow.VERTICAL_SIZE)
        self.show()

    def logging_update(self, log_queue: collections.deque) -> None:
        self.logging_window.setText("".join(log_queue))

    @QtCore.pyqtSlot(model.Battery)
    def update_battery_state(self, battery: model.Battery) -> None:
        self.minutes_left.setText(f"Minutes left: {battery.minutes_left}")
        self.charge_level.setText(f"{battery.percentage} % left")

    def _init_dock_widgets(self) -> None:
        self.addDockWidget(Qt.BottomDockWidgetArea, self.log)
        self.addDockWidget(Qt.BottomDockWidgetArea, self.battery)
        model.signals.battery_state.connect(self.update_battery_state)
        model.signals.logging_update.connect(self.logging_update)
        self.scroll.setWidgetResizable(True)
        self.log.setWidget(self.scroll)
        sub_layout = QtWidgets.QWidget()
        sub_layout.setMaximumWidth(150)
        sub_layout.setLayout(QtWidgets.QVBoxLayout())
        sub_layout.layout().addWidget(self.charge_level)
        sub_layout.layout().addWidget(self.minutes_left)
        self.battery.setWidget(sub_layout)
        self.scroll.setWidget(self.logging_window)

    def _init_pump_laser_tab(self) -> QtWidgets.QTabWidget:
        tab = QtWidgets.QTabWidget()
        sub_layout = QtWidgets.QSplitter()
        pump_laser = PumpLaser()
        pump_laser_tab = QtWidgets.QTabWidget()
        pump_laser_tab.setLayout(QtWidgets.QHBoxLayout())
        sub_layout.insertWidget(0, pump_laser)
        sub_layout.insertWidget(1, self.current_pump_laser.window)
        pump_laser_tab.layout().addWidget(sub_layout)
        tab.addTab(pump_laser_tab, "Laser Driver")
        sub_layout = QtWidgets.QSplitter()
        tec_tab = QtWidgets.QTabWidget()
        tec_tab.setLayout(QtWidgets.QHBoxLayout())
        sub_layout.insertWidget(0, Tec(model.Tec.PUMP_LASER))
        sub_layout.insertWidget(1, self.temperature_pump_laser.window)
        tec_tab.layout().addWidget(sub_layout)
        tab.addTab(tec_tab, "Tec Driver")
        return tab

    def _init_probe_laser_tab(self) -> QtWidgets.QTabWidget:
        tab = QtWidgets.QTabWidget()
        sub_layout = QtWidgets.QSplitter()
        probe_laser = ProbeLaser()
        probe_laser_tab = QtWidgets.QTabWidget()
        probe_laser_tab.setLayout(QtWidgets.QHBoxLayout())
        sub_layout.insertWidget(0, probe_laser)
        sub_layout.insertWidget(1, self.current_probe_laser.window)
        probe_laser_tab.layout().addWidget(sub_layout)
        tab.addTab(probe_laser_tab, "Laser Driver")
        sub_layout = QtWidgets.QSplitter()
        tec_tab = QtWidgets.QTabWidget()
        tec_tab.setLayout(QtWidgets.QHBoxLayout())
        sub_layout.insertWidget(0, Tec(model.Tec.PROBE_LASER))
        sub_layout.insertWidget(1, self.temperature_probe_laser.window)
        tec_tab.layout().addWidget(sub_layout)
        tab.addTab(tec_tab, "Tec Driver")
        return tab

    def _init_tabs(self):
        self.tab_bar.addTab(self.tabs.home, "Home")
        self.tab_bar.addTab(self.tabs.settings, "Settings")
        self.tab_bar.addTab(self.tabs.utilities, "Utilities")
        self.tab_bar.addTab(self.tabs.pump_laser, "Pump Laser")
        self.tab_bar.addTab(self.tabs.probe_laser, "Probe Laser")
        # DC Plot
        self.tabs.dc.setLayout(QtWidgets.QHBoxLayout())
        self.tabs.dc.layout().addWidget(self.dc.window)
        self.tab_bar.addTab(self.tabs.dc, "DC Signals")
        # Amplitudes Plot
        self.tabs.amplitudes.setLayout(QtWidgets.QHBoxLayout())
        self.tabs.amplitudes.layout().addWidget(self.amplitudes.window)
        self.tab_bar.addTab(self.tabs.amplitudes, "Amplitudes")
        # Output Phases Plot
        self.tabs.output_phases.setLayout(QtWidgets.QHBoxLayout())
        self.tabs.output_phases.layout().addWidget(self.output_phases.window)
        self.tab_bar.addTab(self.tabs.output_phases, "Output Phases")
        # Interferometric Phase Plot
        self.tabs.interferometric_phase.setLayout(QtWidgets.QHBoxLayout())
        self.tabs.interferometric_phase.layout().addWidget(self.interferometric_phase.window)
        self.tab_bar.addTab(self.tabs.interferometric_phase, "Interferometric Phase")
        # Sensitivity Plot
        self.tabs.sensitivity.setLayout(QtWidgets.QHBoxLayout())
        self.tabs.sensitivity.layout().addWidget(self.sensitivity.window)
        self.tab_bar.addTab(self.tabs.sensitivity, "Sensitivity")
        # Symmetry Plot
        self.tabs.symmetry.setLayout(QtWidgets.QHBoxLayout())
        self.tabs.symmetry.layout().addWidget(self.symmetry.window)
        self.tab_bar.addTab(self.tabs.symmetry, "Symmetry")
        # PTI Signal Plot
        self.tabs.pti_signal.setLayout(QtWidgets.QHBoxLayout())
        self.tabs.pti_signal.layout().addWidget(self.pti_signal.window)
        self.tab_bar.addTab(self.tabs.pti_signal, "PTI Signal")

    def closeEvent(self, close_event):
        close = QtWidgets.QMessageBox.question(self, "QUIT", "Are you sure you want to close?",
                                               QtWidgets.QMessageBox.StandardButton.Yes |
                                               QtWidgets.QMessageBox.StandardButton.No)
        if close == QtWidgets.QMessageBox.StandardButton.Yes:
            close_event.accept()
            self.main_controller.close()
        else:
            close_event.ignore()


class Tab(NamedTuple):
    home: "Home"
    settings: "Settings"
    utilities: "Utilities"
    pump_laser: QtWidgets.QTabWidget
    probe_laser: QtWidgets.QTabWidget
    dc: QtWidgets.QTabWidget
    amplitudes: QtWidgets.QTabWidget
    output_phases: QtWidgets.QTabWidget
    interferometric_phase: QtWidgets.QTabWidget
    sensitivity: QtWidgets.QTabWidget
    symmetry: QtWidgets.QTabWidget
    pti_signal: QtWidgets.QTabWidget


@dataclass
class Frames:
    def set_frame(self, master: QtWidgets.QWidget, title, x_position=-1, y_position=-1, x_span=1, y_span=1,
                  layout=QtWidgets.QGridLayout()):
        self.__getattribute__(title).setTitle(title)
        self.__getattribute__(title).setTitle(layout)
        try:
            master.layout().addWidget(self.__getattribute__(title), x_position, y_position, x_span, y_span)
        except TypeError:
            master.layout().addWidget(self.__getattribute__(title))


class _CreateButton:
    def __init__(self):
        self.buttons = {}  # type: dict[str, QtWidgets.QPushButton]

    def create_button(self, master, title, slot, master_title="") -> None:
        if master_title:
            master_title += " "
        self.buttons[master_title + title] = QtWidgets.QPushButton(master, text=title)
        self.buttons[master_title + title].clicked.connect(slot)
        master.layout().addWidget(self.buttons[master_title + title])

    def _init_buttons(self) -> None:
        ...


class Table(QtWidgets.QTableView):
    def __init__(self, parent, table_model: model.Table):
        QtWidgets.QTableView.__init__(self, parent=parent)
        header = self.horizontalHeader()
        header.setStretchLastSection(True)
        index = self.verticalHeader()
        index.setSectionResizeMode(QtWidgets.QHeaderView.Stretch)
        header.setSectionResizeMode(QtWidgets.QHeaderView.Stretch)
        index.setStretchLastSection(True)
        self.resizeColumnsToContents()
        self.resizeRowsToContents()
        self.setModel(table_model)


def toggle_button(checked, button: QtWidgets.QPushButton) -> None:
    if checked:
        button.setStyleSheet("background-color : lightgreen")
    else:
        button.setStyleSheet("background-color : light gray")


class Home(QtWidgets.QTabWidget, _CreateButton):
    def __init__(self, main_app: QtWidgets.QApplication, settings_controller):
        QtWidgets.QTabWidget.__init__(self)
        _CreateButton.__init__(self)
        self.setLayout(QtWidgets.QGridLayout())
        self.controller = controller.Home(self, main_app, settings_controller)
        self.dc_signals = DC()
        self.pti_signal = PTISignal()
        self._init_buttons()
        self._init_signals()
        sublayout = QtWidgets.QWidget()
        sublayout.setLayout(QtWidgets.QHBoxLayout())
        sublayout.layout().addWidget(self.dc_signals.window)
        sublayout.layout().addWidget(self.pti_signal.window)
        self.layout().addWidget(sublayout, 0, 0)
        model.signals.bypass.connect(self.update_clean_air)

    def _init_buttons(self) -> None:
        sub_layout = QtWidgets.QWidget()
        sub_layout.setLayout(QtWidgets.QHBoxLayout())
        self.create_button(master=sub_layout, title="Run Measurement", slot=self.controller.enable_motherboard)
        if platform.system() == "Windows":
            self.create_button(master=sub_layout, title="Disable all Devices", slot=self.controller.shutdown_by_button)
        else:
            self.create_button(master=sub_layout, title="Shutdown and Close", slot=self.controller.shutdown_by_button)
        self.layout().addWidget(sub_layout, 1, 0)
        # self.create_button(master=sub_layout, title="Clean Air", slot=self.controller.update_bypass)

    @QtCore.pyqtSlot(bool)
    def update_run_measurement(self, state: bool) -> None:
        toggle_button(state, self.buttons["Run Measurement"])

    @QtCore.pyqtSlot(bool)
    def update_clean_air(self, state: bool) -> None:
        toggle_button(state, self.buttons["Clean Air"])

    def _init_signals(self) -> None:
        model.signals.daq_running.connect(self.update_run_measurement)


@dataclass
class SettingsFrames(Frames):
    configuration = QtWidgets.QGroupBox()
    file_path = QtWidgets.QGroupBox()
    drivers = QtWidgets.QGroupBox()
    save_data = QtWidgets.QGroupBox()
    measurement = QtWidgets.QGroupBox()
    valve = QtWidgets.QGroupBox()


class Settings(QtWidgets.QTabWidget, _CreateButton):
    def __init__(self, main_app):
        QtWidgets.QTabWidget.__init__(self)
        _CreateButton.__init__(self)
        self.frames = SettingsFrames()
        self.setLayout(QtWidgets.QGridLayout())
        self.controller = controller.Settings(main_app, self)
        self.destination_folder = QtWidgets.QLabel(self.controller.destination_folder.folder)
        self._init_frames()
        self.settings = Table(parent=self.frames.configuration,
                              table_model=self.controller.settings_table_model)
        self.destination_folder = QtWidgets.QLabel(self.controller.destination_folder.folder)
        self.save_raw_data = QtWidgets.QCheckBox("Save Raw Data")
        self.automatic_valve_switch = QtWidgets.QCheckBox("Automatic Valve Switch")
        self.duty_cyle_valve = QtWidgets.QLabel("%")
        self.period_valve = QtWidgets.QLabel("s")
        self.duty_cycle_field = QtWidgets.QLineEdit()
        self.period_field = QtWidgets.QLineEdit()
        self.average_period = QtWidgets.QComboBox()
        self.samples = QtWidgets.QLabel("8000 Samples")
        self._init_frames()
        self._init_average_period_box()
        self.frames.configuration.layout().addWidget(self.settings)
        self._init_buttons()
        self._init_valves()
        model.signals.destination_folder_changed.connect(self.update_destination_folder)
        model.signals.valve_change.connect(self.update_valve)

    def update_samples(self) -> None:
        text = self.average_period.currentText()
        if text[-2:] == "ms":
            self.samples.setText(f"{int((float(text[:-3]) / 1000) * 8000)} Samples")
        else:
            self.samples.setText(f"{int(float(text[:-2]) * 8000)} Samples")

    @QtCore.pyqtSlot(hardware.motherboard.Valve)
    def update_valve(self, valve: hardware.motherboard.Valve) -> None:
        self.duty_cycle_field.setText(str(valve.duty_cycle))
        self.period_field.setText(str(valve.period))
        self.automatic_valve_switch.setChecked(valve.automatic_switch)

    @QtCore.pyqtSlot(str)
    def update_destination_folder(self, destionation_folder: str) -> None:
        self.destination_folder.setText(destionation_folder)

    def _init_average_period_box(self) -> None:
        for i in range(1, 80):
            self.average_period.addItem(f"{i * 100 / 8000 * 1000} ms")
        for i in range(80, 320 + 1):
            self.average_period.addItem(f"{i * 100 / 8000 } s")
        self.average_period.setCurrentIndex(80 - 1)
        sublayout = QtWidgets.QWidget()
        sublayout.setLayout(QtWidgets.QVBoxLayout())
        sublayout.layout().addWidget(QtWidgets.QLabel("Averaging Time"))
        sublayout.layout().addWidget(self.average_period)
        sublayout.layout().addWidget(self.samples)
        self.frames.measurement.layout().addWidget(sublayout)
        self.average_period.currentIndexChanged.connect(self.update_samples)

    def _init_frames(self) -> None:
        self.frames.set_frame(master=self, title="File Path", x_position=2, y_position=1)
        sublayout = QtWidgets.QWidget()
        sublayout.setLayout(QtWidgets.QHBoxLayout())
        self.frames.set_frame(master=sublayout, title="Drivers")
        self.layout().addWidget(sublayout, 4, 0)
        self.frames.set_frame(master=self, title="Save Data", x_position=0, y_position=1)
        self.frames.set_frame(master=self, title="Measurement", x_position=1, y_position=1)
        self.frames.set_frame(master=self, title="Configuration", x_position=0, y_position=0, x_span=4)
        self.frames.set_frame(master=self, title="Valve", x_position=3, y_position=1, x_span=2)

    def _init_buttons(self) -> None:
        sub_layout = QtWidgets.QWidget()
        self.frames.configuration.layout().addWidget(sub_layout)
        sub_layout.setLayout(QtWidgets.QHBoxLayout())

        sub_layout = QtWidgets.QWidget(parent=self.frames.drivers)
        sub_layout.setLayout(QtWidgets.QHBoxLayout())
        self.frames.drivers.layout().addWidget(sub_layout)
        self.create_button(master=sub_layout, title="Connect Devices", slot=self.controller.init_devices)

        sub_layout = QtWidgets.QWidget(parent=self.frames.configuration)
        sub_layout.setLayout(QtWidgets.QHBoxLayout())
        self.frames.configuration.layout().addWidget(sub_layout)
        self.create_button(master=sub_layout, title="Save Settings", slot=self.controller.save_settings)
        self.create_button(master=sub_layout, title="Save Settings As", slot=self.controller.save_settings_as)
        self.create_button(master=sub_layout, title="Load Settings", slot=self.controller.load_settings)
        self.frames.measurement.layout().addWidget(self.save_raw_data)

        # Valve Control
        sub_layout = QtWidgets.QWidget(parent=self.frames.valve)
        sub_layout.setLayout(QtWidgets.QGridLayout())
        sub_layout.layout().addWidget(self.automatic_valve_switch, 0, 0)
        sub_layout.layout().addWidget(QtWidgets.QLabel("Valve Period"), 1, 0)
        sub_layout.layout().addWidget(self.period_field, 1, 1)
        sub_layout.layout().addWidget(QtWidgets.QLabel("s"), 1, 2)
        sub_layout.layout().addWidget(QtWidgets.QLabel("Valve Duty Cycle"), 2, 0)
        sub_layout.layout().addWidget(self.duty_cycle_field, 2, 1)
        sub_layout.layout().addWidget(QtWidgets.QLabel("%"), 2, 2)
        self.frames.valve.layout().addWidget(sub_layout)
        sub_layout = QtWidgets.QWidget(parent=self.frames.valve)
        sub_layout.setLayout(QtWidgets.QHBoxLayout())
        self.create_button(master=sub_layout, title="Save Settings",
                           slot=self.controller.save_motherboard_configuration)
        self.create_button(master=sub_layout, title="Load Settings",
                           slot=self.controller.load_motherboard_configuration)
        self.frames.valve.layout().addWidget(sub_layout)

        sub_layout = QtWidgets.QWidget(parent=self.frames.file_path)
        sub_layout.setLayout(QtWidgets.QVBoxLayout())
        self.frames.file_path.layout().addWidget(sub_layout)
        self.create_button(master=sub_layout, title="Destination Folder", slot=self.controller.set_destination_folder)
        sub_layout.layout().addWidget(self.destination_folder)

        self.frames.save_data.layout().addWidget(QtWidgets.QCheckBox())

        self.frames.save_data.layout().addWidget(QtWidgets.QCheckBox())
        self.frames.save_data.layout().addWidget(QtWidgets.QCheckBox())

    def _init_valves(self) -> None:
        self.automatic_valve_switch.stateChanged.connect(self._automatic_switch_changed)
        self.period_field.editingFinished.connect(self._period_changed)
        self.duty_cycle_field.editingFinished.connect(self._duty_cycle_changed)

    def _automatic_switch_changed(self) -> None:
        self.controller.update_automatic_valve_switch(self.automatic_valve_switch.isChecked())

    def _period_changed(self) -> None:
        self.controller.update_valve_period(self.period_field.text())

    def _duty_cycle_changed(self) -> None:
        self.controller.update_valve_duty_cycle(self.duty_cycle_field.text())


@dataclass
class UtilitiesFrames(Frames):
    decimation = QtWidgets.QGroupBox()
    pti_inversion = QtWidgets.QGroupBox()
    interferometer_characterisation = QtWidgets.QGroupBox()


class Utilities(QtWidgets.QTabWidget, _CreateButton):
    def __init__(self, settings_controller):
        QtWidgets.QTabWidget.__init__(self)
        _CreateButton.__init__(self)
        self.frames = UtilitiesFrames()
        self.setLayout(QtWidgets.QGridLayout())
        self.controller = controller.Utilities(self, settings_controller)
        self._init_frames()
        self._init_buttons()

    def _init_frames(self) -> None:
        self.frames.set_frame(master=self, title="Decimation", x_position=0, y_position=0)
        self.frames.set_frame(master=self, title="PTI Inversion", x_position=1, y_position=0)
        self.frames.set_frame(master=self, title="Interferometer Characterisation", x_position=2, y_position=0)

    def _init_buttons(self) -> None:
        # Decimation
        sub_layout = QtWidgets.QWidget()
        sub_layout.setLayout(QtWidgets.QVBoxLayout())
        self.frames["Decimation"].layout().addWidget(sub_layout)
        self.create_button(master=sub_layout, title="Calculate", slot=self.controller.calculate_decimation)
        self.create_button(master=sub_layout, title="Plot DC Signals", slot=self.controller.plot_dc)
        # PTI Inversion
        sub_layout = QtWidgets.QWidget()
        sub_layout.setLayout(QtWidgets.QVBoxLayout())
        self.frames["PTI Inversion"].layout().addWidget(sub_layout)
        self.create_button(master=sub_layout, title="Calculate", slot=self.controller.calculate_pti_inversion)
        self.create_button(master=sub_layout, title="Plot", slot=self.controller.plot_inversion)
        # Characterisation
        sub_layout = QtWidgets.QWidget()
        sub_layout.setLayout(QtWidgets.QVBoxLayout())
        self.frames["Interferometer Characterisation"].layout().addWidget(sub_layout)
        self.create_button(master=sub_layout, title="Calculate", slot=self.controller.calculate_characterisation)
        self.create_button(master=sub_layout, title="Plot", slot=self.controller.plot_characterisation)


class _MatplotlibColors:
    BLUE = "#045993"
    ORANGE = "#db6000"
    GREEN = "#118011"


class _Plotting(pg.PlotWidget):
    def __init__(self):
        pg.PlotWidget.__init__(self)
        pg.setConfigOption('leftButtonPan', False)
        pg.setConfigOptions(antialias=True)
        pg.setConfigOption('background', "white")
        pg.setConfigOption('foreground', 'k')
        self.window = pg.GraphicsLayoutWidget()
        self.plot = self.window.addPlot()
        self.curves = self.plot.plot(pen=pg.mkPen(_MatplotlibColors.BLUE))
        self.plot.showGrid(x=True, y=True)
        self.plot.addLegend()

    @QtCore.pyqtSlot()
    def clear(self) -> None:
        self.window.clear()

    @abc.abstractmethod
    def update_data_live(self, data: model.Buffer) -> None:
        ...


class _DAQPlots(_Plotting):
    def __init__(self):
        _Plotting.__init__(self)
        model.signals.clear_daq.connect(self.clear)

    @abc.abstractmethod
    def update_data(self, data: pd.DataFrame) -> None:
        ...


class DC(_DAQPlots):
    def __init__(self):
        _DAQPlots.__init__(self)
        self.curves = [self.plot.plot(pen=pg.mkPen(_MatplotlibColors.BLUE), name="DC CH1"),
                       self.plot.plot(pen=pg.mkPen(_MatplotlibColors.ORANGE), name="DC CH2"),
                       self.plot.plot(pen=pg.mkPen(_MatplotlibColors.GREEN), name="DC CH3")]
        self.plot.setLabel(axis="bottom", text="Time [s]")
        self.plot.setLabel(axis="left", text="Intensity [V]")
        model.signals.decimation.connect(self.update_data)
        model.signals.decimation_live.connect(self.update_data_live)

    def update_data(self, data: pd.DataFrame) -> None:
        for channel in range(3):
            try:
                self.curves[channel].setData(data[f"DC CH{channel + 1}"].to_numpy())
            except KeyError:
                self.curves[channel].setData(data[f"PD{channel + 1}"].to_numpy())

    def update_data_live(self, data: model.PTIBuffer) -> None:
        for channel in range(3):
            self.curves[channel].setData(data.time, data.dc_values[channel])


class Amplitudes(_DAQPlots):
    def __init__(self):
        _DAQPlots.__init__(self)
        self.curves = [self.plot.scatterPlot(pen=pg.mkPen(_MatplotlibColors.BLUE),
                                             brush=pg.mkBrush(_MatplotlibColors.BLUE),
                                             name="Amplitude CH1"),
                       self.plot.scatterPlot(pen=pg.mkPen(_MatplotlibColors.ORANGE),
                                             brush=pg.mkBrush(_MatplotlibColors.ORANGE),
                                             name="Amplitude CH2"),
                       self.plot.scatterPlot(pen=pg.mkPen(_MatplotlibColors.GREEN),
                                             brush=pg.mkBrush(_MatplotlibColors.GREEN),
                                             name="Amplitude CH3")]
        self.plot.setLabel(axis="bottom", text="Time [s]")
        self.plot.setLabel(axis="left", text="Amplitude [V]")
        model.signals.characterization.connect(self.update_data)
        model.signals.characterization_live.connect(self.update_data_live)

    def update_data(self, data: pd.DataFrame) -> None:
        for channel in range(3):
            self.curves[channel].setData(data.index, data[f"Amplitude CH{channel + 1}"].to_numpy())

    def update_data_live(self, data: model.CharacterisationBuffer) -> None:
        for channel in range(3):
            self.curves[channel].setData(data.time, data.amplitudes[channel])


class OutputPhases(_DAQPlots):
    def __init__(self):
        _DAQPlots.__init__(self)
        self.curves = [self.plot.scatterPlot(pen=pg.mkPen(_MatplotlibColors.ORANGE), name="Output Phase CH2",
                                             brush=pg.mkBrush(_MatplotlibColors.ORANGE)),
                       self.plot.scatterPlot(pen=pg.mkPen(_MatplotlibColors.GREEN), name="Output Phase CH3",
                                             brush=pg.mkBrush(_MatplotlibColors.GREEN))]
        self.plot.setLabel(axis="bottom", text="Time [s]")
        self.plot.setLabel(axis="left", text="Output Phase [deg]")
        model.signals.characterization.connect(self.update_data)
        model.signals.characterization_live.connect(self.update_data_live)

    def update_data(self, data: pd.DataFrame) -> None:
        for channel in range(2):
            self.curves[channel].setData(data.index, data[f"Output Phase CH{channel + 2}"].to_numpy())

    def update_data_live(self, data: model.CharacterisationBuffer) -> None:
        for channel in range(2):
            self.curves[channel].setData(data.time, data.output_phases[channel])


class InterferometricPhase(_DAQPlots):
    def __init__(self):
        _DAQPlots.__init__(self)
        self.curves = self.plot.plot(pen=pg.mkPen(_MatplotlibColors.BLUE))
        self.plot.setLabel(axis="bottom", text="Time [s]")
        self.plot.setLabel(axis="left", text="Interferometric Phase [rad]")
        model.signals.inversion.connect(self.update_data)
        model.signals.inversion_live.connect(self.update_data_live)

    def update_data(self, data: pd.DataFrame) -> None:
        self.curves.setData(data["Interferometric Phase"].to_numpy())

    def update_data_live(self, data: model.PTIBuffer) -> None:
        self.curves.setData(data.time, data.interferometric_phase)


class Sensitivity(_DAQPlots):
    def __init__(self):
        _DAQPlots.__init__(self)
        self.curves = [self.plot.plot(pen=pg.mkPen(_MatplotlibColors.BLUE), name="CH1"),
                       self.plot.plot(pen=pg.mkPen(_MatplotlibColors.ORANGE), name="CH2"),
                       self.plot.plot(pen=pg.mkPen(_MatplotlibColors.GREEN), name="CH3")]
        self.plot.setLabel(axis="bottom", text="Time [s]")
        self.plot.setLabel(axis="left", text="Sensitivity [V/rad]")
        model.signals.inversion.connect(self.update_data)
        model.signals.inversion_live.connect(self.update_data_live)

    def update_data(self, data: pd.DataFrame) -> None:
        for channel in range(3):
            self.curves[channel].setData(data[f"Sensitivity CH{channel + 1}"].to_numpy())

    def update_data_live(self, data: model.PTIBuffer) -> None:
        for channel in range(3):
            self.curves[channel].setData(data.time, data.sensitivity[channel])


class Symmetry(_DAQPlots):
    def __init__(self):
        _DAQPlots.__init__(self)
        self.curves = [self.plot.scatterPlot(pen=pg.mkPen(_MatplotlibColors.BLUE), name="Absolute Symmetry",
                                             brush=pg.mkBrush(_MatplotlibColors.BLUE)),
                       self.plot.scatterPlot(pen=pg.mkPen(_MatplotlibColors.ORANGE), name="Relative Symmetry",
                                             brush=pg.mkBrush(_MatplotlibColors.ORANGE))]
        self.plot.setLabel(axis="bottom", text="Time [s]")
        self.plot.setLabel(axis="left", text="Symmetry [%]")
        model.signals.characterization.connect(self.update_data)
        model.signals.characterization_live.connect(self.update_data_live)

    def update_data(self, data: pd.DataFrame) -> None:
        self.curves[0].setData(data.index, data["Symmetry"].to_numpy())
        self.curves[1].setData(data.index, data["Relative Symmetry"].to_numpy())

    def update_data_live(self, data: model.CharacterisationBuffer) -> None:
        self.curves[0].setData(data.time, data.symmetry)
        self.curves[1].setData(data.time, data.relative_symmetry)


class PTISignal(_DAQPlots):
    def __init__(self):
        _DAQPlots.__init__(self)
        self.curves = {"PTI Signal": self.plot.scatterPlot(pen=pg.mkPen(_MatplotlibColors.BLUE), name="1 s", size=6),
                       "PTI Signal Mean": self.plot.plot(pen=pg.mkPen(_MatplotlibColors.ORANGE), name="60 s Mean")}
        self.plot.setLabel(axis="bottom", text="Time [s]")
        self.plot.setLabel(axis="left", text="PTI Signal [µrad]")
        model.signals.inversion.connect(self.update_data)
        model.signals.inversion_live.connect(self.update_data_live)

    def update_data(self, data: pd.DataFrame) -> None:
        try:
            self.curves["PTI Signal"].setData(data["PTI Signal"].to_numpy())
            self.curves["PTI Signal Mean"].setData(data["PTI Signal 60 s Mean"].to_numpy())
        except KeyError:
            pass

    def update_data_live(self, data: model.PTIBuffer) -> None:
        self.curves["PTI Signal"].setData(data.time, data.pti_signal)
        self.curves["PTI Signal Mean"].setData(data.time, data.pti_signal_mean)


class PumpLaserCurrent(_Plotting):
    def __init__(self):
        _Plotting.__init__(self)
        self.curves = self.plot.plot(pen=pg.mkPen(_MatplotlibColors.BLUE))
        self.plot.setLabel(axis="bottom", text="Time [s]")
        self.plot.setLabel(axis="left", text="Current [mA]")
        model.laser_signals.data.connect(self.update_data_live)
        model.laser_signals.clear_pumplaser.connect(self.clear)

    def update_data_live(self, data: model.LaserBuffer) -> None:
        self.curves.setData(data.time, data.pump_laser_current)


class ProbeLaserCurrent(_Plotting):
    def __init__(self):
        _Plotting.__init__(self)
        self.curves = self.plot.plot(pen=pg.mkPen(_MatplotlibColors.BLUE))
        self.plot.setLabel(axis="bottom", text="Time [s]")
        self.plot.setLabel(axis="left", text="Current [mA]")
        model.laser_signals.data.connect(self.update_data_live)
        model.laser_signals.clear_probelaser.connect(self.clear)

    def update_data_live(self, data: model.LaserBuffer) -> None:
        self.curves.setData(data.time, data.probe_laser_current)


class TecTemperature(_Plotting):
    SET_POINT = 0
    MEASURAED = 1

    def __init__(self, channel: int):
        _Plotting.__init__(self)
        self.curves = [self.plot.plot(pen=pg.mkPen(_MatplotlibColors.BLUE), name="Setpoint Temperature"),
                       self.plot.plot(pen=pg.mkPen(_MatplotlibColors.ORANGE), name="Measured Temperature")]
        self.plot.setLabel(axis="bottom", text="Time [s]")
        self.plot.setLabel(axis="left", text="Temperature [°C]")
        self.laser = channel
        model.tec_signals[channel].clear_plots.connect(self.clear)
        model.signals.tec_data.connect(self.update_data_live)

    def update_data_live(self, data: model.TecBuffer) -> None:
        self.curves[TecTemperature.SET_POINT].setData(data.time, data.set_point[self.laser])
        self.curves[TecTemperature.MEASURAED].setData(data.time, data.actual_value[self.laser])
