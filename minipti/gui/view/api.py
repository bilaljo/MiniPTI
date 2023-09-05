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
import pyqtgraph as pg
from pyqtgraph import dockarea


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


@dataclass
class Docks:
    home: pg.dockarea.Dock
    dc_signals: pg.dockarea.Dock
    amplitudes: pg.dockarea.Dock


class MainWindow(QtWidgets.QMainWindow):
    HORIZONTAL_SIZE = 1200
    VERTICAL_SIZE = 1000

    def __init__(self, controllers: controller.interface.Controllers):
        QtWidgets.QMainWindow.__init__(self)
        self.setWindowTitle("MiniPTI")
        self.setWindowIcon(QtGui.QIcon("minipti/gui/images/logo.png"))
        self.controllers = controllers
        self.dock_area = pg.dockarea.DockArea()
        self.docks = [pg.dockarea.Dock(name="Home", widget=Home(self.controllers.home)),
                      pg.dockarea.Dock(name="Probe Laser", widget=self._init_probe_laser()),
                      pg.dockarea.Dock(name="Pump Laser", widget=self._init_pump_laser()),
                      pg.dockarea.Dock(name="DC Signals", widget=plots.DC().window),
                      pg.dockarea.Dock(name="Amplitudes", widget=plots.Amplitudes().window),
                      pg.dockarea.Dock(name="Output Phases", widget=plots.OutputPhases().window),
                      pg.dockarea.Dock(name="Interferometric Phase", widget=plots.InterferometricPhase().window),
                      pg.dockarea.Dock(name="Sensitivity", widget=plots.Sensitivity().window),
                      pg.dockarea.Dock(name="PTI Signal", widget=plots.PTISignal().window)]
        for dock in self.docks:
            self.dock_area.addDock(dock)
        for i in range(len(self.docks) - 1, 0, -1):
            self.dock_area.moveDock(self.docks[i - 1], "above", self.docks[i])
        self.setCentralWidget(self.dock_area)
        self.logging_window = QtWidgets.QLabel()
        self.log = QtWidgets.QDockWidget("Log")
        self.scroll = QtWidgets.QScrollArea(widgetResizable=True)
        self.battery = QtWidgets.QDockWidget("Battery")
        self.charge_level = QtWidgets.QLabel("NaN % left")
        self.minutes_left = QtWidgets.QLabel("NaN Minutes left")
        self._init_dock_widgets()
        self.resize(MainWindow.HORIZONTAL_SIZE, MainWindow.VERTICAL_SIZE)
        self.setWindowIcon(QtGui.QIcon("minipti/gui/images/logo.png"))
        self.show()

    def logging_update(self, log_queue: collections.deque) -> None:
        self.logging_window.setText("".join(log_queue))

    @QtCore.pyqtSlot(model.Battery)
    def update_battery_state(self, battery: model.Battery) -> None:
        self.minutes_left.setText(f"Minutes left: {battery.minutes_left}")
        self.charge_level.setText(f"{battery.percentage} % left")

    def _init_tec(self, laser: int) -> QtWidgets.QWidget:
        tec_ch = QtWidgets.QWidget()
        tec_ch.setLayout(QtWidgets.QHBoxLayout())
        tec_ch.layout().addWidget(hardware.Tec(self.controllers.tec[laser], laser))
        tec_ch.layout().addWidget(plots.TecTemperature(laser).window)
        return tec_ch

    def _init_probe_laser(self) -> pg.dockarea.DockArea:
        probe_laser = QtWidgets.QWidget()
        probe_laser.setLayout(QtWidgets.QHBoxLayout())
        probe_laser.layout().addWidget(hardware.ProbeLaser(self.controllers.probe_laser))
        probe_laser.layout().addWidget(plots.ProbeLaserCurrent().window)
        dock_area = pg.dockarea.DockArea()
        tec = self._init_tec(model.Tec.PROBE_LASER)
        laser_dock = pg.dockarea.Dock(name="Laser Driver", widget=probe_laser)
        tec_dock = pg.dockarea.Dock(name="TEC Driver", widget=tec)
        dock_area.addDock(laser_dock)
        dock_area.addDock(tec_dock)
        dock_area.moveDock(laser_dock, "above", tec_dock)
        return dock_area

    def _init_pump_laser(self) -> pg.dockarea.DockArea:
        pump_laser = QtWidgets.QWidget()
        pump_laser.setLayout(QtWidgets.QHBoxLayout())
        pump_laser.layout().addWidget(hardware.PumpLaser(self.controllers.pump_laser))
        pump_laser.layout().addWidget(plots.PumpLaserCurrent().window)
        dock_area = pg.dockarea.DockArea()
        tec = self._init_tec(model.Tec.PUMP_LASER)
        laser_dock = pg.dockarea.Dock(name="Laser Driver", widget=pump_laser)
        tec_dock = pg.dockarea.Dock(name="TEC Driver", widget=tec)
        dock_area.addDock(laser_dock)
        dock_area.addDock(tec_dock)
        dock_area.moveDock(laser_dock, "above", tec_dock)
        return dock_area

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

    def closeEvent(self, close_event):
        close = QtWidgets.QMessageBox.question(self, "QUIT", "Are you sure you want to close?",
                                               QtWidgets.QMessageBox.StandardButton.Yes |
                                               QtWidgets.QMessageBox.StandardButton.No)
        if close == QtWidgets.QMessageBox.StandardButton.Yes:
            close_event.accept()
            self.controllers.main_application.close()
        else:
            close_event.ignore()


@dataclass
class HomeButtons:
    run_measurement: Union[QtWidgets.QPushButton, None] = None
    settings: Union[QtWidgets.QPushButton, None] = None
    utilities: Union[QtWidgets.QPushButton, None] = None


class Home(QtWidgets.QTabWidget):
    def __init__(self, home_controller: controller.interface.Home):
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
        self.buttons.run_measurement = helper.create_button(parent=sub_layout, title="Run Measurement", only_icon=True,
                                                            slot=self.controller.enable_motherboard)
        self.buttons.run_measurement.setIcon(QtGui.QIcon("minipti/gui/images/run.svg"))
        self.buttons.run_measurement.setIconSize(QtCore.QSize(40, 40))

        self.buttons.settings = helper.create_button(parent=sub_layout, title="Settings", only_icon=True,
                                                     slot=self.controller.show_settings)
        self.buttons.utilities = helper.create_button(parent=sub_layout, title="Utilities", only_icon=True,
                                                      slot=self.controller.show_utilities)

        self.buttons.settings.setIcon(QtGui.QIcon("minipti/gui/images/settings.svg"))
        self.buttons.settings.setIconSize(QtCore.QSize(40, 40))
        self.buttons.settings.setToolTip("Settings")
        self.buttons.utilities.setIcon(QtGui.QIcon("minipti/gui/images/calculation.svg"))
        self.buttons.utilities.setIconSize(QtCore.QSize(40, 40))
        self.buttons.utilities.setToolTip("Utilities")
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
