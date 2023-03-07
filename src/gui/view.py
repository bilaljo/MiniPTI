import abc
import collections
import enum
import functools
import typing
from typing import NamedTuple

import pandas as pd
import pyqtgraph as pg
from PySide6 import QtWidgets, QtCore

import hardware.laser
from gui import model
from gui import controller


class MainWindow(QtWidgets.QMainWindow):
    HORIZONTAL_SIZE = 1200
    VERTICAL_SIZE = 800

    def __init__(self, main_controller: controller.MainApplication):
        QtWidgets.QMainWindow.__init__(self)
        self.setWindowTitle("Passepartout")
        self.main_controller = main_controller
        self.tab_bar = QtWidgets.QTabWidget(self)
        self.setCentralWidget(self.tab_bar)
        self.tabs: None | Tab = None
        self.current_pump_laser = PumpLaserCurrent()
        self.current_probe_laser = ProbeLaserCurrent()
        self.tec_values = TecCurrent()
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
        pump_laser = PumpLaser()
        pump_laser_tab = QtWidgets.QTabWidget()
        pump_laser_tab.setLayout(QtWidgets.QHBoxLayout())
        pump_laser_tab.layout().addWidget(pump_laser)
        pump_laser_tab.layout().addWidget(self.current_pump_laser.window)
        tab.addTab(pump_laser_tab, "Laser Driver")
        tec_tab = QtWidgets.QTabWidget()
        tec_tab.setLayout(QtWidgets.QHBoxLayout())
        tec_tab.layout().addWidget(Tec(laser="Pump Laser", signals=model.pump_laser_tec_signals))
        tec_tab.layout().addWidget(TecCurrent())
        tab.addTab(tec_tab, "Tec Driver")
        return tab

    def _init_probe_laser_tab(self) -> QtWidgets.QTabWidget:
        tab = QtWidgets.QTabWidget()
        probe_laser = ProbeLaser()
        probe_laser_tab = QtWidgets.QTabWidget()
        probe_laser_tab.setLayout(QtWidgets.QHBoxLayout())
        probe_laser_tab.layout().addWidget(probe_laser)
        probe_laser_tab.layout().addWidget(self.current_probe_laser.window)
        tab.addTab(probe_laser_tab, "Laser Driver")
        tec_tab = QtWidgets.QTabWidget()
        tec_tab.setLayout(QtWidgets.QHBoxLayout())
        tec_tab.layout().addWidget(Tec(laser="Probe Laser", signals=model.probe_laser_tec_signals))
        tec_tab.layout().addWidget(TecCurrent())
        tab.addTab(tec_tab, "Tec Driver")
        return tab

    def _init_tabs(self):
        self.tabs = Tab(home=Home(), pump_laser=self._init_pump_laser_tab(), probe_laser=self._init_probe_laser_tab(),
                        dc=QtWidgets.QTabWidget(), amplitudes=QtWidgets.QTabWidget(),
                        output_phases=QtWidgets.QTabWidget(), sensitivity=QtWidgets.QTabWidget(),
                        symmetry=QtWidgets.QTabWidget(), interferometric_phase=QtWidgets.QTabWidget(),
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
        close = QtWidgets.QMessageBox.question(
            self, "QUIT", "Are you sure you want to close?",
            QtWidgets.QMessageBox.StandardButton.Yes | QtWidgets.QMessageBox.StandardButton.No)
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
    def __init__(self, name):
        self.name = name
        self.frames = {}  # type: dict[str, QtWidgets.QGroupBox]

    def create_frame(self, master: QtWidgets.QWidget, title, x_position, y_position) -> None:
        self.frames[title] = QtWidgets.QGroupBox()
        self.frames[title].setTitle(title)
        self.frames[title].setLayout(QtWidgets.QGridLayout())
        master.layout().addWidget(self.frames[title], x_position, y_position)

    @abc.abstractmethod
    def _init_frames(self) -> None:
        ...


class _CreateButton:
    def __init__(self):
        self.buttons = {}  # type: dict[str, QtWidgets.QPushButton]

    def create_button(self, master, title, slot) -> None:
        self.buttons[title] = QtWidgets.QPushButton(master, text=title)
        self.buttons[title].clicked.connect(slot)
        master.layout().addWidget(self.buttons[title])

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
    def __init__(self):
        QtWidgets.QTabWidget.__init__(self)
        _Frames.__init__(self, name="Home")
        _CreateButton.__init__(self)
        self.setLayout(QtWidgets.QGridLayout())
        self.controller = controller.Home(self)
        self.logging_window = QtWidgets.QLabel()
        model.signals.logging_update.connect(self.logging_update)
        self._init_frames()
        self.settings = SettingsView(parent=self.frames["Setting"], settings_model=self.controller.settings_model)
        self.frames["Setting"].layout().addWidget(self.settings)
        self.frames["Log"].layout().addWidget(self.logging_window)
        self.destination_folder = QtWidgets.QLabel(self.controller.calculation_model.destination_folder)
        model.signals.destination_folder_changed.connect(self.update_destination_folder)
        self.save_raw_data = QtWidgets.QCheckBox("Save Raw Data")
        self._init_buttons()
        self._init_raw_data_button()

    def update_destination_folder(self) -> None:
        self.destination_folder.setText(self.controller.calculation_model.destination_folder)

    def _init_frames(self) -> None:
        self.create_frame(master=self.layout(), title="Log", x_position=0, y_position=1)
        self.create_frame(master=self.layout(), title="Setting", x_position=0, y_position=0)
        self.create_frame(master=self.layout(), title="Offline Processing", x_position=1, y_position=0)
        self.create_frame(master=self.layout(), title="Plot Data", x_position=2, y_position=0)
        self.create_frame(master=self.layout(), title="Drivers", x_position=1, y_position=1)
        self.create_frame(master=self.layout(), title="File Path", x_position=2, y_position=1)
        self.create_frame(master=self.layout(), title="Measurement", x_position=4, y_position=0)

    def _init_buttons(self) -> None:
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

        # Measurement Buttons
        sub_layout = QtWidgets.QWidget(parent=self.frames["Measurement"])
        sub_layout.setLayout(QtWidgets.QHBoxLayout())
        self.frames["Measurement"].layout().addWidget(sub_layout)
        self.create_button(master=sub_layout, title="Enable Pump Laser", slot=self.controller.enable_pump_laser)
        self.create_button(master=sub_layout, title="Enable Tec", slot=self.controller.find_devices)
        self.create_button(master=sub_layout, title="Enable Probe Laser", slot=self.controller.enable_probe_laser)
        self.create_button(master=sub_layout, title="Run Measurement", slot=self.controller.run_measurement)

    def logging_update(self, log_queue: collections.deque) -> None:
        self.logging_window.setText("".join(log_queue))

    def _init_raw_data_button(self) -> None:
        self.save_raw_data.setChecked(self.controller.calculation_model.save_raw_data)
        self.save_raw_data.stateChanged.connect(self.controller.calculation_model.set_raw_data_saving)


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
        _Frames.__init__(self, name="Pump Laser")
        self.model = None
        self.controller = controller.Laser()
        self.setLayout(QtWidgets.QGridLayout())
        self.current_display = QtWidgets.QLabel("0 mA")
        self.voltage_display = QtWidgets.QLabel("0 V")
        self.driver_voltage = Slider(minimum=PumpLaser.MIN_DRIVER_BIT, maximum=PumpLaser.MAX_DRIVER_BIT, unit="V")
        self.current = [Slider(minimum=PumpLaser.MIN_CURRENT, maximum=PumpLaser.MAX_CURRENT, unit="Bit"),
                        Slider(minimum=PumpLaser.MIN_CURRENT, maximum=PumpLaser.MAX_CURRENT, unit="Bit")]
        self.mode_matrix = [[QtWidgets.QComboBox() for _ in range(3)], [QtWidgets.QComboBox() for _ in range(3)]]
        self._init_frames()
        self._init_buttons()
        self._init_current_configuration()
        self._init_voltage_configuration()
        self.frames["Driver Voltage"].layout().addWidget(self.driver_voltage)
        self.frames["Measured Values"].layout().addWidget(self.current_display)
        self.frames["Measured Values"].layout().addWidget(self.voltage_display)
        model.signals.laser_data_display.connect(self._update_current_voltage)
        self.controller.load_configuration()

    @QtCore.Slot()
    def _update_current_voltage(self, value: hardware.laser.LaserData):
        self.current_display.setText(str(value.pump_laser_current) + " mA")
        self.voltage_display.setText(str(value.pump_laser_voltage) + " V")

    def _init_voltage_configuration(self):
        self.driver_voltage.slider.valueChanged.connect(self.controller.update_driver_voltage)
        model.signals.laser_voltage.connect(self._update_voltage_slider)

    def _init_current_configuration(self):
        self.current[0].slider.valueChanged.connect(self.controller.update_current_dac1)
        self.current[1].slider.valueChanged.connect(self.controller.update_current_dac2)
        model.signals.current_dac.connect(self._update_current_dac)
        for i in range(3):
            self.mode_matrix[0][i].currentIndexChanged.connect(self.controller.update_dac1(i))
            self.mode_matrix[1][i].currentIndexChanged.connect(self.controller.update_dac2(i))
        model.signals.matrix_dac.connect(self._update_dac_matrix)

    @QtCore.Slot(int, list)
    def _update_dac_matrix(self, dac_number: int, configuration: typing.Annotated[list[int], 3]) -> None:
        for channel in range(3):
            match configuration[channel]:
                case model.Mode.CONTINUOUS_WAVE:
                    self.mode_matrix[dac_number][channel].setCurrentIndex(ModeIndices.CONTINUOUS_WAVE)
                case model.Mode.PULSED:
                    self.mode_matrix[dac_number][channel].setCurrentIndex(ModeIndices.PULSED)
                case model.Mode.DISABLED:
                    self.mode_matrix[dac_number][channel].setCurrentIndex(ModeIndices.DISABLED)

    @QtCore.Slot(int, float)
    def _update_voltage_slider(self, index: int, value: float):
        self.driver_voltage.slider.setValue(index)
        self.driver_voltage.update_value(value)

    @QtCore.Slot(int, int)
    def _update_current_dac(self, dac: int, index: int):
        self.current[dac].slider.setValue(index)
        self.current[dac].update_value(index)

    def _init_frames(self):
        self.create_frame(master=self, title="Measured Values", x_position=1, y_position=0)
        self.create_frame(master=self, title="Driver Voltage", x_position=2, y_position=0)
        for i in range(1, 3):
            self.create_frame(master=self, title=f"Current {i}", x_position=i + 2, y_position=0)
        self.create_frame(master=self, title="Configuration", x_position=5, y_position=0)

    def _init_buttons(self):
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
        self.create_button(master=config, title="Save Configuration", slot=self.controller.save_configuration)
        self.create_button(master=config, title="Load Configuration", slot=self.controller.load_configuration)
        self.create_button(master=config, title="Apply Configuration", slot=self.controller.apply_configuration)
        self.frames["Configuration"].layout().addWidget(config, 4, 0)


class ProbeLaser(QtWidgets.QWidget, _CreateButton, _Frames):
    MIN_CURRENT_BIT = 0
    MAX_CURRENT_BIT = (1 << 8) - 1
    CONSTANT_CURRENT = 0
    CONSTANT_LIGHT = 1

    def __init__(self):
        QtWidgets.QWidget.__init__(self)
        _Frames.__init__(self, name="Probe Laser")
        _CreateButton.__init__(self)
        self.frames = {}
        self.setLayout(QtWidgets.QGridLayout())
        self.current_slider = Slider(minimum=ProbeLaser.MIN_CURRENT_BIT, maximum=ProbeLaser.MAX_CURRENT_BIT, unit="mA")
        self.controller = controller.Laser()
        self.laser_mode = QtWidgets.QComboBox()
        self.photo_gain = QtWidgets.QComboBox()
        self.current_display = QtWidgets.QLabel("0 mA")
        self._init_frames()
        self._init_slider()
        self._init_buttons()
        self.photo_gain.currentIndexChanged.connect(self.controller.update_photo_gain)
        self.laser_mode.currentIndexChanged.connect(self.controller.update_probe_laser_mode)
        self.frames["Measured Values"].layout().addWidget(self.current_display)
        self.max_current_display = QtWidgets.QLineEdit(str(self.controller.laser.probe_laser_max_current))
        self.max_current_display.returnPressed.connect(self.max_current_changed)
        self.frames["Maximum Current"].setLayout(QtWidgets.QGridLayout())
        self.frames["Maximum Current"].layout().addWidget(self.max_current_display, 0, 0)
        self.frames["Maximum Current"].layout().addWidget(QtWidgets.QLabel("mA"), 0, 1)
        model.signals.laser_data_display.connect(self.update_current)
        self.controller.load_configuration()

    @QtCore.Slot(hardware.laser.LaserData)
    def update_current(self, value: hardware.laser.LaserData) -> None:
        self.current_display.setText(str(value.probe_laser_current) + " mA")

    def max_current_changed(self) -> None:
        return self.controller.update_max_current_probe_laser(self.max_current_display.text())

    def _init_frames(self) -> None:
        self.create_frame(master=self.layout(), title="Maximum Current", x_position=0, y_position=0)
        self.create_frame(master=self.layout(), title="Measured Values", x_position=1, y_position=0)
        self.create_frame(master=self.layout(), title="Current", x_position=2, y_position=0)
        self.create_frame(master=self.layout(), title="Mode", x_position=3, y_position=0)
        self.create_frame(master=self.layout(), title="Photo Diode Gain", x_position=4, y_position=0)
        self.create_frame(master=self.layout(), title="Configuration", x_position=5, y_position=0)

    def _init_slider(self) -> None:
        self.frames["Current"].layout().addWidget(self.current_slider)
        self.current_slider.slider.valueChanged.connect(self.controller.update_current_probe_laser)
        model.signals.current_probe_laser.connect(self._update_current_slider)

    @QtCore.Slot(int, float)
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
        model.signals.photo_gain.connect(self._update_photo_gain)
        model.signals.probe_laser_mode.connect(self._update_mode)

    @QtCore.Slot(int)
    def _update_photo_gain(self, index: int) -> None:
        self.photo_gain.setCurrentIndex(index)

    @QtCore.Slot(int)
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
    def __init__(self, laser: str, signals: model.TecSignals):
        QtWidgets.QWidget.__init__(self)
        _Frames.__init__(self, name="Tec Driver")
        _CreateButton.__init__(self)
        self.setLayout(QtWidgets.QGridLayout())
        self.controller = controller.Tec(laser)
        self.text_fields = TecTextFields()
        self.signals = signals
        self._init_frames()
        self._init_text_fields()
        self._init_buttons()
        self.controller.load_configuration()

    def _init_frames(self) -> None:
        self.create_frame(master=self.layout(), title="PID Configuration", x_position=0, y_position=0)
        self.create_frame(master=self.layout(), title="System Settings", x_position=1, y_position=0)
        self.create_frame(master=self.layout(), title="System Parameters", x_position=2, y_position=0)
        self.create_frame(master=self.layout(), title="Configuration", x_position=3, y_position=0)

    @staticmethod
    def _update_text_field(text_field: QtWidgets.QLineEdit):
        @QtCore.Slot(float)
        def update(value: float):
            text_field.setText(str(round(value, 2)))
        return update

    def _init_text_fields(self) -> None:
        self.frames["PID Configuration"].layout().addWidget(QtWidgets.QLabel("P Value"), 0, 0)
        self.frames["PID Configuration"].layout().addWidget(self.text_fields.p_value, 0, 1)
        self.text_fields.p_value.returnPressed.connect(self.p_value_changed)
        self.signals.p_value.connect(Tec._update_text_field(self.text_fields.p_value))

        self.frames["PID Configuration"].layout().addWidget(QtWidgets.QLabel("I<sub>1</sub> Value"), 1, 0)
        self.frames["PID Configuration"].layout().addWidget(self.text_fields.i_value[0], 1, 1)
        self.text_fields.i_value[0].returnPressed.connect(self.i_1_value_changed)
        self.signals.i_1_value.connect(Tec._update_text_field(self.text_fields.i_value[0]))

        self.frames["PID Configuration"].layout().addWidget(QtWidgets.QLabel("I<sub>2</sub> Value"), 2, 0)
        self.frames["PID Configuration"].layout().addWidget(self.text_fields.i_value[1], 2, 1)
        self.text_fields.i_value[1].returnPressed.connect(self.i_2_value_changed)
        self.signals.i_2_value.connect(Tec._update_text_field(self.text_fields.i_value[1]))

        self.frames["PID Configuration"].layout().addWidget(QtWidgets.QLabel("D Value"), 3, 0)
        self.frames["PID Configuration"].layout().addWidget(self.text_fields.d_value, 3, 1)
        self.text_fields.d_value.returnPressed.connect(self.d_value_changed)
        self.signals.d_value.connect(Tec._update_text_field(self.text_fields.d_value))

        self.frames["System Settings"].layout().addWidget(QtWidgets.QLabel("Setpoint Temperature"), 0, 0)
        self.frames["System Settings"].layout().addWidget(self.text_fields.setpoint_temperature, 0, 1)
        self.text_fields.setpoint_temperature.returnPressed.connect(self.setpoint_temperature_changed)
        self.signals.setpoint_temperature.connect(Tec._update_text_field(self.text_fields.setpoint_temperature))

        self.frames["System Settings"].layout().addWidget(QtWidgets.QLabel("Loop Time"), 1, 0)
        self.frames["System Settings"].layout().addWidget(self.text_fields.loop_time, 1, 1)
        self.text_fields.loop_time.returnPressed.connect(self.loop_time_changed)
        self.signals.loop_time.connect(Tec._update_text_field(self.text_fields.loop_time))

        self.frames["System Settings"].layout().addWidget(QtWidgets.QLabel("Reference Resistor"), 2, 0)
        self.frames["System Settings"].layout().addWidget(self.text_fields.reference_resistor, 2, 1)
        self.text_fields.reference_resistor.returnPressed.connect(self.reference_resistor_changed)
        self.signals.reference_resistor.connect(Tec._update_text_field(self.text_fields.reference_resistor))

        self.frames["System Settings"].layout().addWidget(QtWidgets.QLabel("Max Power"), 3, 0)
        self.frames["System Settings"].layout().addWidget(self.text_fields.max_power, 3, 1)
        self.text_fields.max_power.returnPressed.connect(self.max_power_changed)
        self.signals.max_power.connect(Tec._update_text_field(self.text_fields.max_power))

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
                self.curves[channel].setData(data[f"DC CH{channel + 1}"])
            except KeyError:
                self.curves[channel].setData(data[f"PD{channel + 1}"])

    def update_data_live(self, data: model.PTIBuffer) -> None:
        for channel in range(3):
            self.curves[channel].setData(data.dc_values[channel])


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
            self.curves[channel].setData(data[f"Amplitude CH{channel + 1}"])

    def update_data_live(self, data: model.CharacterisationBuffer) -> None:
        for channel in range(3):
            self.curves[channel].setData(data.time, data.amplitudes[channel])


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
            self.curves[channel].setData(data[f"Output Phase CH{channel + 2}"])

    def update_data_live(self, data: model.CharacterisationBuffer) -> None:
        for channel in range(2):
            self.curves[channel].setData(data.time, data.output_phases[channel])


class InterferometricPhase(_Plotting):
    def __init__(self):
        _Plotting.__init__(self)
        self.curves = self.plot.plot(pen=pg.mkPen(_MatplotlibColors.BLUE))
        self.plot.setLabel(axis="bottom", text="Time [s]")
        self.plot.setLabel(axis="left", text="Interferometric Phase [rad]")
        model.signals.inversion.connect(self.update_data)
        model.signals.inversion_live.connect(self.update_data_live)

    def update_data(self, data: pd.DataFrame) -> None:
        self.curves.setData(data["Interferometric Phase"])

    def update_data_live(self, data: model.PTIBuffer) -> None:
        self.curves.setData(data.time, data.interferometric_phase)


class Sensitivity(_Plotting):
    def __init__(self):
        _Plotting.__init__(self)
        self.curves = [self.plot.plot(pen=pg.mkPen(_MatplotlibColors.BLUE)),
                       self.plot.plot(pen=pg.mkPen(_MatplotlibColors.ORANGE)),
                       self.plot.plot(pen=pg.mkPen(_MatplotlibColors.GREEN))]
        self.plot.setLabel(axis="bottom", text="Time [s]")
        self.plot.setLabel(axis="left", text="Sensitivity [V/rad]")
        model.signals.inversion.connect(self.update_data)
        model.signals.inversion_live.connect(self.update_data_live)

    def update_data(self, data: pd.DataFrame) -> None:
        for channel in range(3):
            self.curves[channel].setData(data[f"Sensitivity CH{channel + 1}"])

    def update_data_live(self, data: model.PTIBuffer) -> None:
        for channel in range(3):
            self.curves[channel].setData(data.time, data.sensitivity[channel])


class Symmetry(_Plotting):
    def __init__(self):
        _Plotting.__init__(self)
        self.curves = self.plot.plot(pen=pg.mkPen(_MatplotlibColors.BLUE))
        self.plot.setLabel(axis="bottom", text="Time [s]")
        self.plot.setLabel(axis="left", text="Symmetry [1]")
        model.signals.inversion.connect(self.update_data)
        model.signals.inversion_live.connect(self.update_data_live)

    def update_data(self, data: pd.DataFrame) -> None:
        self.curves.setData(data[f"Symmetry"])

    def update_data_live(self, data: model.PTIBuffer) -> None:
        self.curves.setData(data.time, data.symmetry)


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
            self.curves["PTI Signal"].setData(data["PTI Signal"])
            self.curves["PTI Signal Mean"].setData(data["PTI Signal 60 s Mean"])
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
        model.signals.laser_data.connect(self.update_data_live)

    def update_data(self, data: pd.DataFrame) -> None:
        raise NotImplementedError

    def update_data_live(self, data: model.LaserBuffer) -> None:
        self.curves.setData(data.time, data.pump_laser_current)


class PumpLaserVoltage(_Plotting):
    def __init__(self):
        _Plotting.__init__(self)
        self.curves = self.plot.plot(pen=pg.mkPen(_MatplotlibColors.BLUE))
        self.plot.setLabel(axis="bottom", text="Time [s]")
        self.plot.setLabel(axis="left", text="Voltage [V]")
        model.signals.laser_data.connect(self.update_data_live)

    def update_data(self, data: pd.DataFrame) -> None:
        raise NotImplementedError("There is no need to plot laser data offline")

    def update_data_live(self, data: model.LaserBuffer) -> None:
        self.curves.setData(data.time, data.pump_laser_voltage)


class ProbeLaserCurrent(_Plotting):
    def __init__(self):
        _Plotting.__init__(self)
        self.curves = self.plot.plot(pen=pg.mkPen(_MatplotlibColors.BLUE))
        self.plot.setLabel(axis="bottom", text="Time [s]")
        self.plot.setLabel(axis="left", text="Current [mA]")
        model.signals.laser_data.connect(self.update_data_live)

    def update_data(self, data: pd.DataFrame) -> None:
        raise NotImplementedError("There is no need to plot laser data offline")

    def update_data_live(self, data: model.LaserBuffer) -> None:
        self.curves.setData(data.time, data.probe_laser_current)


class TecCurrent(_Plotting):
    def __init__(self):
        _Plotting.__init__(self)
        self.curves = self.plot.plot(pen=pg.mkPen(_MatplotlibColors.BLUE))
        self.plot.setLabel(axis="bottom", text="Time [s]")
        self.plot.setLabel(axis="left", text="Current [mA]")
        # model.signals.laser_data.connect(self.update_data_live)

    def update_data(self, data: pd.DataFrame) -> None:
        raise NotImplementedError("There is no need to plot laser data offline")

    def update_data_live(self, data: model.LaserBuffer) -> None:
        self.curves.setData(data.time, data.probe_laser_current)
