import abc
from typing import NamedTuple

import pyqtgraph as pg
from PySide6 import QtWidgets, QtCore

import model
from dataclasses import dataclass


class MainWindow(QtWidgets.QMainWindow):
    def __init__(self, controller):
        QtWidgets.QMainWindow.__init__(self)
        self.setWindowTitle("Passepartout")
        self.controller = controller
        self.sheet = None
        self.tab_bar = QtWidgets.QTabWidget(self)
        self.setCentralWidget(self.tab_bar)
        self.tabs = Tab(Home(controller), DAQ(controller), LaserDriver(controller), DC(),
                        Amplitudes(), OutputPhases(), InterferometricPhase(), Sensitivity(), PTISignal())
        self.tabs.home.settings.setModel(model.SettingsTable())
        for tab in self.tabs:
            self.tab_bar.addTab(tab, tab.name)
        self.resize(900, 600)
        self.show()

    def closeEvent(self, close_event):
        close = QtWidgets.QMessageBox.question(self, "QUIT", "Are you sure you want to close?",
                                               QtWidgets.QMessageBox.StandardButton.Yes
                                               | QtWidgets.QMessageBox.StandardButton.No)
        if close == QtWidgets.QMessageBox.StandardButton.Yes:
            close_event.accept()
            self.model.daq.close()
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
        self.frames = {}
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
        self.buttons = {}

    def create_button(self, master, title, slot):
        self.buttons[title] = QtWidgets.QPushButton(master, text=title)
        self.buttons[title].clicked.connect(slot)
        master.layout().addWidget(self.buttons[title])

    @abc.abstractmethod
    def _init_buttons(self, controller): ...


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
    def __init__(self, controller, name="Home"):
        _Tab.__init__(self, name=name)
        CreateButton.__init__(self)
        self.logging_window = QtWidgets.QLabel()
        model.Signals.logging_update.connect(self.logging_update)
        self._init_frames()
        self.settings = SettingsView(parent=self.frames["Setting"])
        self.frames["Setting"].layout().addWidget(self.settings, 0, 0)
        self.frames["Log"].layout().addWidget(self.logging_window)
        self._init_buttons(controller)

    def _init_frames(self):
        self.create_frame(title="Log", x_position=0, y_position=1)
        self.create_frame(title="Setting", x_position=0, y_position=0)
        self.create_frame(title="Offline Processing", x_position=1, y_position=0)
        self.create_frame(title="Plot Data", x_position=2, y_position=0)
        self.create_frame(title="Drivers", x_position=3, y_position=0)

    def _init_buttons(self, controller):
        assert (controller is not None)
        # SettingsTable buttons
        sub_layout = QtWidgets.QWidget()
        self.frames["Setting"].layout().addWidget(sub_layout)
        sub_layout.setLayout(QtWidgets.QHBoxLayout())
        self.create_button(master=sub_layout, title="Save SettingsTable", slot=controller.save_settings)
        self.create_button(master=sub_layout, title="Load SettingsTable", slot=controller.load_settings)
        # TODO: Implement autosave slot
        self.create_button(master=sub_layout, title="Auto Save", slot=controller.load_settings)

        # Offline Processing buttons
        sub_layout = QtWidgets.QWidget()
        sub_layout.setLayout(QtWidgets.QHBoxLayout())
        self.frames["Offline Processing"].layout().addWidget(sub_layout)
        self.create_button(master=sub_layout, title="Decimation", slot=controller.calculate_decimation)
        self.create_button(master=sub_layout, title="Inversion", slot=controller.calculate_inversion)
        self.create_button(master=sub_layout, title="Characterisation", slot=controller.calculate_characterisation)

        # Plotting buttons
        sub_layout = QtWidgets.QWidget(parent=self.frames["Plot Data"])
        sub_layout.setLayout(QtWidgets.QHBoxLayout())
        self.frames["Plot Data"].layout().addWidget(sub_layout)
        self.create_button(master=sub_layout, title="Decimation", slot=controller.plot_dc)
        self.create_button(master=sub_layout, title="Inversion", slot=controller.plot_inversion)
        self.create_button(master=sub_layout, title="Characterisation", slot=controller.plot_characterisation)

        # Driver buttons
        sub_layout = QtWidgets.QWidget(parent=self.frames["Drivers"])
        sub_layout.setLayout(QtWidgets.QHBoxLayout())
        self.frames["Drivers"].layout().addWidget(sub_layout)
        self.create_button(master=sub_layout, title="Scan Ports", slot=controller.find_devices)
        self.create_button(master=sub_layout, title="Connect Devices", slot=controller.connect_devices)

    def logging_update(self, log):
        self.logging_window.setText("".join(log))


class Slider(QtWidgets.QWidget):
    def __init__(self, calculator=lambda x: x, minimum=0, maximum=100, unit="%"):
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
        self.slider.valueChanged.connect(self.update_value)
        self.calulcate_value = calculator
        self.slider_value.setText(f"0 {unit}")

    def calulcate_value(self):
        return self.slider.value()

    def update_value(self):
        self.slider_value.setText(f"{round(self.slider.value() / ((1 << 16) - 1) * 100, 2)} %")


class DAQ(_Tab, CreateButton):
    def __init__(self, controller, name="DAQ"):
        _Tab.__init__(self, name)
        CreateButton.__init__(self)
        self.port_box = QtWidgets.QLabel()
        self.connected_box = QtWidgets.QLabel()
        self._init_frames()
        self._init_buttons(controller)

    def _init_frames(self):
        self.create_frame(title="Valves", x_position=2, y_position=0)

    def _init_buttons(self, controller):
        self.frames["Valves"].layout().addWidget(QtWidgets.QLabel("Valve 1"))
        self.frames["Valves"].layout().addWidget(Slider())
        self.frames["Valves"].layout().addWidget(QtWidgets.QLabel("Valve 2"))
        self.frames["Valves"].layout().addWidget(Slider())


class LaserDriver(_Tab, CreateButton):
    def __init__(self, controller, name="Laser Driver"):
        _Tab.__init__(self, name)
        CreateButton.__init__(self)
        self.plot = _Plotting()
        self.tab_bar = QtWidgets.QTabWidget()
        self.config_tab = QtWidgets.QTabWidget()
        self.plot_tab = QtWidgets.QTabWidget()
        self.probe_laser_tab = QtWidgets.QTabWidget()
        self.config_tab.setLayout(QtWidgets.QGridLayout())
        self.probe_laser_tab.setLayout(QtWidgets.QGridLayout())
        self.plot_tab.setLayout(QtWidgets.QGridLayout())
        self.tab_bar.addTab(self.config_tab, "Pump Laser")
        self.tab_bar.addTab(self.plot_tab, "Probe Laser")
        self.tab_bar.addTab(self.probe_laser_tab, "Plots")
        self.driver_voltage_slider = Slider(minimum=0, maximum=3, unit="V")
        self.dac_slider = [Slider(minimum=0, maximum=3, unit="V"), Slider(minimum=0, maximum=3, unit="V")]
        self.mode_matrix = [[QtWidgets.QComboBox() for i in range(3)], [QtWidgets.QComboBox() for i in range(3)]]
        self.layout().addWidget(self.tab_bar)
        self._init_frames()
        # self._init_laser_plot()
        self._init_buttons(controller)

    def _init_frames(self):
        pass
        # self.create_frame(master=self.config_tab, title="Pump Laser", x_position=0, y_position=0)
        # self.create_frame(master=self.config_tab, title="Probe Laser", x_position=1, y_position=0)

    def _init_laser_plot(self):
        plot = self.plot.window.addPlot()
        plot.showGrid(x=True, y=True)
        self.frames["Plot"].layout().addWidget(self.plot.window)

    def _init_buttons(self, controller):
        voltage_frame = QtWidgets.QGroupBox()
        voltage_frame.setTitle("Driver Voltage")
        voltage_frame.setLayout(QtWidgets.QHBoxLayout())
        voltage_frame.layout().addWidget(Slider(minimum=0, maximum=3, unit="V"))
        self.config_tab.layout().addWidget(voltage_frame, 0, 0)

        dac_outer_frame = QtWidgets.QWidget()
        dac_inner_frames = [QtWidgets.QGroupBox() for _ in range(2)]
        self.config_tab.layout().addWidget(dac_outer_frame, 1, 0)
        for j in range(2):
            dac_outer_frame.setLayout(QtWidgets.QVBoxLayout())
            dac_inner_frames[j].setLayout(QtWidgets.QHBoxLayout())
            dac_inner_frames[j].setTitle(f"DAC {j + 1}")
            dac_outer_frame.layout().addWidget(dac_inner_frames[j])
            dac_inner_frames[j].layout().addWidget(self.dac_slider[j])
            for i in range(3):
                sub_frames = [QtWidgets.QWidget() for _ in range(3)]
                sub_frames[i].setLayout(QtWidgets.QVBoxLayout())
                dac_inner_frames[j].layout().addWidget(sub_frames[i])
                self.mode_matrix[j][i].addItem("Disabled")
                self.mode_matrix[j][i].addItem("Pulsed Mode")
                self.mode_matrix[j][i].addItem("Continuous Wave")
                sub_frames[i].layout().addWidget(QtWidgets.QLabel(f"Channel {i + 1}"))
                sub_frames[i].layout().addWidget(self.mode_matrix[j][i])

        config = QtWidgets.QWidget()
        config.setLayout(QtWidgets.QHBoxLayout())
        config.layout().addWidget(QtWidgets.QPushButton("Save Configuration"))
        choice_config = QtWidgets.QComboBox()
        choice_config.addItem("Config 1")
        choice_config.addItem("Config 2")
        config.layout().addWidget(choice_config)
        config.layout().addWidget(QtWidgets.QPushButton("Apply Configuration"))
        self.config_tab.layout().addWidget(config, 2, 0)


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

    @abc.abstractmethod
    def update_data(self, data: model.Buffer):
        ...


class DC(_Plotting):
    def __init__(self):
        _Plotting.__init__(self)
        self.curves = [self.plot(pen=pg.mkPen(_MatplotlibColors.BLUE), name="DC CH1"),
                       self.plot(pen=pg.mkPen(_MatplotlibColors.ORANGE), name="DC CH2"),
                       self.plot(pen=pg.mkPen(_MatplotlibColors.GREEN), name="DC CH3")]
        self.setLabel(axis="bottom", text="Time [s]")
        self.setLabel(axis="left", text="Intensity [V]")
        self.showGrid(x=True, y=True)
        self.layout().addWidget(self.window)
        model.Signals.inversion.connect(self.update_data)

    def update_data(self, data: model.PTIBuffer):
        for channel in range(3):
            self.curves[channel].setData(data.time, data.dc_values[channel])


class Amplitudes(_Plotting):
    def __init__(self):
        _Plotting.__init__(self)
        self.curves = [self.plot(pen=pg.mkPen(_MatplotlibColors.BLUE), name="Amplitude CH1"),
                       self.plot(pen=pg.mkPen(_MatplotlibColors.ORANGE), name="Amplitude CH2"),
                       self.plot(pen=pg.mkPen(_MatplotlibColors.GREEN), name="Amplitude CH3")]
        self.setLabel(axis="bottom", text="Time [s]")
        self.setLabel(axis="left", text="Amplitude [V]")
        self.showGrid(x=True, y=True)
        self.layout().addWidget(self.window)
        model.Signals.characterization.connect(self.update_data)

    def update_data(self, data: model.CharacterisationBuffer):
        for channel in range(3):
            self.curves[channel].setData(data.time, data.amplitudes[channel])


class OutputPhases(_Plotting):
    def __init__(self):
        _Plotting.__init__(self)
        self.curves = [self.plot(pen=pg.mkPen(_MatplotlibColors.ORANGE), name="Output Phase CH2"),
                       self.plot(pen=pg.mkPen(_MatplotlibColors.GREEN), name="Output Phase CH3")]
        self.setLabel(axis="bottom", text="Time [s]")
        self.setLabel(axis="left", text="Output Phase [deg]")
        self.showGrid(x=True, y=True)
        self.layout().addWidget(self.window)
        model.Signals.characterization.connect(self.update_data)

    def update_data(self, data: model.CharacterisationBuffer):
        for channel in range(2):
            self.curves[channel].setData(data.time, data.amplitudes[channel])


class InterferometricPhase(_Plotting):
    def __init__(self):
        _Plotting.__init__(self)
        self.curves = self.plot(pen=pg.mkPen(_MatplotlibColors.BLUE))
        self.setLabel(axis="bottom", text="Time [s]")
        self.setLabel(axis="left", text="Interferometric Phase [rad]")
        self.showGrid(x=True, y=True)
        self.layout().addWidget(self.plot.window)
        model.Signals.inversion.connect(self.update_data)

    def update_data(self, data: model.PTIBuffer):
        for channel in range(2):
            self.curves[channel].setData(data.time, data.interferometric_phase[channel])


class Sensitivity(_Plotting):
    def __init__(self):
        _Plotting.__init__(self)
        self.curves = self.plot(pen=pg.mkPen(_MatplotlibColors.BLUE))
        self.setLabel(axis="bottom", text="Time [s]")
        self.setLabel(axis="left", text="Sensitivity [1/rad]")
        self.showGrid(x=True, y=True)
        self.layout().addWidget(self.plot.window)
        model.Signals.inversion.connect(self.update_data)

    def update_data(self, data: model.PTIBuffer):
        self.curves.setData(data.time, data.sensitivity)


class PTISignal(_Plotting):
    def __init__(self):
        _Plotting.__init__(self)
        self.curves = {"PTI Signal": self.scatterPlot(pen=pg.mkPen(_MatplotlibColors.BLUE), name="1 s", size=6),
                       "PTI Signal Mean": self.plot(pen=pg.mkPen(_MatplotlibColors.ORANGE), name="60 s Mean")}
        self.setLabel(axis="bottom", text="Time [s]")
        self.setLabel(axis="left", text="PTI Signal [µrad]")
        self.showGrid(x=True, y=True)
        self.layout().addWidget(self.plot.window)
        model.Signals.inversion.connect(self.update_data)

    def update_data(self, data: model.PTIBuffer):
        self.curves["PTI Signal"].setData(data.time, data.pti_signal)
        self.curves["PTI Signal Mean"].setData(data.time, data.pti_signal_mean)


class Tab(NamedTuple):
    home: Home
    daq: DAQ
    laser_driver: LaserDriver
    dc: DC
    amplitudes: Amplitudes
    output_phases: OutputPhases
    interferometric_phase: InterferometricPhase
    sensitivity: Sensitivity
    pti_signal: PTISignal
