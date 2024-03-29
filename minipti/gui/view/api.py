import collections
from typing import NamedTuple

import pyqtgraph as pg
from PyQt5 import QtWidgets, QtGui, QtCore
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QApplication
from overrides import override

import minipti
from minipti.gui import controller
from minipti.gui import model
from minipti.gui.view import hardware
from minipti.gui.view import plots
from minipti.gui.view import general_purpose


class Plots(NamedTuple):
    measurement: plots.Measurement
    interferometrie: plots.Interferometrie
    characterisation: plots.Characterisation
    probe_laser: plots.ProbeLaserCurrent
    pump_laser: plots.PumpLaserCurrent
    tec: list[plots.TecTemperature]


class _FullSizeTab(QtWidgets.QTabWidget):
    def __init__(self, *args, **kwargs):
        QtWidgets.QTabWidget.__init__(self, *args, **kwargs)

    @override
    def resizeEvent(self, event):
        self.tabBar().setFixedWidth(self.width())
        super().resizeEvent(event)


class MainWindow(QtWidgets.QMainWindow):
    HORIZONTAL_SIZE = 1200
    VERTICAL_SIZE = 1000

    def __init__(self, controllers: controller.interface.Controllers):
        QtWidgets.QMainWindow.__init__(self)
        self.setWindowIcon(QtGui.QIcon(f"{minipti.MODULE_PATH}/gui/images/logo.png"))
        self.controllers = controllers
        self.toolbar = general_purpose.ToolBar(self.controllers.toolbar)
        self.addToolBar(QtCore.Qt.LeftToolBarArea, self.toolbar)
        self.setStatusBar(self.controllers.statusbar.view)
        self.tabbar = _FullSizeTab(movable=True)
        self.plots = Plots(plots.Measurement(), plots.Interferometrie(), plots.Characterisation(),
                           plots.ProbeLaserCurrent(),
                           plots.PumpLaserCurrent(),
                           [plots.TecTemperature(model.serial_devices.Tec.PUMP_LASER),
                            plots.TecTemperature(model.serial_devices.Tec.PROBE_LASER)])
        if model.configuration.GUI.plots.measurement.use:
            self.tabbar.addTab(self.plots.measurement, "Measurement")
        if model.configuration.GUI.plots.interferometry.use:
            self.tabbar.addTab(self.plots.interferometrie, "Interferometry")
        if model.configuration.GUI.plots.characterisation.use:
            self.tabbar.addTab(self.plots.characterisation, "Characterization")
        if model.configuration.GUI.pump_laser.use:
            pump_laser = self._init_laser_tab(hardware.PumpLaser(self.controllers.pump_laser),
                                              self.plots.pump_laser.window, model.serial_devices.Tec.PUMP_LASER)
            self.tabbar.addTab(pump_laser, "Pump Laser")
        if model.configuration.GUI.probe_laser.use:
            probe_laser = self._init_laser_tab(hardware.ProbeLaser(self.controllers.probe_laser),
                                               self.plots.probe_laser.window, model.serial_devices.Tec.PROBE_LASER)
            self.tabbar.addTab(probe_laser, "Probe Laser")
        self.logging_window = QtWidgets.QLabel()
        self.log = QtWidgets.QDockWidget("Log")
        self.scroll = QtWidgets.QScrollArea(widgetResizable=True)
        self._init_dock_widgets()
        self.resize(MainWindow.HORIZONTAL_SIZE, MainWindow.VERTICAL_SIZE)
        self.setWindowIcon(QtGui.QIcon(f"{minipti.MODULE_PATH}/gui/images/logo.png"))
        self.setWindowTitle(model.configuration.GUI.window_title)
        self.full_screen = False
        self.tabbar.tabBar().setExpanding(True)
        self.setCentralWidget(self.tabbar)
        self.progress_bar = QtWidgets.QProgressBar()
        model.signals.GENERAL_PURPORSE.progess_bar.connect(self.update_progess_bar)
        model.signals.GENERAL_PURPORSE.progess_bar_start.connect(self.start_progess_bar)
        model.signals.GENERAL_PURPORSE.progess_bar_stop.connect(self.stop_progess_bar)
        self.show()

    def start_progess_bar(self) -> None:
        self.progress_bar.show()

    def stop_progess_bar(self) -> None:
        self.progress_bar.close()

    def update_progess_bar(self, progress: int) -> None:
        self.progress_bar.setValue(progress)

    def keyPressEvent(self, e):
        if e.key() == Qt.Key_F1:
            self.controllers.toolbar.show_settings()
        elif e.key() == Qt.Key_F2:
            self.controllers.toolbar.show_utilities()
        elif e.key() == Qt.Key_F11:
            if self.full_screen:
                self.showNormal()
                self.full_screen = False
            else:
                self.showFullScreen()
                self.full_screen = True
        elif e.key() == Qt.Key_Escape:
            self.controllers.main_application.emergency_stop()
        elif e.key() == Qt.Key_Space:
            self.controllers.toolbar.on_run()

    def logging_update(self, log_queue: collections.deque) -> None:
        self.logging_window.setText("".join(log_queue))

    def _init_tec(self, laser: int) -> QtWidgets.QWidget:
        tec_ch = QtWidgets.QWidget()
        tec_ch.setLayout(QtWidgets.QHBoxLayout())
        tec_ch.layout().addWidget(hardware.Tec(self.controllers.tec[laser], laser))
        tec_ch.layout().addWidget(self.plots.tec[laser].window)
        return tec_ch

    def _init_laser_tab(self, laser_widget: QtWidgets.QWidget, laser_plot: pg.GraphicsWidget,
                        channel: int) -> QtWidgets.QTabWidget:
        laser = QtWidgets.QWidget()
        laser.setLayout(QtWidgets.QHBoxLayout())
        laser.layout().addWidget(laser_widget)
        laser.layout().addWidget(laser_plot)
        tabbar = _FullSizeTab(movable=True)
        tec = self._init_tec(channel)
        tabbar.addTab(laser, "Laser Driver")
        tabbar.addTab(tec, "TEC Driver")
        return tabbar

    def _init_dock_widgets(self) -> None:
        model.signals.GENERAL_PURPORSE.logging_update.connect(self.logging_update)
        self.scroll.setWidgetResizable(True)
        self.log.setWidget(self.scroll)
        self.scroll.setWidget(self.logging_window)
        if model.configuration.GUI.logging.console:
            self.addDockWidget(Qt.BottomDockWidgetArea, self.log)

    def closeEvent(self, close_event):
        close = QtWidgets.QMessageBox.question(self, "QUIT", "Are you sure you want to close?",
                                               QtWidgets.QMessageBox.StandardButton.Yes |
                                               QtWidgets.QMessageBox.StandardButton.No)
        if close == QtWidgets.QMessageBox.StandardButton.Yes:
            close_event.accept()
            self.controllers.main_application.close()
            QApplication.closeAllWindows()
        else:
            close_event.ignore()
