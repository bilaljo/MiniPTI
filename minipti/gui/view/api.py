import collections
import logging
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


@dataclass
class Docks:
    home: pg.dockarea.Dock
    dc_signals: pg.dockarea.Dock
    amplitudes: pg.dockarea.Dock


class Plots(NamedTuple):
    dc: plots.DC
    interferometric_phase: plots.InterferometricPhase
    probe_laser: plots.ProbeLaserCurrent
    pump_laser: plots.PumpLaserCurrent
    amplitudes: plots.Amplitudes
    output_phases: plots.OutputPhases
    sensitivity: plots.Sensitivity
    pti_signal: plots.PTISignal
    tec: list[plots.TecTemperature]


class MainWindow(QtWidgets.QMainWindow):
    HORIZONTAL_SIZE = 1200
    VERTICAL_SIZE = 1000

    def __init__(self, controllers: controller.interface.Controllers):
        QtWidgets.QMainWindow.__init__(self)
        self.setWindowTitle("MiniPTI")
        self.setWindowIcon(QtGui.QIcon("minipti/gui/images/logo.png"))
        self.controllers = controllers
        self.dock_area = pg.dockarea.DockArea()
        self.plots = Plots(plots.DC(),
                           plots.InterferometricPhase(),
                           plots.ProbeLaserCurrent(),
                           plots.PumpLaserCurrent(),
                           plots.Amplitudes(),
                           plots.OutputPhases(),
                           plots.Sensitivity(),
                           plots.PTISignal(),
                           [plots.TecTemperature(model.Tec.PUMP_LASER),
                            plots.TecTemperature(model.Tec.PROBE_LASER)])
        self.home = Home(self.controllers.home)
        self.docks = []
        if self.controllers.configuration.home.use:
            self.docks.append(pg.dockarea.Dock(name="Home", widget=self.home))
        if self.controllers.configuration.pump_laser.use:
            self.docks.append(pg.dockarea.Dock(name="Pump Laser", widget=self._init_pump_laser()))
        if self.controllers.configuration.probe_laser.use:
            self.docks.append(pg.dockarea.Dock(name="Probe Laser", widget=self._init_probe_laser()))
        if self.controllers.configuration.plots.dc_signals.use:
            self.docks.append(pg.dockarea.Dock(name="DC Signals", widget=self.plots.dc.window))
        if self.controllers.configuration.plots.amplitudes.use:
            self.docks.append(pg.dockarea.Dock(name="Amplitudes", widget=self.plots.amplitudes.window))
        if self.controllers.configuration.plots.output_phases.use:
            self.docks.append(pg.dockarea.Dock(name="Output Phases", widget=self.plots.output_phases.window))
        if self.controllers.configuration.plots.interferometric_phase.use:
            self.docks.append(pg.dockarea.Dock(name="Interferometric Phase",
                                               widget=self.plots.interferometric_phase.window))
        if self.controllers.configuration.plots.sensitivity.use:
            self.docks.append(pg.dockarea.Dock(name="Sensitivity", widget=self.plots.sensitivity.window))
        if self.controllers.configuration.plots.pti_signal.use:
            self.docks.append(pg.dockarea.Dock(name="PTI Signal", widget=self.plots.pti_signal.window))
        for dock in self.docks:
            self.dock_area.addDock(dock)
        if len(self.docks) == 1:
            self.setWindowTitle(self.docks[0].title())
            self.docks[0].setTitle("")
        else:
            for i in range(len(self.docks) - 1, 0, -1):
                self.dock_area.moveDock(self.docks[i - 1], "above", self.docks[i])
        self.setCentralWidget(self.dock_area)
        self.logging_window = QtWidgets.QLabel()
        self.log = dockarea.Dock("Log", size=(500, 1))
        self.scroll = QtWidgets.QScrollArea(widgetResizable=True)
        self.battery = dockarea.Dock("Battery", size=(1, 1))
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
        tec_ch.layout().addWidget(self.plots.tec[laser].window)
        return tec_ch

    def _init_probe_laser(self) -> pg.dockarea.DockArea:
        probe_laser = QtWidgets.QWidget()
        probe_laser.setLayout(QtWidgets.QHBoxLayout())
        probe_laser.layout().addWidget(hardware.ProbeLaser(self.controllers.probe_laser))
        probe_laser.layout().addWidget(self.plots.probe_laser.window)
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
        pump_laser.layout().addWidget(self.plots.pump_laser.window)
        dock_area = pg.dockarea.DockArea()
        tec = self._init_tec(model.Tec.PUMP_LASER)
        laser_dock = pg.dockarea.Dock(name="Laser Driver", widget=pump_laser)
        tec_dock = pg.dockarea.Dock(name="TEC Driver", widget=tec)
        dock_area.addDock(laser_dock)
        dock_area.addDock(tec_dock)
        dock_area.moveDock(laser_dock, "above", tec_dock)
        return dock_area

    def _init_dock_widgets(self) -> None:
        model.signals.battery_state.connect(self.update_battery_state)
        model.signals.logging_update.connect(self.logging_update)
        self.scroll.setWidgetResizable(True)
        self.log.addWidget(self.scroll)
        sub_layout = QtWidgets.QWidget()
        sub_layout.setMaximumWidth(150)
        sub_layout.setLayout(QtWidgets.QVBoxLayout())
        sub_layout.layout().addWidget(self.charge_level)
        # sub_layout.layout().addWidget(self.minutes_left)
        self.battery.addWidget(sub_layout)
        if self.controllers.configuration.logging.console:
            self.dock_area.addDock(self.log, "bottom")
            self.scroll.setWidget(self.logging_window)
        if self.controllers.configuration.battery.use:
            self.dock_area.addDock(self.battery, "bottom")
            self.dock_area.moveDock(self.log, "left", self.battery)
        #self.layout().addWidget(dock_area)

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
        self.buttons = HomeButtons()
        self._init_buttons()
        self._init_signals()
        self.pti_signal = plots.PTISignal()
        self.dc = plots.DC()
        self.interferometric_phase = plots.InterferometricPhase()
        sublayout = QtWidgets.QWidget()
        sublayout.setLayout(QtWidgets.QHBoxLayout())
        if self.controller.configuration.plots.dc_signals:
            sublayout.layout().addWidget(self.dc.window)
        if self.controller.configuration.plots.interferometric_phase:
            sublayout.layout().addWidget(self.interferometric_phase.window)
        if self.controller.configuration.plots.pti_signal:
            sublayout.layout().addWidget(self.pti_signal.window)
        self.layout().addWidget(sublayout, 0, 0)

    def _init_buttons(self) -> None:
        sub_layout = QtWidgets.QWidget()
        sub_layout.setLayout(QtWidgets.QHBoxLayout())

        button_layout = QtWidgets.QWidget()
        button_layout.setLayout(QtWidgets.QVBoxLayout())
        self.buttons.run_measurement = helper.create_button(parent=button_layout, title="Run Measurement",
                                                            only_icon=True, slot=self.controller.enable_motherboard)
        self.buttons.run_measurement.setIcon(QtGui.QIcon("minipti/gui/images/run.svg"))
        self.buttons.run_measurement.setIconSize(QtCore.QSize(40, 40))
        label = QtWidgets.QLabel("Run")
        label.setAlignment(Qt.AlignHCenter)
        button_layout.layout().addWidget(label)
        sub_layout.layout().addWidget(button_layout)

        button_layout = QtWidgets.QWidget()
        button_layout.setLayout(QtWidgets.QVBoxLayout())
        self.buttons.settings = helper.create_button(parent=button_layout, title="Settings", only_icon=True,
                                                     slot=self.controller.show_settings)
        self.buttons.settings.setIcon(QtGui.QIcon("minipti/gui/images/settings.svg"))
        self.buttons.settings.setIconSize(QtCore.QSize(40, 40))
        self.buttons.settings.setToolTip("Settings")
        label = QtWidgets.QLabel("Settings")
        label.setAlignment(Qt.AlignHCenter)
        button_layout.layout().addWidget(label)
        sub_layout.layout().setAlignment(Qt.AlignHCenter)
        sub_layout.layout().addWidget(button_layout)

        if self.controller.configuration.use_utilities:
            button_layout = QtWidgets.QWidget()
            button_layout.setLayout(QtWidgets.QVBoxLayout())
            self.buttons.utilities = helper.create_button(parent=button_layout, title="Utilities", only_icon=True,
                                                          slot=self.controller.show_utilities)
            self.buttons.utilities.setIcon(QtGui.QIcon("minipti/gui/images/calculation.svg"))
            self.buttons.utilities.setIconSize(QtCore.QSize(40, 40))
            self.buttons.utilities.setToolTip("Utilities")
            button_layout.layout().addWidget(self.buttons.utilities)
            label = QtWidgets.QLabel("Utilities")
            label.setAlignment(Qt.AlignHCenter)
            button_layout.layout().addWidget(label)
            button_layout.layout().setAlignment(Qt.AlignHCenter)
            sub_layout.layout().addWidget(button_layout)
        self.layout().addWidget(sub_layout, 1, 0)
        # self.create_button(master=sub_layout, title="Clean Air", slot=self.controller.update_bypass)

    @QtCore.pyqtSlot(bool)
    def update_run_measurement(self, state: bool) -> None:
        helper.toggle_button(state, self.buttons.run_measurement)

    # @QtCore.pyqtSlot(bool)
    # def update_clean_air(self, state: bool) -> None:
    #    helper.toggle_button(state, self.buttons["Clean Air"])

    def _init_signals(self) -> None:
        model.daq_signals.running.connect(self.update_run_measurement)
