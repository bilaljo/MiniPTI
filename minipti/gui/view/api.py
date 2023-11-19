import collections
from typing import NamedTuple

import pyqtgraph as pg
from PyQt5 import QtWidgets, QtGui, QtCore
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QApplication
from pyqtgraph import dockarea

import minipti
from minipti.gui import controller
from minipti.gui import model
from minipti.gui.view import hardware
from minipti.gui.view import plots
from minipti.gui.view import general_purpose


class Plots(NamedTuple):
    probe_laser: plots.ProbeLaserCurrent
    pump_laser: plots.PumpLaserCurrent
    tec: list[plots.TecTemperature]


class MainWindow(QtWidgets.QMainWindow):
    HORIZONTAL_SIZE = 1200
    VERTICAL_SIZE = 1000

    def __init__(self, controllers: controller.interface.Controllers):
        QtWidgets.QMainWindow.__init__(self)
        self.setWindowIcon(QtGui.QIcon(f"{minipti.module_path}/gui/images/logo.png"))
        self.controllers = controllers
        self.toolbar = general_purpose.ToolBar(self.controllers.toolbar)
        self.addToolBar(QtCore.Qt.LeftToolBarArea, self.toolbar)
        self.setStatusBar(self.controllers.statusbar.view)
        self.dock_area = pg.dockarea.DockArea()
        self.plots = Plots(plots.ProbeLaserCurrent(),
                           plots.PumpLaserCurrent(),
                           [plots.TecTemperature(model.serial_devices.Tec.PUMP_LASER),
                            plots.TecTemperature(model.serial_devices.Tec.PROBE_LASER)])
        self.docks = []
        if model.configuration.GUI.plots.measurement.use:
            self.docks.append(pg.dockarea.Dock(name="Measurement", widget=plots.Measurement()))
        if model.configuration.GUI.plots.interferometry.use:
            self.docks.append(pg.dockarea.Dock(name="Interferometry", widget=plots.Interferometrie()))
        if model.configuration.GUI.plots.characterisation.use:
            self.docks.append(pg.dockarea.Dock(name="Characterisation", widget=plots.Characterisation()))
        if model.configuration.GUI.pump_laser.use:
            pump_laser = self._init_laser_tab(hardware.PumpLaser(self.controllers.pump_laser),
                                              self.plots.pump_laser.window, model.serial_devices.Tec.PUMP_LASER)
            self.docks.append(pg.dockarea.Dock(name="Pump Laser", widget=pump_laser))
        if model.configuration.GUI.probe_laser.use:
            probe_laser = self._init_laser_tab(hardware.ProbeLaser(self.controllers.probe_laser),
                                               self.plots.probe_laser.window, model.serial_devices.Tec.PROBE_LASER)
            self.docks.append(pg.dockarea.Dock(name="Probe Laser", widget=probe_laser))
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
        self._init_dock_widgets()
        self.resize(MainWindow.HORIZONTAL_SIZE, MainWindow.VERTICAL_SIZE)
        self.setWindowIcon(QtGui.QIcon(f"{minipti.module_path}/gui/images/logo.png"))
        self.setWindowTitle(model.configuration.GUI.window_title)
        self.full_screen = False
        self.show()

    def keyPressEvent(self, e):
        if e.key() == Qt.Key_F11:
            if self.full_screen:
                self.showNormal()
                self.full_screen = False
            else:
                self.showFullScreen()
                self.full_screen = True
        if e.key == Qt.Key_Escape:
            # Implement me
            ...

    def logging_update(self, log_queue: collections.deque) -> None:
        self.logging_window.setText("".join(log_queue))

    def _init_tec(self, laser: int) -> QtWidgets.QWidget:
        tec_ch = QtWidgets.QWidget()
        tec_ch.setLayout(QtWidgets.QHBoxLayout())
        tec_ch.layout().addWidget(hardware.Tec(self.controllers.tec[laser], laser))
        tec_ch.layout().addWidget(self.plots.tec[laser].window)
        return tec_ch

    def _init_laser_tab(self, laser_widget: QtWidgets.QWidget, laser_plot: pg.GraphicsWidget,
                        channel: int) -> pg.dockarea.DockArea:
        laser = QtWidgets.QWidget()
        laser.setLayout(QtWidgets.QHBoxLayout())
        laser.layout().addWidget(laser_widget)
        laser.layout().addWidget(laser_plot)
        dock_area = pg.dockarea.DockArea()
        tec = self._init_tec(channel)
        laser_dock = pg.dockarea.Dock(name="Laser Driver", widget=laser)
        tec_dock = pg.dockarea.Dock(name="TEC Driver", widget=tec)
        dock_area.addDock(laser_dock)
        dock_area.addDock(tec_dock)
        dock_area.moveDock(laser_dock, "above", tec_dock)
        return dock_area

    def _init_dock_widgets(self) -> None:
        model.signals.GENERAL_PURPORSE.logging_update.connect(self.logging_update)
        self.scroll.setWidgetResizable(True)
        self.log.addWidget(self.scroll)
        if model.configuration.GUI.logging.console:
            self.dock_area.addDock(self.log, "bottom")
            self.scroll.setWidget(self.logging_window)

    def closeEvent(self, close_event):
        close = QtWidgets.QMessageBox.question(self, "QUIT", "Are you sure you want to close?",
                                               QtWidgets.QMessageBox.StandardButton.Yes |
                                               QtWidgets.QMessageBox.StandardButton.No)
        if close == QtWidgets.QMessageBox.StandardButton.Yes:
            close_event.accept()
            QApplication.closeAllWindows()
        else:
            close_event.ignore()
