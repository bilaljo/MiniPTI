import collections
from dataclasses import dataclass
from typing import NamedTuple, Union

from PyQt5 import QtWidgets, QtCore, QtGui
from PyQt5.QtCore import Qt

from minipti.gui.view import helper
from minipti.gui.view import plots
from minipti.gui import controller
from minipti.gui import model
from minipti.gui.view import hardware


class DAQPlots(NamedTuple):
    dc_signals: plots.DC
    amplitudes: plots.Amplitudes
    output_phases: plots.OutputPhases
    interferometric_phase: plots.InterferometricPhase
    sensitivity: plots.Sensitivity
    symmetry: plots.Symmetry
    pti_signal: plots.PTISignal


class LaserPlots(NamedTuple):
    current: tuple[plots.PumpLaserCurrent, plots.ProbeLaserCurrent]
    temperature: tuple[plots.TecTemperature, plots.TecTemperature]


class MainWindow(QtWidgets.QMainWindow):
    HORIZONTAL_SIZE = 1200
    VERTICAL_SIZE = 1000

    def __init__(self, controllers: controller.interface.Controllers):
        QtWidgets.QMainWindow.__init__(self)
        self.setWindowTitle("MiniPTI")
        self.setWindowIcon(QtGui.QIcon("../images/icon.png"))
        self.controllers = controllers
        self.tab_bar = QtWidgets.QTabWidget(self)
        self.setCentralWidget(self.tab_bar)
        self.logging_window = QtWidgets.QLabel()
        self.daq_plots = DAQPlots(dc_signals=plots.DC(), amplitudes=plots.Amplitudes(),
                                  output_phases=plots.OutputPhases(), symmetry=plots.Symmetry(),
                                  pti_signal=plots.PTISignal(), interferometric_phase=plots.InterferometricPhase(),
                                  sensitivity=plots.Sensitivity())
        self.laser_plots = LaserPlots(current=(plots.PumpLaserCurrent(), plots.ProbeLaserCurrent()),
                                      temperature=(plots.TecTemperature(model.Tec.PUMP_LASER),
                                                   plots.TecTemperature(model.Tec.PROBE_LASER)))
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

    def _init_laser_tab(self, laser: hardware.Driver, laser_index: int) -> QtWidgets.QTabWidget:
        tab = QtWidgets.QTabWidget()
        sub_layout = QtWidgets.QSplitter()
        laser_tab = QtWidgets.QTabWidget()
        laser_tab.setLayout(QtWidgets.QHBoxLayout())
        sub_layout.insertWidget(0, laser)
        sub_layout.insertWidget(1, self.laser_plots.current[laser_index].window)
        laser_tab.layout().addWidget(sub_layout)
        tab.addTab(laser_tab, "Laser Driver")
        sub_layout = QtWidgets.QSplitter()
        tec_tab = QtWidgets.QTabWidget()
        tec_tab.setLayout(QtWidgets.QHBoxLayout())
        sub_layout.insertWidget(0, hardware.Tec(self.controllers.tec[laser_index], laser_index))
        sub_layout.insertWidget(1, self.laser_plots.temperature[laser_index].window)
        tec_tab.layout().addWidget(sub_layout)
        tab.addTab(tec_tab, "Tec Driver")
        return tab

    def _init_tabs(self):
        self.tab_bar.addTab(Home(self.controllers.home), "Home")
        self.tab_bar.addTab(Settings(self.controllers.settings), "Settings")
        self.tab_bar.addTab(Utilities(self.controllers.utilities), "Utilities")
        self.tab_bar.addTab(self._init_laser_tab(hardware.PumpLaser(self.controllers.pump_laser),
                                                 model.Tec.PUMP_LASER), "Pump Laser")
        self.tab_bar.addTab(self._init_laser_tab(hardware.ProbeLaser(self.controllers.probe_laser),
                                                 model.Tec.PROBE_LASER), "Probe Laser")
        for plot in self.daq_plots:  # type: plots.DAQPlots
            plot_tab = QtWidgets.QTabWidget()
            plot_tab.setLayout(QtWidgets.QHBoxLayout())
            plot_tab.layout().addWidget(plot.window)
            self.tab_bar.addTab(plot_tab, plot.name)

    def closeEvent(self, close_event):
        close = QtWidgets.QMessageBox.question(self, "QUIT", "Are you sure you want to close?",
                                               QtWidgets.QMessageBox.StandardButton.Yes |
                                               QtWidgets.QMessageBox.StandardButton.No)
        if close == QtWidgets.QMessageBox.StandardButton.Yes:
            close_event.accept()
            self.controllers.main_application.close()
        else:
            close_event.ignore()


class Table(QtWidgets.QTableView):
    def __init__(self, parent, table_model: Union[model.Table, None] = None):
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


@dataclass
class HomeButtons:
    run_measurement: Union[QtWidgets.QPushButton, None] = None
    shutdown_and_close: Union[QtWidgets.QPushButton, None] = None


class Home(QtWidgets.QTabWidget):
    def __init__(self, home_controller):
        QtWidgets.QTabWidget.__init__(self)
        self.setLayout(QtWidgets.QGridLayout())
        self.controller = home_controller
        self.dc_signals = plots.DC()
        self.pti_signal = plots.PTISignal()
        self.buttons = HomeButtons()
        self._init_buttons()
        self._init_signals()
        sublayout = QtWidgets.QWidget()
        sublayout.setLayout(QtWidgets.QHBoxLayout())
        sublayout.layout().addWidget(self.dc_signals.window)
        sublayout.layout().addWidget(self.pti_signal.window)
        self.layout().addWidget(sublayout, 0, 0)

    def _init_buttons(self) -> None:
        sub_layout = QtWidgets.QWidget()
        sub_layout.setLayout(QtWidgets.QHBoxLayout())
        self.buttons.run_measurement = helper.create_button(parent=sub_layout, title="Run Measurement",
                                                            slot=self.controller.enable_motherboard)
        self.buttons.shutdown_and_close = helper.create_button(parent=sub_layout, title="Shutdown and Close",
                                                               slot=self.controller.shutdown_by_button)
        self.layout().addWidget(sub_layout, 1, 0)
        # self.create_button(master=sub_layout, title="Clean Air", slot=self.controller.update_bypass)

    @QtCore.pyqtSlot(bool)
    def update_run_measurement(self, state: bool) -> None:
        helper.toggle_button(state, self.buttons.run_measurement)

    # @QtCore.pyqtSlot(bool)
    # def update_clean_air(self, state: bool) -> None:
    #    helper.toggle_button(state, self.buttons["Clean Air"])

    def _init_signals(self) -> None:
        model.signals.daq_running.connect(self.update_run_measurement)


@dataclass
class SettingsFrames:
    pti_configuration: Union[QtWidgets.QGroupBox, None] = None
    measurement: Union[QtWidgets.QGroupBox, None] = None
    valve: Union[QtWidgets.QGroupBox, None] = None
    file_path: Union[QtWidgets.QGroupBox, None] = None


@dataclass
class SettingsButtons:
    save_pti_settings: Union[QtWidgets.QPushButton, None] = None
    save_pti_settings_as: Union[QtWidgets.QPushButton, None] = None
    load_pti_settings: Union[QtWidgets.QPushButton, None] = None
    save_motherboard_settings: Union[QtWidgets.QPushButton, None] = None
    save_motherboard_settings_as: Union[QtWidgets.QPushButton, None] = None
    load_motherboard_settings: Union[QtWidgets.QPushButton, None] = None


class Settings(QtWidgets.QTabWidget):
    def __init__(self, settings_controller: controller.interface.Settings):
        QtWidgets.QTabWidget.__init__(self)
        self.setLayout(QtWidgets.QGridLayout())
        self.controller = settings_controller
        self.destination_folder = QtWidgets.QLabel("")
        self.frames = SettingsFrames()
        self.buttons = SettingsButtons()
        self.algorithm_settings = Table(parent=self.frames.pti_configuration)
        self.destination_folder = QtWidgets.QLabel("")
        self.save_raw_data = QtWidgets.QCheckBox("Save Raw Data")
        self.automatic_valve_switch = QtWidgets.QCheckBox("Automatic Valve Switch")
        self.duty_cycle_valve = QtWidgets.QLabel("%")
        self.period_valve = QtWidgets.QLabel("s")
        self.duty_cycle_field = QtWidgets.QLineEdit()
        self.period_field = QtWidgets.QLineEdit()
        self.average_period = QtWidgets.QComboBox()
        self.samples = QtWidgets.QLabel("8000 Samples")
        self._init_frames()
        self._init_average_period_box()
        self.frames.pti_configuration.layout().addWidget(self.algorithm_settings)
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
        self.controller.motherboard.update_average_period(self.samples.text())

    @QtCore.pyqtSlot(model.Valve)
    def update_valve(self, valve: model.Valve) -> None:
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
        self.frames.file_path = helper.create_frame(parent=self, title="File Path", x_position=2, y_position=1)
        self.frames.measurement = helper.create_frame(parent=self, title="Measurement", x_position=1, y_position=1)
        self.frames.pti_configuration = helper.create_frame(parent=self, title="Configuration", x_position=0,
                                                            y_position=0, x_span=4)
        self.frames.valve = helper.create_frame(parent=self, title="Valve", x_position=3, y_position=1, x_span=2)

    def _init_buttons(self) -> None:
        # sub_layout = QtWidgets.QWidget()
        # self.frames.pti_configuration.layout().addWidget(sub_layout)
        # sub_layout.setLayout(QtWidgets.QHBoxLayout())
        sub_layout = QtWidgets.QWidget(parent=self.frames.pti_configuration)
        sub_layout.setLayout(QtWidgets.QHBoxLayout())
        self.frames.pti_configuration.layout().addWidget(sub_layout)
        self.buttons.save_settings = helper.create_button(parent=sub_layout, title="Save Settings",
                                                          slot=self.controller.save_settings)
        self.buttons.save_settings_as = helper.create_button(parent=sub_layout, title="Save Settings As",
                                                             slot=self.controller.save_settings_as)
        self.buttons.load_settings = helper.create_button(parent=sub_layout, title="Load Settings",
                                                          slot=self.controller.load_settings)
        self.frames.measurement.layout().addWidget(self.save_raw_data)
        sub_layout = QtWidgets.QWidget(parent=self.frames.file_path)
        sub_layout.setLayout(QtWidgets.QVBoxLayout())
        self.frames.file_path.layout().addWidget(sub_layout)
        self.destination_folder = helper.create_button(parent=sub_layout, title="Destination Folder",
                                                       slot=self.controller.set_destination_folder)
        sub_layout.layout().addWidget(self.destination_folder)

    def _init_valves(self) -> None:
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
        self.frames.valve.layout().addWidget(sub_layout)

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
class UtilitiesFrames:
    driver: Union[QtWidgets.QGroupBox, None] = None
    decimation: Union[QtWidgets.QGroupBox, None] = None
    pti_inversion: Union[QtWidgets.QGroupBox, None] = None
    characterisation: Union[QtWidgets.QGroupBox, None] = None


@dataclass
class UtilitiesButtons:
    plot_dc: Union[QtWidgets.QPushButton, None] = None
    calculate_decimation: Union[QtWidgets.QPushButton, None] = None
    plot_pti: Union[QtWidgets.QPushButton, None] = None
    calculate_pti_inversion: Union[QtWidgets.QPushButton, None] = None
    plot_characterisation: Union[QtWidgets.QPushButton, None] = None
    calculate_characterisation: Union[QtWidgets.QPushButton, None] = None


class Utilities(QtWidgets.QTabWidget):
    def __init__(self, utilities_controller):
        QtWidgets.QTabWidget.__init__(self)
        self.setLayout(QtWidgets.QGridLayout())
        self.controller = utilities_controller
        self.frames = UtilitiesFrames()
        self.buttons = UtilitiesButtons()
        self._init_frames()
        self._init_buttons()

    def _init_frames(self) -> None:
        self.frames.decimation = helper.create_frame(parent=self, title="Decimation", x_position=0, y_position=0)
        self.frames.pti_inversion = helper.create_frame(parent=self, title="PTI Inversion", x_position=1, y_position=0)
        self.frames.characterisation = helper.create_frame(parent=self, title="Interferometer Characterisation",
                                                           x_position=2, y_position=0)

    def _init_buttons(self) -> None:
        # Decimation
        sub_layout = QtWidgets.QWidget()
        sub_layout.setLayout(QtWidgets.QVBoxLayout())
        self.frames.decimation.layout().addWidget(sub_layout)
        self.buttons.calculate_decimation = helper.create_button(parent=sub_layout, title="Calculate",
                                                                 slot=self.controller.calculate_decimation)
        self.buttons.plot_dc = helper.create_button(parent=sub_layout, title="Plot DC Signals",
                                                    slot=self.controller.plot_dc)
        # PTI Inversion
        sub_layout = QtWidgets.QWidget()
        sub_layout.setLayout(QtWidgets.QVBoxLayout())
        self.frames.pti_inversion.layout().addWidget(sub_layout)
        self.buttons.calculate_pti_inversion = helper.create_button(parent=sub_layout, title="Calculate",
                                                                    slot=self.controller.calculate_pti_inversion)
        self.buttons.plot_pti = helper.create_button(parent=sub_layout, title="Plot",
                                                     slot=self.controller.plot_inversion)
        # Characterisation
        sub_layout = QtWidgets.QWidget()
        sub_layout.setLayout(QtWidgets.QVBoxLayout())
        self.frames.characterisation.layout().addWidget(sub_layout)
        self.buttons.calculate_characterisation = helper.create_button(parent=sub_layout, title="Calculate",
                                                                       slot=self.controller.calculate_characterisation)
        self.buttons.plot_characterisation = helper.create_button(parent=sub_layout, title="Plot",
                                                                  slot=self.controller.plot_characterisation)
