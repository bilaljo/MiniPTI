import abc
from typing import NamedTuple,  Mapping

import pandas as pd
import pyqtgraph as pg
from PySide6 import QtWidgets, QtCore

import hardware.laser
from gui import model
from gui import controller


class MainWindow(QtWidgets.QMainWindow):
    HORIZONTAL_SIZE = 1200
    VERTICAL_SIZE = 800

    def __init__(self, main_controller: controller.MainApplication, driver_controller: controller.Hardware):
        QtWidgets.QMainWindow.__init__(self)
        self.setWindowTitle("Passepartout")
        self.main_controller = main_controller
        self.hardware_controller = driver_controller
        self.hardware_model = driver_controller.hardware_model
        self.tab_bar = QtWidgets.QTabWidget(self)
        self.setCentralWidget(self.tab_bar)
        self.tabs: None | Tab = None
        self.current_pump_laser = PumpLaserCurrent()
        self.current_probe_laser = ProbeLaserCurrent()
        self.dc = DC()
        self.amplitudes = Amplitudes()
        self.output_phases = OutputPhases()
        self.interferometric_phase = InterferometricPhase()
        self.sensitivity = Sensitivity()
        self.pti_signal = PTISignal()
        self._init_tabs()
        self.tabs.home.settings.setModel(self.main_controller.settings_model)
        self.resize(MainWindow.HORIZONTAL_SIZE, MainWindow.VERTICAL_SIZE)
        self.show()

    def _init_pump_laser_tab(self) -> QtWidgets.QTabWidget:
        pump_laser_tab = QtWidgets.QTabWidget()
        pump_laser_tab.setLayout(QtWidgets.QHBoxLayout())
        pump_laser_tab.layout().addWidget(PumpLaser(self.hardware_model, self.hardware_controller))
        pump_laser_tab.layout().addWidget(self.current_pump_laser.window)
        return pump_laser_tab

    def _init_probe_laser_tab(self) -> QtWidgets.QTabWidget:
        probe_laser_tab = QtWidgets.QTabWidget()
        probe_laser_tab.setLayout(QtWidgets.QHBoxLayout())
        probe_laser_tab.layout().addWidget(ProbeLaser(self.hardware_model, self.hardware_controller))
        probe_laser_tab.layout().addWidget(self.current_probe_laser.window)
        return probe_laser_tab

    def _init_tec_tab(self) -> QtWidgets.QTabWidget:
        tec_tab = QtWidgets.QTabWidget()
        tec_tab.setLayout(QtWidgets.QHBoxLayout())
        return tec_tab

    def _init_tabs(self):
        self.tabs = Tab(home=Home(controller.Home(self.hardware_controller, self.main_controller, self)), daq=DAQ(),
                        pump_laser=self._init_pump_laser_tab(), probe_laser=self._init_probe_laser_tab(),
                        tec=self._init_tec_tab(), dc=QtWidgets.QTabWidget(), amplitudes=QtWidgets.QTabWidget(),
                        output_phases=QtWidgets.QTabWidget(), sensitivity=QtWidgets.QTabWidget(),
                        interferometric_phase=QtWidgets.QTabWidget(), pti_signal=QtWidgets.QTabWidget(),
                        aerosol_concentration=QtWidgets.QTabWidget())
        self.tab_bar.addTab(self.tabs.home, "Home")
        self.tab_bar.addTab(self.tabs.daq, "Valves")
        self.tab_bar.addTab(self.tabs.pump_laser, "Pump Laser")
        self.tab_bar.addTab(self.tabs.probe_laser, "Probe Laser")
        self.tab_bar.addTab(self.tabs.tec, "Tec")
        # DC Plot
        self.tabs.dc.setLayout(QtWidgets.QHBoxLayout())
        self.tabs.dc.layout().addWidget(self.dc.window)
        self.tab_bar.addTab(self.tabs.dc, "DC Signals")
        # Amplitudes Plot
        self.tabs.amplitudes.setLayout(QtWidgets.QHBoxLayout())
        self.tabs.amplitudes.layout().addWidget(Amplitudes().window)
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
        # PTI Signal Plot
        self.tabs.pti_signal.setLayout(QtWidgets.QHBoxLayout())
        self.tabs.pti_signal.layout().addWidget(self.pti_signal.window)
        self.tab_bar.addTab(self.tabs.pti_signal, "PTI Signal")
        self.tabs.pti_signal.setLayout(QtWidgets.QHBoxLayout())
        self.tabs.pti_signal.layout().addWidget(self.pti_signal.window)
        self.tab_bar.addTab(self.tabs.pti_signal, "Aersole Concentration")

    def closeEvent(self, close_event):
        close = QtWidgets.QMessageBox.question(self, "QUIT", "Are you sure you want to close?",
                                               QtWidgets.QMessageBox.StandardButton.Yes
                                               | QtWidgets.QMessageBox.StandardButton.No)
        if close == QtWidgets.QMessageBox.StandardButton.Yes:
            close_event.accept()
            for port in self.hardware_model.ports:
                port.close()
            self.main_controller.close()
        else:
            close_event.ignore()


class _Tab(QtWidgets.QTabWidget):
    def __init__(self, name="_Tab"):
        QtWidgets.QTabWidget.__init__(self)
        self.name = name
        self.frames = {}  # type: dict[str, QtWidgets.QGroupBox]
        self.setLayout(QtWidgets.QGridLayout())

    def create_frame(self, title, x_position, y_position, master=None):
        self.frames[title] = QtWidgets.QGroupBox()
        self.frames[title].setTitle(title)
        self.frames[title].setLayout(QtWidgets.QGridLayout())
        if master is None:
            self.layout().addWidget(self.frames[title], x_position, y_position)
        else:
            master.layout().addWidget(self.frames[title], x_position, y_position)


class CreateButton:
    def __init__(self):
        self.buttons = {}  # type: Mapping[str, QtWidgets.QPushButton]

    def create_button(self, master, title, slot):
        self.buttons[title] = QtWidgets.QPushButton(master, text=title)
        self.buttons[title].clicked.connect(slot)
        master.layout().addWidget(self.buttons[title])

    @abc.abstractmethod
    def _init_buttons(self):
        ...


class SettingsView(QtWidgets.QTableView):
    def __init__(self, parent):
        QtWidgets.QTableView.__init__(self, parent=parent)
        header = self.horizontalHeader()
        header.setStretchLastSection(True)
        index = self.verticalHeader()
        index.setSectionResizeMode(QtWidgets.QHeaderView.Stretch)
        header.setSectionResizeMode(QtWidgets.QHeaderView.Stretch)
        index.setStretchLastSection(True)
        self.resizeColumnsToContents()
        self.resizeRowsToContents()


class Home(_Tab, CreateButton):
    def __init__(self, home_controller, name="Home"):
        _Tab.__init__(self, name=name)
        CreateButton.__init__(self)
        self.controller = home_controller
        self.logging_window = QtWidgets.QLabel()
        model.signals.logging_update.connect(self.logging_update)
        self._init_frames()
        self.settings = SettingsView(parent=self.frames["Setting"])
        self.frames["Setting"].layout().addWidget(self.settings, 0, 0)
        self.frames["Log"].layout().addWidget(self.logging_window)
        self._init_buttons()

    def _init_frames(self):
        self.create_frame(title="Log", x_position=0, y_position=1)
        self.create_frame(title="Setting", x_position=0, y_position=0)
        self.create_frame(title="Offline Processing", x_position=1, y_position=0)
        self.create_frame(title="Plot Data", x_position=2, y_position=0)
        self.create_frame(title="Drivers", x_position=1, y_position=1)
        self.create_frame(title="Measurement", x_position=4, y_position=0)

    def _init_buttons(self):
        # SettingsTable buttons
        sub_layout = QtWidgets.QWidget()
        self.frames["Setting"].layout().addWidget(sub_layout)
        sub_layout.setLayout(QtWidgets.QHBoxLayout())
        self.create_button(master=sub_layout, title="Save Settings", slot=self.controller.save_settings)
        self.create_button(master=sub_layout, title="Load Settings", slot=self.controller.load_settings)
        # TODO: Implement autosave slot
        self.create_button(master=sub_layout, title="Auto Save", slot=self.controller.load_settings)
        sub_layout.layout().addWidget(QtWidgets.QLabel("10.5"))
        self.create_button(master=sub_layout, title="Auto Save", slot=self.controller.load_settings)

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

        # Measurement Buttons
        sub_layout = QtWidgets.QWidget(parent=self.frames["Measurement"])
        sub_layout.setLayout(QtWidgets.QHBoxLayout())
        self.frames["Measurement"].layout().addWidget(sub_layout)
        self.create_button(master=sub_layout, title="Enable Modulation", slot=self.controller.find_devices)
        self.create_button(master=sub_layout, title="Enable Tec", slot=self.controller.find_devices)
        self.create_button(master=sub_layout, title="Enable Probe Laser", slot=self.controller.enable_laser)
        self.create_button(master=sub_layout, title="Run Measurement", slot=self.controller.connect_devices)

    def logging_update(self, log):
        self.logging_window.setText("".join(log))


class Slider(QtWidgets.QWidget):
    def __init__(self, minimum=0, maximum=100, unit="%", floating_number=True):
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
        self.floating_number = floating_number

    def update_value(self, value):
        if self.floating_number:
            self.slider_value.setText(f"{round(value, 2)} " + self.unit)
        else:
            self.slider_value.setText(f"{value} " + self.unit)


class DAQ(_Tab, CreateButton):
    def __init__(self, name="DAQ"):
        _Tab.__init__(self, name)
        CreateButton.__init__(self)
        self.port_box = QtWidgets.QLabel()
        self.connected_box = QtWidgets.QLabel()
        self._init_frames()
        self._init_buttons()

    def _init_frames(self):
        self.create_frame(title="Valves", x_position=2, y_position=0)

    def _init_buttons(self):
        self.frames["Valves"].layout().addWidget(QtWidgets.QLabel("Valve 1"))
        self.frames["Valves"].layout().addWidget(Slider())
        self.frames["Valves"].layout().addWidget(QtWidgets.QLabel("Valve 2"))
        self.frames["Valves"].layout().addWidget(Slider())


class PumpLaser(QtWidgets.QWidget, CreateButton):
    MIN_DRIVER_BIT = 0
    MAX_DRIVER_BIT = (1 << 7) - 1
    MIN_CURRENT = 0
    MAX_CURRENT = (1 << 12) - 1

    def __init__(self, hardware_model: model.Hardware, hardware_controller: controller.Hardware):
        self.frames = {}
        QtWidgets.QWidget.__init__(self)
        CreateButton.__init__(self)
        self.hardware_model = hardware_model
        self.hardware_controller = hardware_controller
        self.setLayout(QtWidgets.QGridLayout())
        self.current_display = QtWidgets.QLabel("0 mA")
        self.voltage_display = QtWidgets.QLabel("0 V")
        self.driver_voltage = Slider(minimum=PumpLaser.MIN_DRIVER_BIT, maximum=PumpLaser.MAX_DRIVER_BIT,
                                     unit="V")
        self.current = [Slider(minimum=PumpLaser.MIN_CURRENT, maximum=PumpLaser.MAX_CURRENT, unit="Bit",
                               floating_number=False),
                        Slider(minimum=PumpLaser.MIN_CURRENT, maximum=PumpLaser.MAX_CURRENT, unit="Bit",
                               floating_number=False)]
        self.mode_matrix = [[QtWidgets.QComboBox() for _ in range(3)], [QtWidgets.QComboBox() for _ in range(3)]]
        self._init_frames()
        self._init_buttons()
        self._init_current_configuration()
        self._init_voltage_configuration()
        self.frames["Driver Voltage"].layout().addWidget(self.driver_voltage)
        self.frames["Measured Values"].layout().addWidget(self.current_display)
        self.frames["Measured Values"].layout().addWidget(self.voltage_display)
        model.signals.laser_data_display.connect(self.update_current_voltage)

    @QtCore.Slot()
    def update_current_voltage(self, value: hardware.laser.LaserData):
        self.current_display.setText(str(value.pump_laser_current) + " mA")
        self.voltage_display.setText(str(value.pump_laser_voltage) + " V")

    def _init_voltage_configuration(self):
        model.signals.laser_voltage.connect(self.driver_voltage.update_value)
        self.driver_voltage.slider.valueChanged.connect(self.hardware_controller.update_driver_voltage)
        self.driver_voltage.slider.setValue(self.hardware_controller.pump_laser.bit_value)

    def _init_current_configuration(self):
        self.current[0].slider.valueChanged.connect(self.hardware_controller.update_current_dac1)
        self.current[1].slider.valueChanged.connect(self.hardware_controller.update_current_dac2)
        model.signals.current_dac1.connect(self.current[0].update_value)
        model.signals.current_dac2.connect(self.current[1].update_value)
        for i in range(3):
            self.mode_matrix[0][i].currentIndexChanged.connect(self.hardware_controller.mode_dac1(i))
            if self.hardware_controller.pump_laser.DAC_1.continuous_wave[i]:
                self.mode_matrix[0][i].setCurrentIndex(model.Mode.CONTINUOUS_WAVE)
            elif self.hardware_controller.pump_laser.DAC_1.pulsed_mode[i]:
                self.mode_matrix[0][i].setCurrentIndex(model.Mode.PULSED)
            else:
                self.mode_matrix[0][i].setCurrentIndex(model.Mode.DISABLED)
        for i in range(3):
            self.mode_matrix[1][i].currentIndexChanged.connect(self.hardware_controller.mode_dac2(i))
            if self.hardware_controller.pump_laser.DAC_2.continuous_wave[i]:
                self.mode_matrix[1][i].setCurrentIndex(model.Mode.CONTINUOUS_WAVE)
            elif self.hardware_controller.pump_laser.DAC_2.pulsed_mode[i]:
                self.mode_matrix[1][i].setCurrentIndex(model.Mode.PULSED)
            else:
                self.mode_matrix[1][i].setCurrentIndex(model.Mode.DISABLED)
        self.current[0].slider.setValue(self.hardware_controller.pump_laser.DAC_1.bit_value)
        self.current[1].slider.setValue(self.hardware_controller.pump_laser.DAC_2.bit_value)

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
                self.mode_matrix[j][i].addItem("Pulsed Mode")
                self.mode_matrix[j][i].addItem("Continuous Wave")
                sub_frames[i].layout().addWidget(QtWidgets.QLabel(f"Channel {i + 1}"))
                sub_frames[i].layout().addWidget(self.mode_matrix[j][i])
            self.frames[f"Current {j + 1}"].layout().addWidget(dac_inner_frames[j])

        config = QtWidgets.QWidget()
        config.setLayout(QtWidgets.QHBoxLayout())
        self.create_button(master=config, title="Save Configuration", slot=self.hardware_controller.update_configuration)
        self.create_button(master=config, title="Load Configuration", slot=self.hardware_controller.update_configuration)
        self.create_button(master=config, title="Apply Configuration", slot=self.hardware_controller.update_configuration)
        self.frames["Configuration"].layout().addWidget(config, 4, 0)

    def create_frame(self, title, x_position, y_position, master=None):
        self.frames[title] = QtWidgets.QGroupBox()
        self.frames[title].setTitle(title)
        self.frames[title].setLayout(QtWidgets.QGridLayout())
        if master is None:
            self.layout().addWidget(self.frames[title], x_position, y_position)
        else:
            master.layout().addWidget(self.frames[title], x_position, y_position)


class ProbeLaser(QtWidgets.QWidget, CreateButton):
    MIN_CURRENT_BIT = 0
    MAX_CURRENT_BIT = (1 << 8) - 1
    CONSTANT_CURRENT = 0
    CONSTANT_LIGHT = 1

    def __init__(self, hardware_model: model.Hardware, hardware_controller: controller.Hardware):
        self.frames = {}
        QtWidgets.QWidget.__init__(self)
        CreateButton.__init__(self)
        self.frames = {}
        self.setLayout(QtWidgets.QGridLayout())
        self.current_slider = Slider(minimum=ProbeLaser.MIN_CURRENT_BIT, maximum=ProbeLaser.MAX_CURRENT_BIT,
                                     unit="mA")
        self.hardware_model = hardware_model
        self.hardware_controller = hardware_controller
        self.laser_mode = QtWidgets.QComboBox()
        self.photo_gain = QtWidgets.QComboBox()
        self.current_display = QtWidgets.QLabel("0 mA")
        self._init_frames()
        self._init_slider()
        self._init_buttons()
        self._init_photo_gain_configuration()
        self._init_current_mode_configuration()
        self.frames["Measured Values"].layout().addWidget(self.current_display)
        self.max_current_display = QtWidgets.QLineEdit()
        self.max_current_display.returnPressed.connect(self.max_current_changed)
        self.max_current_display.setText(str(self.hardware_controller.probe_laser.max_current_mA))
        self.frames["Maximum Current"].setLayout(QtWidgets.QGridLayout())
        self.frames["Maximum Current"].layout().addWidget(self.max_current_display, 0, 0)
        self.frames["Maximum Current"].layout().addWidget(QtWidgets.QLabel("mA"), 0, 1)
        model.signals.laser_data_display.connect(self.update_current)

    @QtCore.Slot(hardware.laser.LaserData)
    def update_current(self, value: hardware.laser.LaserData):
        self.current_display.setText(str(value.probe_laser_current) + " mA")

    def max_current_changed(self):
        return self.hardware_controller.update_max_current_probe_laser(self.max_current_display.text())

    def _init_frames(self):
        self.create_frame(title="Maximum Current", x_position=0, y_position=0)
        self.create_frame(title="Measured Values", x_position=1, y_position=0)
        self.create_frame(title="Current", x_position=2, y_position=0)
        self.create_frame(title="Mode", x_position=3, y_position=0)
        self.create_frame(title="Photo Diode Gain", x_position=4, y_position=0)
        self.create_frame(title="Configuration", x_position=5, y_position=0)

    def _init_slider(self):
        self.frames["Current"].layout().addWidget(self.current_slider)
        self.current_slider.slider.valueChanged.connect(self.hardware_controller.update_current_probe_laser)
        model.signals.current_probe_laser.connect(self.current_slider.update_value)
        self.current_slider.slider.setValue(self.hardware_controller.probe_laser.current_bits)

    def _init_buttons(self):
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
        self.create_button(master=config, title="Save Configuration", slot=self.hardware_controller.update_configuration)
        self.create_button(master=config, title="Load Configuration", slot=self.hardware_controller.update_configuration)
        self.create_button(master=config, title="Apply Configuration", slot=self.hardware_controller.update_configuration)
        self.frames["Configuration"].layout().addWidget(config, 3, 0)

    def _init_photo_gain_configuration(self):
        photo_gain = self.hardware_controller.probe_laser.photo_diode_gain
        if not isinstance(photo_gain, int) or not 1 <= photo_gain <= 4:
            photo_gain = 1
        self.photo_gain.setCurrentIndex(photo_gain - 1)
        self.photo_gain.currentIndexChanged.connect(self.hardware_controller.update_photo_gain)

    def _init_current_mode_configuration(self):
        if self.hardware_controller.probe_laser.constant_current:
            self.laser_mode.setCurrentIndex(ProbeLaser.CONSTANT_CURRENT)
        elif self.hardware_controller.probe_laser.constant_light:
            self.laser_mode.setCurrentIndex(ProbeLaser.CONSTANT_LIGHT)
        else:
            self.laser_mode.setCurrentIndex(ProbeLaser.CONSTANT_CURRENT)
        self.laser_mode.currentIndexChanged.connect(self.hardware_controller.update_probe_laser_mode)

    def create_frame(self, title, x_position, y_position, master=None):
        self.frames[title] = QtWidgets.QGroupBox()
        self.frames[title].setTitle(title)
        self.frames[title].setLayout(QtWidgets.QGridLayout())
        if master is None:
            self.layout().addWidget(self.frames[title], x_position, y_position)
        else:
            master.layout().addWidget(self.frames[title], x_position, y_position)


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
    def update_data(self, data: pd.DataFrame):
        ...

    @abc.abstractmethod
    def update_data_live(self, data: model.Buffer):
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
        model.signals.decimation_live.connect(self.update_data)

    def update_data(self, data: pd.DataFrame):
        for channel in range(3):
            self.curves[channel].setData(data[f"DC CH{channel + 1}"])

    def update_data_live(self, data: model.PTIBuffer):
        for channel in range(3):
            self.curves[channel].setData(data.dc_values[channel])


class Amplitudes(_Plotting):
    def __init__(self):
        _Plotting.__init__(self)
        self.curves = [self.plot.plot(pen=pg.mkPen(_MatplotlibColors.BLUE), name="Amplitude CH1"),
                       self.plot.plot(pen=pg.mkPen(_MatplotlibColors.ORANGE), name="Amplitude CH2"),
                       self.plot.plot(pen=pg.mkPen(_MatplotlibColors.GREEN), name="Amplitude CH3")]
        self.plot.setLabel(axis="bottom", text="Time [s]")
        self.plot.setLabel(axis="left", text="Amplitude [V]")
        model.signals.characterization.connect(self.update_data)
        model.signals.characterization_live.connect(self.update_data_live)

    def update_data(self, data: pd.DataFrame):
        for channel in range(3):
            self.curves[channel].setData(data[f"Amplitudes CH{channel + 1}"])

    def update_data_live(self, data: model.CharacterisationBuffer):
        for channel in range(3):
            self.curves[channel].setData(data.time, data.amplitudes[channel])


class OutputPhases(_Plotting):
    def __init__(self):
        _Plotting.__init__(self)
        self.curves = [self.plot.plot(pen=pg.mkPen(_MatplotlibColors.ORANGE), name="Output Phase CH2"),
                       self.plot.plot(pen=pg.mkPen(_MatplotlibColors.GREEN), name="Output Phase CH3")]
        self.plot.setLabel(axis="bottom", text="Time [s]")
        self.plot.setLabel(axis="left", text="Output Phase [deg]")
        model.signals.characterization.connect(self.update_data)
        model.signals.characterization_live.connect(self.update_data_live)

    def update_data(self, data: pd.DataFrame):
        for channel in range(1, 3):
            self.curves[channel].setData(data[f"Output Phases CH {channel + 1}"])

    def update_data_live(self, data: model.CharacterisationBuffer):
        for channel in range(2):
            self.curves[channel].setData(data.time, data.output_phases)


class InterferometricPhase(_Plotting):
    def __init__(self):
        _Plotting.__init__(self)
        self.curves = self.plot.plot(pen=pg.mkPen(_MatplotlibColors.BLUE))
        self.plot.setLabel(axis="bottom", text="Time [s]")
        self.plot.setLabel(axis="left", text="Interferometric Phase [rad]")
        model.signals.inversion.connect(self.update_data)
        model.signals.inversion_live.connect(self.update_data_live)

    def update_data(self, data: pd.DataFrame):
        self.curves.setData(data["Interferometric Phase"])

    def update_data_live(self, data: model.PTIBuffer):
        self.curves.setData(data.time, data.interferometric_phase)


class Sensitivity(_Plotting):
    def __init__(self):
        _Plotting.__init__(self)
        self.curves = self.plot.plot(pen=pg.mkPen(_MatplotlibColors.BLUE))
        self.plot.setLabel(axis="bottom", text="Time [s]")
        self.plot.setLabel(axis="left", text="Sensitivity [1/rad]")
        model.signals.inversion.connect(self.update_data)
        model.signals.inversion_live.connect(self.update_data_live)

    def update_data(self, data: pd.DataFrame):
        self.curves.setData(data.time, data.sensitivity)

    def update_data_live(self, data: model.PTIBuffer):
        self.curves.setData(data.time, data.sensitivity)


class PTISignal(_Plotting):
    def __init__(self):
        _Plotting.__init__(self)
        self.curves = {"PTI Signal": self.plot.scatterPlot(pen=pg.mkPen(_MatplotlibColors.BLUE), name="1 s", size=6),
                       "PTI Signal Mean": self.plot.plot(pen=pg.mkPen(_MatplotlibColors.ORANGE), name="60 s Mean")}
        self.plot.setLabel(axis="bottom", text="Time [s]")
        self.plot.setLabel(axis="left", text="PTI Signal [µrad]")
        model.signals.inversion.connect(self.update_data)
        model.signals.inversion_live.connect(self.update_data)

    def update_data(self, data: pd.DataFrame):
        self.curves["PTI Signal"].setData(data["PTI Signal"])
        self.curves["PTI Signal Mean"].setData(data["PTI Signal 60 s Mean"])

    def update_data_live(self, data: model.PTIBuffer):
        self.curves["PTI Signal"].setData(data.time, data.pti_signal)
        self.curves["PTI Signal Mean"].setData(data.time, data.pti_signal_mean)


class PumpLaserCurrent(_Plotting):
    def __init__(self):
        _Plotting.__init__(self)
        self.curves = self.plot.plot(pen=pg.mkPen(_MatplotlibColors.BLUE))
        self.plot.setLabel(axis="bottom", text="Time [s]")
        self.plot.setLabel(axis="left", text="Current [mA]")
        model.signals.laser_data.connect(self.update_data_live)

    def update_data(self, data: pd.DataFrame):
        raise NotImplementedError

    def update_data_live(self, data: model.LaserBuffer):
        self.curves.setData(data.time, data.pump_laser_current)


class PumpLaserVoltage(_Plotting):
    def __init__(self):
        _Plotting.__init__(self)
        self.curves = self.plot.plot(pen=pg.mkPen(_MatplotlibColors.BLUE))
        self.plot.setLabel(axis="bottom", text="Time [s]")
        self.plot.setLabel(axis="left", text="Voltage [V]")
        model.signals.laser_data.connect(self.update_data_live)

    def update_data(self, data: pd.DataFrame):
        raise NotImplementedError("There is no need to plot laser data offline")

    def update_data_live(self, data: model.LaserBuffer):
        self.curves.setData(data.time, data.pump_laser_voltage)


class ProbeLaserCurrent(_Plotting):
    def __init__(self):
        _Plotting.__init__(self)
        self.curves = self.plot.plot(pen=pg.mkPen(_MatplotlibColors.BLUE))
        self.plot.setLabel(axis="bottom", text="Time [s]")
        self.plot.setLabel(axis="left", text="Current [mA]")
        model.signals.laser_data.connect(self.update_data_live)

    def update_data(self, data: pd.DataFrame):
        raise NotImplementedError("There is no need to plot laser data offline")

    def update_data_live(self, data: model.LaserBuffer):
        self.curves.setData(data.time, data.probe_laser_current)


class Tab(NamedTuple):
    home: Home
    daq: DAQ
    pump_laser: QtWidgets.QTabWidget
    probe_laser: QtWidgets.QTabWidget
    tec: QtWidgets.QTabWidget
    dc: QtWidgets.QTabWidget
    amplitudes: QtWidgets.QTabWidget
    output_phases: QtWidgets.QTabWidget
    interferometric_phase: QtWidgets.QTabWidget
    sensitivity: QtWidgets.QTabWidget
    pti_signal: QtWidgets.QTabWidget
    aerosol_concentration: QtWidgets.QTabWidget
