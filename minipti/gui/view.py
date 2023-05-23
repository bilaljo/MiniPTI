import abc
import collections
import enum
import functools
import logging
import typing
from typing import NamedTuple, Union

import pandas as pd
import pyqtgraph as pg
from PyQt5 import QtWidgets, QtCore, QtGui
from PyQt5.QtCore import Qt

from .. import hardware
from . import controller
from . import model


class MainWindow(QtWidgets.QMainWindow):
    HORIZONTAL_SIZE = 1100
    VERTICAL_SIZE = 800

    def __init__(self, main_controller):
        QtWidgets.QMainWindow.__init__(self)
        self.setWindowTitle("MiniPTI")
        self.setWindowIcon(QtGui.QIcon("images/icon.png"))
        self.main_controller = main_controller
        self.tab_bar = QtWidgets.QTabWidget(self)
        self.setCentralWidget(self.tab_bar)
        self.tabs: Union[Tab, None] = None
        self.current_pump_laser = PumpLaserCurrent()
        self.current_probe_laser = ProbeLaserCurrent()
        self.temperature_probe_laser = TecTemperature(laser="Probe Laser")
        self.temperature_pump_laser = TecTemperature(laser="Pump Laser")
        self.dc = DC()
        self.amplitudes = Amplitudes()
        self.output_phases = OutputPhases()
        self.interferometric_phase = InterferometricPhase()
        self.sensitivity = Sensitivity()
        self.symmetry = Symmetry()
        self.pti_signal = PTISignal()
        self._init_tabs()
        self.resize(MainWindow.HORIZONTAL_SIZE, MainWindow.VERTICAL_SIZE)
        self.show()

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
        sub_layout.insertWidget(0, Tec(laser="Pump Laser"))
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
        sub_layout.insertWidget(0, Tec(laser="Probe Laser"))
        sub_layout.insertWidget(1, self.temperature_probe_laser.window)
        tec_tab.layout().addWidget(sub_layout)
        tab.addTab(tec_tab, "Tec Driver")
        return tab

    def _init_tabs(self):
        self.tabs = Tab(home=Home(self, self.main_controller),
                        pump_laser=self._init_pump_laser_tab(),
                        probe_laser=self._init_probe_laser_tab(),
                        dc=QtWidgets.QTabWidget(),
                        amplitudes=QtWidgets.QTabWidget(),
                        output_phases=QtWidgets.QTabWidget(),
                        sensitivity=QtWidgets.QTabWidget(),
                        symmetry=QtWidgets.QTabWidget(),
                        interferometric_phase=QtWidgets.QTabWidget(),
                        pti_signal=QtWidgets.QTabWidget())
        self.tab_bar.addTab(self.tabs.home, "Home")
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
    pump_laser: QtWidgets.QTabWidget
    probe_laser: QtWidgets.QTabWidget
    dc: QtWidgets.QTabWidget
    amplitudes: QtWidgets.QTabWidget
    output_phases: QtWidgets.QTabWidget
    interferometric_phase: QtWidgets.QTabWidget
    sensitivity: QtWidgets.QTabWidget
    symmetry: QtWidgets.QTabWidget
    pti_signal: QtWidgets.QTabWidget


class _Frames:
    def __init__(self):
        self.frames = {}  # type: dict[str, Union[QtWidgets.QGroupBox, QtWidgets.QDockWidget]]

    def create_frame(self, master: QtWidgets.QWidget, title, x_position, y_position,
                     x_span=1, y_span=1) -> None:
        self.frames[title] = QtWidgets.QGroupBox()
        self.frames[title].setTitle(title)
        self.frames[title].setLayout(QtWidgets.QGridLayout())
        try:
            master.layout().addWidget(self.frames[title], x_position, y_position, x_span, y_span)
        except TypeError:
            master.layout().addWidget(self.frames[title])

    @abc.abstractmethod
    def _init_frames(self) -> None:
        ...


class _CreateButton:
    def __init__(self):
        self.buttons = {}  # type: dict[str, QtWidgets.QPushButton]

    def create_button(self, master, title, slot, master_title="") -> None:
        if master_title:
            master_title += " "
        self.buttons[master_title + title] = QtWidgets.QPushButton(master, text=title)
        self.buttons[master_title + title].clicked.connect(slot)
        master.layout().addWidget(self.buttons[master_title + title])

    @abc.abstractmethod
    def _init_buttons(self) -> None:
        ...


class SettingsView(QtWidgets.QTableView):
    def __init__(self, parent, settings_model: QtCore.QAbstractTableModel):
        QtWidgets.QTableView.__init__(self, parent=parent)
        header = self.horizontalHeader()
        header.setStretchLastSection(True)
        index = self.verticalHeader()
        index.setSectionResizeMode(QtWidgets.QHeaderView.Stretch)
        header.setSectionResizeMode(QtWidgets.QHeaderView.Stretch)
        index.setStretchLastSection(True)
        self.resizeColumnsToContents()
        self.resizeRowsToContents()
        self.setModel(settings_model)


def toggle_button(checked, button: QtWidgets.QPushButton) -> None:
    if checked:
        button.setStyleSheet("background-color : lightgreen")
    else:
        button.setStyleSheet("background-color : light gray")


class Home(QtWidgets.QTabWidget, _Frames, _CreateButton):
    def __init__(self, main_window: QtWidgets.QMainWindow, main_app: QtWidgets.QApplication):
        QtWidgets.QTabWidget.__init__(self)
        _Frames.__init__(self)
        _CreateButton.__init__(self)
        self.setLayout(QtWidgets.QGridLayout())
        self.controller = controller.Home(self, main_window, main_app)
        self.logging_window = QtWidgets.QLabel()
        model.signals.logging_update.connect(self.logging_update)
        self._init_frames()
        self.settings = SettingsView(parent=self.frames["Setting"], settings_model=self.controller.settings_model)
        self.frames["Setting"].layout().addWidget(self.settings)
        self.scroll = QtWidgets.QScrollArea(widgetResizable=True)
        self.scroll.setWidgetResizable(True)
        self.frames["Log"] = QtWidgets.QDockWidget("Log", self)
        self.scroll.setWidget(self.logging_window)
        self.frames["Log"].setWidget(self.scroll)
        self.frames["Battery"] = QtWidgets.QDockWidget("Battery", self)
        self.charge_level = QtWidgets.QLabel("NaN % left")
        self.minutes_left = QtWidgets.QLabel("NaN Minutes left")
        sub_layout = QtWidgets.QWidget()
        sub_layout.setMaximumWidth(150)
        sub_layout.setLayout(QtWidgets.QVBoxLayout())
        sub_layout.layout().addWidget(self.charge_level)
        sub_layout.layout().addWidget(self.minutes_left)
        self.frames["Battery"].setWidget(sub_layout)
        self.scroll.setWidget(self.logging_window)
        main_window.addDockWidget(Qt.BottomDockWidgetArea, self.frames["Log"])
        self.frames["Log"].show()
        main_window.addDockWidget(Qt.BottomDockWidgetArea, self.frames["Battery"])
        main_window.setCorner(Qt.BottomRightCorner, Qt.RightDockWidgetArea)
        self.destination_folder = QtWidgets.QLabel(self.controller.calculation_model.destination_folder)
        model.signals.destination_folder_changed.connect(self.update_destination_folder)
        self.save_raw_data = QtWidgets.QCheckBox("Save Raw Data")
        self.automatic_valve_switch = QtWidgets.QCheckBox("Automatic Valve Switch")
        self.duty_cyle_valve = QtWidgets.QLabel("%")
        self.period_valve = QtWidgets.QLabel("s")
        self.duty_cycle_field = QtWidgets.QLineEdit()
        self.period_field = QtWidgets.QLineEdit()
        self._init_buttons()
        self._init_raw_data_button()
        self._init_valves()
        self._init_signals()
        self.controller.fire_motherboard_configuration_change()

    def update_destination_folder(self) -> None:
        self.destination_folder.setText(self.controller.calculation_model.destination_folder)

    @QtCore.pyqtSlot(model.Battery)
    def update_battery_state(self, battery: model.Battery) -> None:
        self.charge_level.setText(f"{battery.percentage} % left")
        self.minutes_left.setText(f"Minutes left: {battery.minutes_left}")

    @QtCore.pyqtSlot(hardware.motherboard.Valve)
    def update_valve(self, valve: hardware.motherboard.Valve) -> None:
        self.duty_cycle_field.setText(str(valve.duty_cycle))
        self.period_field.setText(str(valve.period))
        self.automatic_valve_switch.setChecked(valve.automatic_switch)

    def _init_frames(self) -> None:
        sub_layout = QtWidgets.QWidget()
        sub_layout.setLayout(QtWidgets.QGridLayout())
        self.create_frame(master=sub_layout, title="File Path", x_position=0, y_position=1)
        self.create_frame(master=sub_layout, title="Shutdown", x_position=0, y_position=2)
        self.create_frame(master=self, title="Setting", x_position=0, y_position=0, x_span=2)
        self.create_frame(master=self, title="Offline Processing", x_position=2, y_position=0)
        self.create_frame(master=self, title="Plot Data", x_position=2, y_position=1)
        self.create_frame(master=self, title="Measurement", x_position=3, y_position=0)
        self.create_frame(master=self, title="Drivers", x_position=3, y_position=1)
        self.create_frame(master=self, title="Pump Laser", x_position=4, y_position=0)
        self.create_frame(master=self, title="Probe Laser", x_position=4, y_position=1)
        self.layout().addWidget(sub_layout, 1, 1)
        self.create_frame(master=self, title="Valve", x_position=0, y_position=1)

    def _init_buttons(self) -> None:
        self.create_button(master=self.frames["Shutdown"], title="Shutdown and Close",
                           slot=self.controller.shutdown_by_button)

        # SettingsTable buttons
        sub_layout = QtWidgets.QWidget()
        self.frames["Setting"].layout().addWidget(sub_layout)
        sub_layout.setLayout(QtWidgets.QHBoxLayout())
        self.create_button(master=sub_layout, title="Save Settings", slot=self.controller.save_settings)
        self.create_button(master=sub_layout, title="Load Settings", slot=self.controller.load_settings)
        sub_layout.layout().addWidget(self.save_raw_data)

        # Offline Processing buttons
        sub_layout = QtWidgets.QWidget()
        sub_layout.setLayout(QtWidgets.QHBoxLayout())
        self.frames["Offline Processing"].layout().addWidget(sub_layout)
        self.create_button(master=sub_layout, title="Decimation", slot=self.controller.calculate_decimation)
        self.create_button(master=sub_layout, title="Inversion", slot=self.controller.calculate_inversion)
        self.create_button(master=sub_layout, title="Characterisation", slot=self.controller.calculate_characterisation)

        # Plotting buttons
        sub_layout = QtWidgets.QWidget(parent=self.frames["Plot Data"])
        sub_layout.setLayout(QtWidgets.QHBoxLayout())
        self.frames["Plot Data"].layout().addWidget(sub_layout)
        self.create_button(master=sub_layout, title="Decimation", slot=self.controller.plot_dc)
        self.create_button(master=sub_layout, title="Inversion", slot=self.controller.plot_inversion)
        self.create_button(master=sub_layout, title="Characterisation", slot=self.controller.plot_characterisation)

        # Driver buttons
        sub_layout = QtWidgets.QWidget(parent=self.frames["Drivers"])
        sub_layout.setLayout(QtWidgets.QHBoxLayout())
        self.frames["Drivers"].layout().addWidget(sub_layout)
        self.create_button(master=sub_layout, title="Scan Ports", slot=self.controller.find_devices)
        self.create_button(master=sub_layout, title="Connect Devices", slot=self.controller.connect_devices)

        # Output File Location
        sub_layout = QtWidgets.QWidget(parent=self.frames["File Path"])
        sub_layout.setLayout(QtWidgets.QVBoxLayout())
        self.frames["File Path"].layout().addWidget(sub_layout)
        self.create_button(master=sub_layout, title="Destination Folder", slot=self.controller.set_destination_folder)
        sub_layout.layout().addWidget(self.destination_folder)

        # Valve Control
        sub_layout = QtWidgets.QWidget(parent=self.frames["Valve"])
        sub_layout.setLayout(QtWidgets.QGridLayout())
        sub_layout.layout().addWidget(self.automatic_valve_switch, 0, 0)
        sub_layout.layout().addWidget(QtWidgets.QLabel("Valve Period"), 1, 0)
        sub_layout.layout().addWidget(self.period_field, 1, 1)
        sub_layout.layout().addWidget(QtWidgets.QLabel("s"), 1, 2)
        sub_layout.layout().addWidget(QtWidgets.QLabel("Valve Duty Cycle"), 2, 0)
        sub_layout.layout().addWidget(self.duty_cycle_field, 2, 1)
        sub_layout.layout().addWidget(QtWidgets.QLabel("%"), 2, 2)
        self.frames["Valve"].layout().addWidget(sub_layout)
        sub_layout = QtWidgets.QWidget(parent=self.frames["Valve"])
        sub_layout.setLayout(QtWidgets.QHBoxLayout())
        self.create_button(master=sub_layout, title="Save Settings",
                           slot=self.controller.save_motherboard_configuration)
        self.create_button(master=sub_layout, title="Load Settings",
                           slot=self.controller.load_motherboard_configuration)
        self.frames["Valve"].layout().addWidget(sub_layout)

        # Measurement Buttons
        sub_layout = QtWidgets.QWidget(parent=self.frames["Measurement"])
        sub_layout.setLayout(QtWidgets.QHBoxLayout())
        self.frames["Measurement"].layout().addWidget(sub_layout)
        self.create_button(master=sub_layout, title="Run Measurement", slot=self.controller.run_measurement)
        self.create_button(master=sub_layout, title="Clean Air", slot=self.controller.update_bypass)

        # Pump Laser
        sub_layout = QtWidgets.QWidget(parent=self.frames["Pump Laser"])
        sub_layout.setLayout(QtWidgets.QHBoxLayout())
        self.create_button(master=sub_layout, title="Enable Laser", slot=self.controller.enable_pump_laser,
                           master_title="Pump Laser")
        self.create_button(master=sub_layout, title="Enable Tec", slot=self.controller.enable_tec_pump_laser,
                           master_title="Pump Laser")
        self.frames["Pump Laser"].layout().addWidget(sub_layout)

        # Probe Laser
        sub_layout = QtWidgets.QWidget(parent=self.frames["Probe Laser"])
        sub_layout.setLayout(QtWidgets.QHBoxLayout())
        self.create_button(master=sub_layout, title="Enable Laser", slot=self.controller.enable_probe_laser,
                           master_title="Probe Laser")
        self.create_button(master=sub_layout, title="Enable Tec", slot=self.controller.enable_tec_probe_laser,
                           master_title="Probe Laser")
        self.frames["Probe Laser"].layout().addWidget(sub_layout)

    def logging_update(self, log_queue: collections.deque) -> None:
        self.logging_window.setText("".join(log_queue))

    def _init_raw_data_button(self) -> None:
        self.save_raw_data.stateChanged.connect(self.controller.calculation_model.set_raw_data_saving)

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

    @QtCore.pyqtSlot(bool)
    def update_clean_air(self, state: bool) -> None:
        toggle_button(state, self.buttons["Clean Air"])

    @QtCore.pyqtSlot(bool)
    def update_enable_pump_laser(self, state: bool):
        toggle_button(state, self.buttons["Pump Laser Enable Laser"])

    @QtCore.pyqtSlot(bool)
    def update_enable_probe_laser(self, state: bool):
        toggle_button(state, self.buttons["Probe Laser Enable Laser"])

    @QtCore.pyqtSlot(bool)
    def update_enable_pump_laser_tec(self, state: bool):
        toggle_button(state, self.buttons["Pump Laser Enable Tec"])

    @QtCore.pyqtSlot(bool)
    def update_enable_probe_laser_tec(self, state: bool):
        toggle_button(state, self.buttons["Probe Laser Enable Tec"])

    def _init_signals(self) -> None:
        model.signals.valve_change.connect(self.update_valve)
        model.signals.bypass.connect(self.update_clean_air)
        model.laser_signals.pump_laser_enabled.connect(self.update_enable_pump_laser)
        model.laser_signals.probe_laser_enabled.connect(self.update_enable_probe_laser)
        model.tec_signals.pump_laser.enabled.connect(self.update_enable_pump_laser_tec)
        model.tec_signals.probe_laser.enabled.connect(self.update_enable_probe_laser_tec)


class Slider(QtWidgets.QWidget):
    def __init__(self, minimum=0, maximum=100, unit="%"):
        QtWidgets.QWidget.__init__(self)
        self.slider = QtWidgets.QSlider()
        self.setLayout(QtWidgets.QHBoxLayout())
        self.layout().addWidget(self.slider)
        self.slider.setOrientation(QtCore.Qt.Orientation.Horizontal)
        self.slider_value = QtWidgets.QLabel()
        self.layout().addWidget(self.slider_value)
        self.slider.setMinimum(minimum)
        self.slider.setMaximum(maximum)
        self.unit = unit
        self.index_value = 0  # type: typing.Any

    @functools.singledispatchmethod
    def update_value(self, value: int) -> None:
        self.slider_value.setText(f"{value} " + self.unit)

    @update_value.register
    def _(self, value: float) -> None:
        self.slider_value.setText(f"{round(value, 2)} " + self.unit)


class ModeIndices(enum.IntEnum):
    DISABLED = 0
    CONTINUOUS_WAVE = 1
    PULSED = 2


class PumpLaser(QtWidgets.QWidget, _Frames, _CreateButton):
    MIN_DRIVER_BIT = 0
    MAX_DRIVER_BIT = (1 << 7) - 1
    MIN_CURRENT = 0
    MAX_CURRENT = (1 << 12) - 1

    def __init__(self):
        QtWidgets.QWidget.__init__(self)
        _CreateButton.__init__(self)
        _Frames.__init__(self)
        self.model = None
        self.setLayout(QtWidgets.QGridLayout())
        self.current_display = QtWidgets.QLabel("0 mA")
        self.voltage_display = QtWidgets.QLabel("0 V")
        self.driver_voltage = Slider(minimum=PumpLaser.MIN_DRIVER_BIT, maximum=PumpLaser.MAX_DRIVER_BIT, unit="V")
        self.current = [Slider(minimum=PumpLaser.MIN_CURRENT, maximum=PumpLaser.MAX_CURRENT, unit="Bit"),
                        Slider(minimum=PumpLaser.MIN_CURRENT, maximum=PumpLaser.MAX_CURRENT, unit="Bit")]
        self.mode_matrix = [[QtWidgets.QComboBox() for _ in range(3)], [QtWidgets.QComboBox() for _ in range(3)]]
        self.controller = controller.PumpLaser(self)
        self._init_frames()
        self._init_current_configuration()
        self._init_voltage_configuration()
        self._init_buttons()
        self.frames["Driver Voltage"].layout().addWidget(self.driver_voltage)
        self.frames["Measured Values"].layout().addWidget(self.current_display)
        self.frames["Measured Values"].layout().addWidget(self.voltage_display)
        self._init_signals()
        self.controller.fire_configuration_change()

    def _init_signals(self) -> None:
        model.laser_signals.laser_voltage.connect(self._update_voltage_slider)
        model.laser_signals.current_dac.connect(self._update_current_dac)
        model.laser_signals.matrix_dac.connect(self._update_dac_matrix)
        model.laser_signals.data_display.connect(self._update_current_voltage)

    @QtCore.pyqtSlot(hardware.laser.Data)
    def _update_current_voltage(self, value: hardware.laser.Data) -> None:
        self.current_display.setText(str(value.pump_laser_current) + " mA")
        self.voltage_display.setText(str(value.pump_laser_voltage) + " V")

    def _init_voltage_configuration(self) -> None:
        self.driver_voltage.slider.valueChanged.connect(self.controller.update_driver_voltage)

    def _init_current_configuration(self) -> None:
        self.current[0].slider.valueChanged.connect(self.controller.update_current_dac1)
        self.current[1].slider.valueChanged.connect(self.controller.update_current_dac2)
        for i in range(3):
            self.mode_matrix[0][i].currentIndexChanged.connect(self.controller.update_dac1(i))
            self.mode_matrix[1][i].currentIndexChanged.connect(self.controller.update_dac2(i))

    @QtCore.pyqtSlot(int, list)
    def _update_dac_matrix(self, dac_number: int, configuration: typing.Annotated[list[int], 3]) -> None:
        for channel in range(3):
            if configuration[channel] == model.Mode.CONTINUOUS_WAVE:
                    self.mode_matrix[dac_number][channel].setCurrentIndex(ModeIndices.CONTINUOUS_WAVE)
            elif configuration[channel] == model.Mode.PULSED:
                self.mode_matrix[dac_number][channel].setCurrentIndex(ModeIndices.PULSED)
            elif configuration[channel] == model.Mode.DISABLED:
                self.mode_matrix[dac_number][channel].setCurrentIndex(ModeIndices.DISABLED)

    @QtCore.pyqtSlot(int, float)
    def _update_voltage_slider(self, index: int, value: float) -> None:
        self.driver_voltage.slider.setValue(index)
        self.driver_voltage.update_value(value)

    @QtCore.pyqtSlot(int, int)
    def _update_current_dac(self, dac: int, index: int) -> None:
        self.current[dac].slider.setValue(index)
        self.current[dac].update_value(index)

    def _init_frames(self) -> None:
        self.create_frame(master=self, title="Measured Values", x_position=1, y_position=0)
        self.create_frame(master=self, title="Driver Voltage", x_position=2, y_position=0)
        for i in range(1, 3):
            self.create_frame(master=self, title=f"Current {i}", x_position=i + 2, y_position=0)
        self.create_frame(master=self, title="Configuration", x_position=5, y_position=0)

    def _init_buttons(self) -> None:
        dac_inner_frames = [QtWidgets.QWidget() for _ in range(2)]  # For slider and button-matrices
        for j in range(2):
            dac_inner_frames[j].setLayout(QtWidgets.QGridLayout())
            self.frames[f"Current {j + 1}"].layout().addWidget(self.current[j])
            for i in range(3):
                sub_frames = [QtWidgets.QWidget() for _ in range(3)]
                sub_frames[i].setLayout(QtWidgets.QVBoxLayout())
                dac_inner_frames[j].layout().addWidget(sub_frames[i], 1, i)
                self.mode_matrix[j][i].addItem("Disabled")
                self.mode_matrix[j][i].addItem("Continuous Wave")
                self.mode_matrix[j][i].addItem("Pulsed Mode")
                sub_frames[i].layout().addWidget(QtWidgets.QLabel(f"Channel {i + 1}"))
                sub_frames[i].layout().addWidget(self.mode_matrix[j][i])
            self.frames[f"Current {j + 1}"].layout().addWidget(dac_inner_frames[j])

        config = QtWidgets.QWidget()
        config.setLayout(QtWidgets.QHBoxLayout())
        self.create_button(master=config, title="Save Configuration",  slot=self.controller.save_configuration)
        self.create_button(master=config, title="Load Configuration",  slot=self.controller.load_configuration)
        self.create_button(master=config, title="Apply Configuration", slot=self.controller.apply_configuration)
        self.frames["Configuration"].layout().addWidget(config, 4, 0)


class ProbeLaser(QtWidgets.QWidget, _CreateButton, _Frames):
    MIN_CURRENT_BIT = 0
    MAX_CURRENT_BIT = (1 << 8) - 1
    CONSTANT_CURRENT = 0
    CONSTANT_LIGHT = 1

    def __init__(self):
        QtWidgets.QWidget.__init__(self)
        _Frames.__init__(self)
        _CreateButton.__init__(self)
        self.frames = {}
        self.setLayout(QtWidgets.QGridLayout())
        self.current_slider = Slider(minimum=ProbeLaser.MIN_CURRENT_BIT, maximum=ProbeLaser.MAX_CURRENT_BIT, unit="mA")
        self.controller = controller.ProbeLaser(self)
        self.laser_mode = QtWidgets.QComboBox()
        self.photo_gain = QtWidgets.QComboBox()
        self.current_display = QtWidgets.QLabel("0")
        self._init_frames()
        self._init_slider()
        self._init_buttons()
        self.photo_gain.currentIndexChanged.connect(self.controller.update_photo_gain)
        self.laser_mode.currentIndexChanged.connect(self.controller.update_probe_laser_mode)
        self.frames["Measured Values"].layout().addWidget(self.current_display)
        self.max_current_display = QtWidgets.QLineEdit("")
        self.max_current_display.editingFinished.connect(self._max_current_changed)
        self.frames["Maximum Current"].layout().addWidget(self.max_current_display, 0, 0)
        self.frames["Maximum Current"].layout().addWidget(QtWidgets.QLabel("mA"), 0, 1)
        self._init_signals()
        self.controller.fire_configuration_change()

    def _init_signals(self) -> None:
        model.laser_signals.current_probe_laser.connect(self._update_current_slider)
        model.laser_signals.photo_gain.connect(self._update_photo_gain)
        model.laser_signals.probe_laser_mode.connect(self._update_mode)
        model.laser_signals.data_display.connect(self._update_current)
        model.laser_signals.max_current_probe_laser.connect(self._update_max_current)

    @QtCore.pyqtSlot(hardware.laser.Data)
    def _update_current(self, value: hardware.laser.Data) -> None:
        self.current_display.setText(str(value.probe_laser_current))

    @functools.singledispatchmethod
    def _update_max_current(self, value: int):
        self.max_current_display.setText(str(value))

    @_update_max_current.register
    def _(self, value: float):
        self.max_current_display.setText(str(round(value, 2)))

    def _max_current_changed(self) -> None:
        return self.controller.update_max_current_probe_laser(self.max_current_display.text())

    def _init_frames(self) -> None:
        self.create_frame(master=self, title="Maximum Current", x_position=0, y_position=0)
        self.create_frame(master=self, title="Measured Values", x_position=1, y_position=0)
        self.create_frame(master=self, title="Current", x_position=2, y_position=0)
        self.create_frame(master=self, title="Mode", x_position=3, y_position=0)
        self.create_frame(master=self, title="Photo Diode Gain", x_position=4, y_position=0)
        self.create_frame(master=self, title="Configuration", x_position=5, y_position=0)

    def _init_slider(self) -> None:
        self.frames["Current"].layout().addWidget(self.current_slider)
        self.current_slider.slider.valueChanged.connect(self.controller.update_current_probe_laser)

    @QtCore.pyqtSlot(int, float)
    def _update_current_slider(self, index: int, value: float) -> None:
        self.current_slider.slider.setValue(index)
        self.current_slider.update_value(value)

    def _init_buttons(self) -> None:
        sub_layout = QtWidgets.QWidget()
        sub_layout.setLayout(QtWidgets.QVBoxLayout())
        self.laser_mode.addItem("Constant Light")
        self.laser_mode.addItem("Constant Current")
        sub_layout.layout().addWidget(self.laser_mode)
        self.frames["Mode"].layout().addWidget(sub_layout)
        sub_layout = QtWidgets.QWidget()
        sub_layout.setLayout(QtWidgets.QVBoxLayout())
        self.photo_gain.addItem("1x")
        self.photo_gain.addItem("2x")
        self.photo_gain.addItem("3x")
        self.photo_gain.addItem("4x")
        sub_layout.layout().addWidget(self.photo_gain)
        self.frames["Photo Diode Gain"].layout().addWidget(sub_layout)
        config = QtWidgets.QWidget()
        config.setLayout(QtWidgets.QHBoxLayout())
        self.create_button(master=config, title="Save Configuration", slot=self.controller.save_configuration)
        self.create_button(master=config, title="Load Configuration", slot=self.controller.load_configuration)
        self.create_button(master=config, title="Apply Configuration", slot=self.controller.load_configuration)
        self.frames["Configuration"].layout().addWidget(config, 3, 0)

    @QtCore.pyqtSlot(int)
    def _update_photo_gain(self, index: int) -> None:
        self.photo_gain.setCurrentIndex(index)

    @QtCore.pyqtSlot(int)
    def _update_mode(self, index: int):
        self.laser_mode.setCurrentIndex(index)


class TecTextFields:
    def __init__(self):
        self.p_value = QtWidgets.QLineEdit()
        self.i_value = [QtWidgets.QLineEdit(), QtWidgets.QLineEdit()]
        self.d_value = QtWidgets.QLineEdit()
        self.setpoint_temperature = QtWidgets.QLineEdit()
        self.loop_time = QtWidgets.QLineEdit()
        self.reference_resistor = QtWidgets.QLineEdit()
        self.max_power = QtWidgets.QLineEdit()


class Tec(QtWidgets.QWidget, _Frames, _CreateButton):
    def __init__(self, laser: str):
        QtWidgets.QWidget.__init__(self)
        _Frames.__init__(self)
        _CreateButton.__init__(self)
        self.laser = laser
        self.setLayout(QtWidgets.QGridLayout())
        self.controller = controller.Tec(laser, self)
        self.text_fields = TecTextFields()
        self.temperature_display = QtWidgets.QLabel("NaN °C")
        self._init_frames()
        self._init_text_fields()
        self._init_buttons()
        self._init_signals()
        self.controller.fire_configuration_change()

    def _init_signals(self) -> None:
        model.signals.tec_data_display.connect(self.update_temperature)
        model.tec_signals[self.laser].p_value.connect(
            Tec._update_text_field(self.text_fields.p_value))
        model.tec_signals[self.laser].i_1_value.connect(
            Tec._update_text_field(self.text_fields.i_value[0]))
        model.tec_signals[self.laser].i_2_value.connect(
            Tec._update_text_field(self.text_fields.i_value[1]))
        model.tec_signals[self.laser].d_value.connect(
            Tec._update_text_field(self.text_fields.d_value))
        model.tec_signals[self.laser].setpoint_temperature.connect(
            Tec._update_text_field(self.text_fields.setpoint_temperature))
        model.tec_signals[self.laser].loop_time.connect(
            Tec._update_text_field(self.text_fields.loop_time))
        model.tec_signals[self.laser].reference_resistor.connect(
            Tec._update_text_field(self.text_fields.reference_resistor))
        model.tec_signals[self.laser].max_power.connect(
            Tec._update_text_field(self.text_fields.max_power))
        model.tec_signals[self.laser].mode.connect(self.update_mode)

    def _init_frames(self) -> None:
        self.create_frame(master=self, title="pid Configuration", x_position=0, y_position=0)
        self.create_frame(master=self, title="System Settings", x_position=1, y_position=0)
        self.create_frame(master=self, title="Temperature", x_position=2, y_position=0)
        self.create_frame(master=self, title="Configuration", x_position=3, y_position=0)

    @staticmethod
    def _update_text_field(text_field: QtWidgets.QLineEdit):
        @QtCore.pyqtSlot(float)
        def update(value: float):
            text_field.setText(str(round(value, 2)))

        return update

    @QtCore.pyqtSlot(hardware.tec.Data)
    def update_temperature(self, value: hardware.tec.Data) -> None:
        self.temperature_display.setText(str(value.actual_temperature[self.laser]) + " °C")

    @QtCore.pyqtSlot(model.TecMode)
    def update_mode(self, mode: model.TecMode):
        if mode == model.TecMode.COOLING:
            toggle_button(False, self.buttons["Heat"])
            toggle_button(True, self.buttons["Cool"])
        else:
            toggle_button(True, self.buttons["Heat"])
            toggle_button(False, self.buttons["Cool"])

    def _init_text_fields(self) -> None:
        self.frames["pid Configuration"].layout().addWidget(QtWidgets.QLabel("P Value"), 0, 0)
        self.frames["pid Configuration"].layout().addWidget(self.text_fields.p_value, 0, 1)
        self.text_fields.p_value.editingFinished.connect(self.p_value_changed)

        self.frames["pid Configuration"].layout().addWidget(QtWidgets.QLabel("I<sub>1</sub> Value"), 1, 0)
        self.frames["pid Configuration"].layout().addWidget(self.text_fields.i_value[0], 1, 1)
        self.text_fields.i_value[0].editingFinished.connect(self.i_1_value_changed)

        self.frames["pid Configuration"].layout().addWidget(QtWidgets.QLabel("I<sub>2</sub> Value"), 2, 0)
        self.frames["pid Configuration"].layout().addWidget(self.text_fields.i_value[1], 2, 1)
        self.text_fields.i_value[1].editingFinished.connect(self.i_2_value_changed)

        self.frames["pid Configuration"].layout().addWidget(QtWidgets.QLabel("D Value"), 3, 0)
        self.frames["pid Configuration"].layout().addWidget(self.text_fields.d_value, 3, 1)
        self.text_fields.d_value.editingFinished.connect(self.d_value_changed)

        self.frames["System Settings"].layout().addWidget(QtWidgets.QLabel("Setpoint Temperature"), 0, 0)
        self.frames["System Settings"].layout().addWidget(self.text_fields.setpoint_temperature, 0, 1)
        self.text_fields.setpoint_temperature.editingFinished.connect(self.setpoint_temperature_changed)

        self.frames["System Settings"].layout().addWidget(QtWidgets.QLabel("Loop Time"), 1, 0)
        self.frames["System Settings"].layout().addWidget(self.text_fields.loop_time, 1, 1)
        self.text_fields.loop_time.editingFinished.connect(self.loop_time_changed)

        self.frames["System Settings"].layout().addWidget(QtWidgets.QLabel("Reference Resistor"), 2, 0)
        self.frames["System Settings"].layout().addWidget(self.text_fields.reference_resistor, 2, 1)
        self.text_fields.reference_resistor.editingFinished.connect(self.reference_resistor_changed)

        self.frames["System Settings"].layout().addWidget(QtWidgets.QLabel("Max Power"), 3, 0)
        self.frames["System Settings"].layout().addWidget(self.text_fields.max_power, 3, 1)
        self.text_fields.max_power.editingFinished.connect(self.max_power_changed)

        self.frames["Temperature"].layout().addWidget(self.temperature_display)

    def d_value_changed(self) -> None:
        self.controller.update_d_value(self.text_fields.d_value.text())

    def i_1_value_changed(self) -> None:
        self.controller.update_i_1_value(self.text_fields.i_value[0].text())

    def i_2_value_changed(self) -> None:
        self.controller.update_i_2_value(self.text_fields.i_value[1].text())

    def p_value_changed(self) -> None:
        self.controller.update_p_value(self.text_fields.p_value.text())

    def setpoint_temperature_changed(self) -> None:
        self.controller.update_setpoint_temperature(self.text_fields.setpoint_temperature.text())

    def loop_time_changed(self) -> None:
        self.controller.update_loop_time(self.text_fields.loop_time.text())

    def reference_resistor_changed(self) -> None:
        self.controller.update_reference_resistor(self.text_fields.reference_resistor.text())

    def max_power_changed(self) -> None:
        self.controller.update_max_power(self.text_fields.max_power.text())

    def _init_buttons(self) -> None:
        config = QtWidgets.QWidget()
        config.setLayout(QtWidgets.QHBoxLayout())
        self.create_button(master=config, title="Save Configuration", slot=self.controller.save_configuration)
        self.create_button(master=config, title="Load Configuration", slot=self.controller.load_configuration)
        self.create_button(master=config, title="Apply Configuration", slot=self.controller.load_configuration)
        self.frames["Configuration"].layout().addWidget(config, 3, 0)

        self.create_button(master=self.frames["Temperature"], title="Heat", slot=self.controller.set_heating)
        self.create_button(master=self.frames["Temperature"], title="Cool", slot=self.controller.set_cooling)


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

    @abc.abstractmethod
    def clear(self) -> None:
        ...

    @abc.abstractmethod
    def update_data(self, data: pd.DataFrame) -> None:
        ...

    @abc.abstractmethod
    def update_data_live(self, data: model.Buffer) -> None:
        ...


class DC(_Plotting):
    def __init__(self):
        _Plotting.__init__(self)
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

    def clear(self) -> None:
        for channel in range(3):
            self.curves[channel].setData([])


class Amplitudes(_Plotting):
    def __init__(self):
        _Plotting.__init__(self)
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

    def clear(self) -> None:
        self.curves = [self.plot.scatterPlot(pen=pg.mkPen(_MatplotlibColors.BLUE),
                                             brush=pg.mkBrush(_MatplotlibColors.BLUE),
                                             name="Amplitude CH1"),
                       self.plot.scatterPlot(pen=pg.mkPen(_MatplotlibColors.ORANGE),
                                             brush=pg.mkBrush(_MatplotlibColors.ORANGE),
                                             name="Amplitude CH2"),
                       self.plot.scatterPlot(pen=pg.mkPen(_MatplotlibColors.GREEN),
                                             brush=pg.mkBrush(_MatplotlibColors.GREEN),
                                             name="Amplitude CH3")]


class OutputPhases(_Plotting):
    def __init__(self):
        _Plotting.__init__(self)
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

    def clear(self) -> None:
        self.curves = [self.plot.scatterPlot(pen=pg.mkPen(_MatplotlibColors.ORANGE), name="Output Phase CH2",
                                             brush=pg.mkBrush(_MatplotlibColors.ORANGE)),
                       self.plot.scatterPlot(pen=pg.mkPen(_MatplotlibColors.GREEN), name="Output Phase CH3",
                                             brush=pg.mkBrush(_MatplotlibColors.GREEN))]


class InterferometricPhase(_Plotting):
    def __init__(self):
        _Plotting.__init__(self)
        self.curves = self.plot.plot(pen=pg.mkPen(_MatplotlibColors.BLUE))
        self.plot.setLabel(axis="bottom", text="Time [s]")
        self.plot.setLabel(axis="left", text="Interferometric Phase [rad]")
        model.signals.inversion.connect(self.update_data)
        model.signals.inversion_live.connect(self.update_data_live)

    def update_data(self, data: pd.DataFrame) -> None:
        self.curves.setData(data["Interferometric Phase"].to_numpy())

    def update_data_live(self, data: model.PTIBuffer) -> None:
        self.curves.setData(data.time, data.interferometric_phase)

    def clear(self) -> None:
        self.curves = self.plot.plot(pen=pg.mkPen(_MatplotlibColors.BLUE))


class Sensitivity(_Plotting):
    def __init__(self):
        _Plotting.__init__(self)
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

    def clear(self) -> None:
        self.curves = [self.plot.plot(pen=pg.mkPen(_MatplotlibColors.BLUE), name="CH1"),
                       self.plot.plot(pen=pg.mkPen(_MatplotlibColors.ORANGE), name="CH2"),
                       self.plot.plot(pen=pg.mkPen(_MatplotlibColors.GREEN), name="CH3")]


class Symmetry(_Plotting):
    def __init__(self):
        _Plotting.__init__(self)
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

    def clear(self) -> None:
        self.curves = [self.plot.scatterPlot(pen=pg.mkPen(_MatplotlibColors.BLUE), name="Absolute Symmetry",
                                             brush=pg.mkBrush(_MatplotlibColors.BLUE)),
                       self.plot.scatterPlot(pen=pg.mkPen(_MatplotlibColors.ORANGE), name="Relative Symmetry",
                                             brush=pg.mkBrush(_MatplotlibColors.ORANGE))]


class PTISignal(_Plotting):
    def __init__(self):
        _Plotting.__init__(self)
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

    def clear(self) -> None:
        self.curves = {"PTI Signal": self.plot.scatterPlot(pen=pg.mkPen(_MatplotlibColors.BLUE), name="1 s", size=6),
                       "PTI Signal Mean": self.plot.plot(pen=pg.mkPen(_MatplotlibColors.ORANGE), name="60 s Mean")}


class PumpLaserCurrent(_Plotting):
    def __init__(self):
        _Plotting.__init__(self)
        self.curves = self.plot.plot(pen=pg.mkPen(_MatplotlibColors.BLUE))
        self.plot.setLabel(axis="bottom", text="Time [s]")
        self.plot.setLabel(axis="left", text="Current [mA]")
        model.laser_signals.data.connect(self.update_data_live)

    def update_data(self, data: pd.DataFrame) -> None:
        raise NotImplementedError

    def update_data_live(self, data: model.LaserBuffer) -> None:
        self.curves.setData(data.time, data.pump_laser_current)

    def clear(self) -> None:
        self.curves = self.plot.plot(pen=pg.mkPen(_MatplotlibColors.BLUE))


class PumpLaserVoltage(_Plotting):
    def __init__(self):
        _Plotting.__init__(self)
        self.curves = self.plot.plot(pen=pg.mkPen(_MatplotlibColors.BLUE))
        self.plot.setLabel(axis="bottom", text="Time [s]")
        self.plot.setLabel(axis="left", text="Voltage [V]")
        model.laser_signals.data.connect(self.update_data_live)

    def update_data(self, data: pd.DataFrame) -> None:
        raise NotImplementedError("There is no need to plot laser data offline")

    def update_data_live(self, data: model.LaserBuffer) -> None:
        self.curves.setData(data.time, data.pump_laser_voltage)

    def clear(self) -> None:
        self.curves = self.plot.plot(pen=pg.mkPen(_MatplotlibColors.BLUE))


class ProbeLaserCurrent(_Plotting):
    def __init__(self):
        _Plotting.__init__(self)
        self.curves = self.plot.plot(pen=pg.mkPen(_MatplotlibColors.BLUE))
        self.plot.setLabel(axis="bottom", text="Time [s]")
        self.plot.setLabel(axis="left", text="Current [mA]")
        model.laser_signals.data.connect(self.update_data_live)

    def update_data(self, data: pd.DataFrame) -> None:
        raise NotImplementedError("There is no need to plot laser data offline")

    def update_data_live(self, data: model.LaserBuffer) -> None:
        self.curves.setData(data.time, data.probe_laser_current)

    def clear(self) -> None:
        self.curves = self.plot.plot(pen=pg.mkPen(_MatplotlibColors.BLUE))


class TecTemperature(_Plotting):
    ACTUAL = 0
    MEASURAED = 1

    def __init__(self, laser: str):
        _Plotting.__init__(self)
        self.curves = [self.plot.plot(pen=pg.mkPen(_MatplotlibColors.BLUE), name="Setpoint Temperature"),
                       self.plot.plot(pen=pg.mkPen(_MatplotlibColors.ORANGE), name="Measured Temperature")]
        self.plot.setLabel(axis="bottom", text="Time [s]")
        self.plot.setLabel(axis="left", text="Temperature [°C]")
        if laser == "Pump Laser":
            self.laser = model.TecBuffer.PUMP_LASER
        else:
            self.laser = model.TecBuffer.PROBE_LASER
        model.signals.tec_data.connect(self.update_data_live)

    def update_data(self, data: pd.DataFrame) -> None:
        raise NotImplementedError("There is no need to plot laser data offline")

    def update_data_live(self, data: model.TecBuffer) -> None:
        self.curves[TecTemperature.ACTUAL].setData(data.time, data.actual_value[self.laser])
        self.curves[TecTemperature.MEASURAED].setData(data.time, data.set_point[self.laser])

    def clear(self) -> None:
        self.curves = [self.plot.plot(pen=pg.mkPen(_MatplotlibColors.BLUE), name="Setpoint Temperature"),
                       self.plot.plot(pen=pg.mkPen(_MatplotlibColors.ORANGE), name="Measured Temperature")]
