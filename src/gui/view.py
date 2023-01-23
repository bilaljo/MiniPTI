import abc
from typing import NamedTuple,  Mapping

import pandas as pd
import pyqtgraph as pg
from PySide6 import QtWidgets, QtCore

from gui import model
from gui import controller


class MainWindow(QtWidgets.QMainWindow):
    HORZITONAL_SIZE = 1000
    VERTICAL_SIZE = 600

    def __init__(self, main_controller: controller.MainApplication):
        QtWidgets.QMainWindow.__init__(self)
        self.setWindowTitle("Passepartout")
        self.controller = main_controller
        self.driver_model = main_controller.driver_model
        self.tab_bar = QtWidgets.QTabWidget(self)
        self.setCentralWidget(self.tab_bar)
        self.tabs: None | Tab = None
        self.dc = DC()
        self.amplitudes = Amplitudes()
        self.output_phases = OutputPhases()
        self.interferometric_phase = InterferometricPhase()
        self.sensitivity = Sensitivity()
        self.pti_signal = PTISignal()
        self._init_tabs()
        self.tabs.home.settings.setModel(self.controller.settings_model)
        self.resize(MainWindow.HORZITONAL_SIZE, MainWindow.VERTICAL_SIZE)
        self.show()

    def _init_tabs(self):
        self.tabs = Tab(home=Home(controller.Home(self.controller, self)), daq=DAQ(), laser=PumpLaser(), tec=None,
                        dc=QtWidgets.QTabWidget(), amplitudes=QtWidgets.QTabWidget(),
                        output_phases=QtWidgets.QTabWidget(), sensitivity=QtWidgets.QTabWidget(),
                        interferometric_phase=QtWidgets.QTabWidget(),  pti_signal=QtWidgets.QTabWidget())
        self.tab_bar.addTab(self.tabs.home, "Home")
        self.tab_bar.addTab(self.tabs.daq, "Valves")
        self.tab_bar.addTab(self.tabs.laser, "Laser")
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
        # Sensitivty Plot
        self.tabs.sensitivity.setLayout(QtWidgets.QHBoxLayout())
        self.tabs.sensitivity.layout().addWidget(self.sensitivity.window)
        self.tab_bar.addTab(self.tabs.sensitivity, "Sensitivity")
        # PTI Signal Plot
        self.tabs.pti_signal.setLayout(QtWidgets.QHBoxLayout())
        self.tabs.pti_signal.layout().addWidget(self.pti_signal.window)
        self.tab_bar.addTab(self.tabs.pti_signal, "PTI Signal")

    def closeEvent(self, close_event):
        close = QtWidgets.QMessageBox.question(self, "QUIT", "Are you sure you want to close?",
                                               QtWidgets.QMessageBox.StandardButton.Yes
                                               | QtWidgets.QMessageBox.StandardButton.No)
        if close == QtWidgets.QMessageBox.StandardButton.Yes:
            close_event.accept()
            for port in self.driver_model.ports:
                port.close()
            self.controller.close()
        else:
            close_event.ignore()


class Plotting:
    def button_checked(self, frame, button):
        return self.buttons[frame][button].isChecked()

    def toggle_button(self, state, frame, button):
        if state:
            self.buttons[frame][button].setStyleSheet("background-color : lightgreen")
        else:
            self.buttons[frame][button].setStyleSheet("background-color : light gray")


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
    def _init_buttons(self): ...


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
        self.create_frame(title="Drivers", x_position=3, y_position=0)
        self.create_frame(title="Measurement", x_position=1, y_position=1)

    def _init_buttons(self):
        # SettingsTable buttons
        sub_layout = QtWidgets.QWidget()
        self.frames["Setting"].layout().addWidget(sub_layout)
        sub_layout.setLayout(QtWidgets.QHBoxLayout())
        self.create_button(master=sub_layout, title="Save Settings", slot=self.controller.save_settings)
        self.create_button(master=sub_layout, title="Load Settings", slot=self.controller.load_settings)
        # TODO: Implement autosave slot
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
        sub_layout.setLayout(QtWidgets.QVBoxLayout())
        self.frames["Measurement"].layout().addWidget(sub_layout)
        self.create_button(master=sub_layout, title="Enable Modulation", slot=self.controller.find_devices)
        self.create_button(master=sub_layout, title="Start Pump Laser", slot=self.controller.connect_devices)
        self.create_button(master=sub_layout, title="Run Measurement", slot=self.controller.connect_devices)

    def logging_update(self, log):
        self.logging_window.setText("".join(log))


class Slider(QtWidgets.QWidget):
    def __init__(self, minimum=0, maximum=100, unit="%"):
        QtWidgets.QWidget.__init__(self)
        self.slider = QtWidgets.QSlider()
        self.setLayout(QtWidgets.QHBoxLayout())
        self.layout().addWidget(self.slider)
        # self.slider.setTickPosition(QtWidgets.QSlider.TickPosition.TicksBothSides)
        self.slider.setOrientation(QtCore.Qt.Orientation.Horizontal)
        self.slider_value = QtWidgets.QLabel()
        self.layout().addWidget(self.slider_value)
        self.slider.setMinimum(minimum)
        self.slider.setMaximum(maximum)
        self.unit = unit

    def update_value(self, value):
        self.slider_value.setText(f"{round(value, 2)}" + self.unit)


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


class PumpLaser(_Tab, CreateButton):
    MIN_DRIVER_BIT = 0
    MAX_DRIVER_BIT = 127

    def __init__(self, name="Laser Driver"):
        _Tab.__init__(self, name)
        CreateButton.__init__(self)
        self.driver_model = model.Driver()
        self.probe_laser_tab = QtWidgets.QTabWidget()
        self.setLayout(QtWidgets.QGridLayout())
        self.laser_controller = controller.Laser(self)
        self.driver_voltage_slider = Slider(minimum=PumpLaser.MIN_DRIVER_BIT, maximum=PumpLaser.MAX_DRIVER_BIT,
                                            unit="V")
        model.signals.laser_voltage.connect(self.driver_voltage_slider.update_value)
        self.driver_voltage_slider.slider.valueChanged.connect(self.laser_controller.update_driver_voltage)
        self.dac_slider = [Slider(minimum=0, maximum=3, unit="V"), Slider(minimum=0, maximum=3, unit="V")]
        self.mode_matrix = [[QtWidgets.QComboBox() for _ in range(3)], [QtWidgets.QComboBox() for _ in range(3)]]
        self._init_frames()
        self.frames["Driver Voltage"].layout().addWidget(self.driver_voltage_slider)
        self._init_buttons()

    def _init_frames(self):
        self.create_frame(master=self, title="Driver Voltage", x_position=0, y_position=0)
        for i in range(1, 3):
            self.create_frame(master=self, title=f"DAC {i}", x_position=i, y_position=0)

    def _init_buttons(self):
        dac_inner_frames = [QtWidgets.QGroupBox() for _ in range(2)]  # For slider and button-matrices
        for j in range(2):
            self.frames[f"DAC {j + 1}"].setLayout(QtWidgets.QVBoxLayout())
            dac_inner_frames[j].setLayout(QtWidgets.QHBoxLayout())
            dac_inner_frames[j].layout().addWidget(self.dac_slider[j])
            for i in range(3):
                sub_frames = [QtWidgets.QWidget() for _ in range(3)]
                sub_frames[i].setLayout(QtWidgets.QVBoxLayout())
                dac_inner_frames[j].layout().addWidget(sub_frames[i])
                self.mode_matrix[j][i].addItem("Disabled")
                self.mode_matrix[j][i].addItem("Pulsed Mode")
                self.mode_matrix[j][i].addItem("Continuous Wave")
                if j == 0:
                    self.mode_matrix[j][i].currentIndexChanged.connect(self.laser_controller.mode_dac1(i))
                else:
                    self.mode_matrix[j][i].currentIndexChanged.connect(self.laser_controller.mode_dac2(i))
                sub_frames[i].layout().addWidget(QtWidgets.QLabel(f"Channel {i + 1}"))
                sub_frames[i].layout().addWidget(self.mode_matrix[j][i])
            self.frames[f"DAC {j + 1}"].layout().addWidget(dac_inner_frames[j])

        config = QtWidgets.QWidget()
        config.setLayout(QtWidgets.QHBoxLayout())
        self.create_button(master=config, title="Save Configuration", slot=self.laser_controller.update_configuration)
        self.create_button(master=config, title="Load Configuration", slot=self.laser_controller.update_configuration)
        self.create_button(master=config, title="Apply Configuration", slot=self.laser_controller.update_configuration)
        self.layout().addWidget(config, 3, 0)


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
        self.setLabel(axis="bottom", text="Time [s]")
        self.setLabel(axis="left", text="Intensity [V]")
        self.plot.addLegend()
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
        self.setLabel(axis="bottom", text="Time [s]")
        self.setLabel(axis="left", text="Amplitude [V]")
        self.showGrid(x=True, y=True)
        self.plot.addLegend()
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
        self.setLabel(axis="bottom", text="Time [s]")
        self.setLabel(axis="left", text="Output Phase [deg]")
        self.showGrid(x=True, y=True)
        self.plot.addLegend()
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
        self.setLabel(axis="bottom", text="Time [s]")
        self.setLabel(axis="left", text="Interferometric Phase [rad]")
        self.showGrid(x=True, y=True)
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
        self.setLabel(axis="bottom", text="Time [s]")
        self.setLabel(axis="left", text="Sensitivity [1/rad]")
        self.showGrid(x=True, y=True)
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
        self.setLabel(axis="bottom", text="Time [s]")
        self.setLabel(axis="left", text="PTI Signal [µrad]")
        self.plot.addLegend()
        model.signals.inversion.connect(self.update_data)
        model.signals.inversion_live.connect(self.update_data)

    def update_data(self, data: pd.DataFrame):
        self.curves["PTI Signal"].setData(data["PTI Signal"])
        self.curves["PTI Signal Mean"].setData(data["PTI Signal 60 s Mean"])

    def update_data_live(self, data: model.PTIBuffer):
        self.curves["PTI Signal"].setData(data.time, data.pti_signal)
        self.curves["PTI Signal Mean"].setData(data.time, data.pti_signal_mean)


class Tab(NamedTuple):
    home: Home
    daq: DAQ
    laser: PumpLaser | None  # Not implemented
    tec: None  # Not implemented
    dc: QtWidgets.QTabWidget
    amplitudes: QtWidgets.QTabWidget
    output_phases: QtWidgets.QTabWidget
    interferometric_phase: QtWidgets.QTabWidget
    sensitivity: QtWidgets.QTabWidget
    pti_signal: QtWidgets.QTabWidget
