import collections
from dataclasses import dataclass
from typing import NamedTuple

import pyqtgraph as pg
from PyQt5 import QtWidgets, QtGui
from pyqtgraph import dockarea

import minipti
from minipti.gui import controller
from minipti.gui import model
from minipti.gui.view import hardware
from minipti.gui.view import home
from minipti.gui.view import plots


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
        self.setWindowIcon(QtGui.QIcon(f"{minipti.module_path}/gui/images/logo.png"))
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
                           [plots.TecTemperature(model.serial_devices.Tec.PUMP_LASER),
                            plots.TecTemperature(model.serial_devices.Tec.PROBE_LASER)])
        self.home = home.MainWindow(self.controllers.home)
        self.docks = []
        if model.configuration.GUI.home.use:
            self.docks.append(pg.dockarea.Dock(name="Home", widget=self.home))
        if model.configuration.GUI.pump_laser.use:
            self.docks.append(pg.dockarea.Dock(name="Pump Laser", widget=self._init_pump_laser()))
        if model.configuration.GUI.probe_laser.use:
            self.docks.append(pg.dockarea.Dock(name="Probe Laser", widget=self._init_probe_laser()))
        if model.configuration.GUI.plots.dc_signals.use:
            self.docks.append(pg.dockarea.Dock(name="DC Signals", widget=self.plots.dc.window))
        if model.configuration.GUI.plots.amplitudes.use:
            self.docks.append(pg.dockarea.Dock(name="Amplitudes", widget=self.plots.amplitudes.window))
        if model.configuration.GUI.plots.output_phases.use:
            self.docks.append(pg.dockarea.Dock(name="Output Phases", widget=self.plots.output_phases.window))
        if model.configuration.GUI.plots.interferometric_phase.use:
            self.docks.append(pg.dockarea.Dock(name="Interferometric Phase",
                                               widget=self.plots.interferometric_phase.window))
        if model.configuration.GUI.plots.sensitivity.use:
            self.docks.append(pg.dockarea.Dock(name="Sensitivity", widget=self.plots.sensitivity.window))
        if model.configuration.GUI.plots.pti_signal.use:
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
        self.log = dockarea.Dock("Log", size=(600, 1))
        self.scroll = QtWidgets.QScrollArea(widgetResizable=True)
        self.charge_level = QtWidgets.QProgressBar()
        self.charge_level.resize(1, 1)
        self._init_dock_widgets()
        self.resize(MainWindow.HORIZONTAL_SIZE, MainWindow.VERTICAL_SIZE)
        self.setWindowIcon(QtGui.QIcon(f"{minipti.module_path}/gui/images/logo.png"))
        self.setWindowTitle(model.configuration.GUI.window_title)
        self.show()

    def logging_update(self, log_queue: collections.deque) -> None:
        self.logging_window.setText("".join(log_queue))

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
        tec = self._init_tec(model.serial_devices.Tec.PROBE_LASER)
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
        tec = self._init_tec(model.serial_devices.Tec.PUMP_LASER)
        laser_dock = pg.dockarea.Dock(name="Laser Driver", widget=pump_laser)
        tec_dock = pg.dockarea.Dock(name="TEC Driver", widget=tec)
        dock_area.addDock(laser_dock)
        dock_area.addDock(tec_dock)
        dock_area.moveDock(laser_dock, "above", tec_dock)
        return dock_area

    def _init_dock_widgets(self) -> None:
        model.signals.GENERAL_PURPORSE.logging_update.connect(self.logging_update)
        self.scroll.setWidgetResizable(True)
        self.log.addWidget(self.scroll)
        sub_layout = QtWidgets.QWidget()
        sub_layout.setLayout(QtWidgets.QVBoxLayout())
        sub_layout.layout().addWidget(self.charge_level)
        sub_layout.resize(1, 1)
        if model.configuration.GUI.logging.console:
            self.dock_area.addDock(self.log, "bottom")
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
