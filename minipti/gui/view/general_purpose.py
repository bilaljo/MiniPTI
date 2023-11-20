from dataclasses import dataclass

from PyQt5 import QtWidgets, QtGui, QtCore

import minipti
from minipti.gui import model, controller
from minipti.gui.view import helper


@dataclass
class Actions:
    run: QtWidgets.QAction
    settings: QtWidgets.QAction
    utilities: QtWidgets.QAction
    valve: QtWidgets.QAction
    connect: QtWidgets.QAction
    directory: QtWidgets.QAction
    shutdown: QtWidgets.QAction


class ToolBar(QtWidgets.QToolBar):
    def __init__(self, toolbar_controller: controller.interface.Toolbar):
        QtWidgets.QToolBar.__init__(self)
        self.controller = toolbar_controller
        self.run = QtWidgets.QAction()
        base_path = f"{minipti.module_path}/gui/images"
        self.actions = Actions(QtWidgets.QAction("Run"), QtWidgets.QAction("Settings"), QtWidgets.QAction("Utilities"),
                               QtWidgets.QAction("Valve"), QtWidgets.QAction("Connect"), QtWidgets.QAction("Directory"),
                               QtWidgets.QAction("Shutdown"))
        self.actions.run.setIcon(QtGui.QIcon(f"{base_path}/Run.png"))
        self.actions.settings.setIcon(QtGui.QIcon(f"{base_path}/Settings.png"))
        self.actions.utilities.setIcon(QtGui.QIcon(f"{base_path}/Utilities.png"))
        self.actions.valve.setIcon(QtGui.QIcon(f"{base_path}/Valve.png"))
        self.actions.connect.setIcon(QtGui.QIcon(f"{base_path}/Connect.svg"))
        self.actions.directory.setIcon(QtGui.QIcon(f"{base_path}/Directory.svg"))
        self.actions.shutdown.setIcon(QtGui.QIcon(f"{base_path}/Shutdown.svg"))
        self.setIconSize(QtCore.QSize(30, 30))
        self.setStyleSheet("QToolBar{spacing:12px;}")
        self._init_actions()
        self._init_signals()

    def _init_actions(self) -> None:
        self.addAction(self.actions.run)
        self.actions.run.triggered.connect(self.controller.on_run)
        if model.configuration.GUI.utilities.use:
            self.addAction(self.actions.utilities)
            self.actions.utilities.triggered.connect(self.controller.show_utilities)
        if model.configuration.GUI.settings.use:
            self.addAction(self.actions.settings)
            self.actions.settings.triggered.connect(self.controller.show_settings)
        if model.configuration.GUI.valve.use:
            self.addAction(self.actions.valve)
            self.actions.valve.triggered.connect(self.controller.change_valve)
        if model.configuration.GUI.connect.use:
            self.addAction(self.actions.connect)
            self.actions.connect.triggered.connect(self.controller.init_devices)
        if model.configuration.GUI.destination_folder.use:
            self.addAction(self.actions.directory)
            self.actions.directory.triggered.connect(self.controller.update_destination_folder)
        if model.configuration.GUI.use_shutdown:
            self.addAction(self.actions.shutdown)
            self.actions.shutdown.triggered.connect(self.controller.shutdown)

    @QtCore.pyqtSlot(bool)
    def update_run_measurement(self, state: bool) -> None:
        if state:
            icon = QtGui.QIcon(f"{minipti.module_path}/gui/images/Stop.svg")
        else:
            icon = QtGui.QIcon(f"{minipti.module_path}/gui/images/Run.png")
        self.actions.run.setIcon(icon)

    @QtCore.pyqtSlot(bool)
    def update_clean_air(self, state: bool) -> None:
        icon = QtGui.QIcon(f"{minipti.module_path}/gui/images/Valve.png")
        self.actions.valve.setIcon(icon)

    def _init_signals(self) -> None:
        model.signals.DAQ.running.connect(self.update_run_measurement)
        model.signals.VALVE.bypass.connect(self.update_clean_air)


class BatteryWindow(QtWidgets.QMainWindow):
    def __init__(self):
        QtWidgets.QMainWindow.__init__(self)
        self.setWindowTitle("BMS")
        self.base_layout = QtWidgets.QWidget()
        self.base_layout.setLayout(QtWidgets.QGridLayout())
        self.current_value = QtWidgets.QLabel("NaN")
        self.base_layout.layout().addWidget(QtWidgets.QLabel("Current [mA]:"), 0, 0, QtCore.Qt.AlignCenter)
        self.base_layout.layout().addWidget(self.current_value, 0, 1, QtCore.Qt.AlignCenter)
        self.voltage_value = QtWidgets.QLabel("NaN")
        self.base_layout.layout().addWidget(QtWidgets.QLabel("Voltage [V]:"), 0, 2, QtCore.Qt.AlignCenter)
        self.base_layout.layout().addWidget(self.voltage_value, 0, 3, QtCore.Qt.AlignCenter)
        self.temperature_value = QtWidgets.QLabel("NaN")
        self.base_layout.layout().addWidget(QtWidgets.QLabel("Temperature [°C]:"), 0, 4, QtCore.Qt.AlignCenter)
        self.base_layout.layout().addWidget(self.temperature_value, 0, 5, QtCore.Qt.AlignCenter)
        self.minutes_value = QtWidgets.QLabel("NaN")
        self.base_layout.layout().addWidget(QtWidgets.QLabel("Minutes left:"), 1, 0, QtCore.Qt.AlignCenter)
        self.base_layout.layout().addWidget(self.minutes_value, 1, 1, QtCore.Qt.AlignCenter)
        self.minutes_value = QtWidgets.QLabel("NaN")
        self.base_layout.layout().addWidget(QtWidgets.QLabel("Minutes left:"), 1, 0, QtCore.Qt.AlignCenter)
        self.base_layout.layout().addWidget(self.minutes_value, 1, 1, QtCore.Qt.AlignCenter)
        self.battery_percentage_value = QtWidgets.QLabel("NaN")
        self.base_layout.layout().addWidget(QtWidgets.QLabel("Percentage [%]:"), 1, 2, QtCore.Qt.AlignCenter)
        self.base_layout.layout().addWidget(self.battery_percentage_value, 1, 3, QtCore.Qt.AlignCenter)
        self.remaining_capacity_value = QtWidgets.QLabel("NaN")
        self.base_layout.layout().addWidget(QtWidgets.QLabel("Remaining Charged Capacity [%]:"), 1, 4, QtCore.Qt.AlignCenter)
        self.base_layout.layout().addWidget(self.remaining_capacity_value, 1, 5, QtCore.Qt.AlignCenter)
        self.setCentralWidget(self.base_layout)
        self.setWindowIcon(QtGui.QIcon(f"{minipti.module_path}/gui/images/battery/100_percent.svg"))
        model.signals.BMS.battery_data.connect(self.update_bms_data)

    @QtCore.pyqtSlot(float, float, float, float, float, float)
    def update_bms_data(self, current: float, voltage: float, temperature: float,
                        minutes_left: float, percentage: float, remaining_capacity: float) -> None:
        self.current_value.setText(str(round(current, 2)))
        self.voltage_value.setText(str(round(voltage, 2)))
        self.temperature_value.setText(str(round(temperature, 2)))
        self.minutes_value.setText(str(round(minutes_left, 2)))
        self.battery_percentage_value.setText(str(round(percentage, 2)))
        self.remaining_capacity_value.setText(str(round(remaining_capacity, 2)))


class StatusBar(QtWidgets.QStatusBar):
    BATTERY_THREE_QUARATERS_FULL = 75
    BATTERY_HALF_FULL = 50
    BATTERY_QUARTER_FULL = 25

    def __init__(self, bms_controller: controller.interface.Statusbar):
        QtWidgets.QStatusBar.__init__(self)
        self.controller = bms_controller
        self.setLayout(QtWidgets.QHBoxLayout())
        self.base_path = f"{minipti.module_path}/gui/images/battery"
        self.bypass = QtWidgets.QLabel("Bypass")
        self.addPermanentWidget(self.bypass)
        if model.configuration.GUI.battery.use:
            self.charging_indicator = QtWidgets.QToolButton()
            self.charging_indicator.clicked.connect(self.controller.show_bms)
            self.charging_indicator.setToolTip("100 %")
            self.charging_indicator.setIcon(QtGui.QIcon(f"{self.base_path}/100_percent.svg"))
            self.charging_indicator.setIconSize(QtCore.QSize(30, 40))
            self.addPermanentWidget(self.charging_indicator)
            model.signals.BMS.battery_state.connect(self.update_battery_state)
        model.signals.GENERAL_PURPORSE.destination_folder_changed.connect(self.update_destination_folder)
        model.signals.VALVE.bypass.connect(self.update_valve_state)

    def update_destination_folder(self, folder: str) -> None:
        self.controller.update_destination_folder(folder)

    def _set_battery_icon(self, percentage: float, charing: bool):
        suffix = "_charging.png" if charing else ".svg"
        if percentage > StatusBar.BATTERY_THREE_QUARATERS_FULL:
            self.charging_indicator.setIcon(QtGui.QIcon(f"{self.base_path}/100_percent{suffix}"))
        elif percentage > StatusBar.BATTERY_HALF_FULL:
            self.charging_indicator.setIcon(QtGui.QIcon(f"{self.base_path}/75_percent{suffix}"))
        elif percentage > StatusBar.BATTERY_QUARTER_FULL:
            self.charging_indicator.setIcon(QtGui.QIcon(f"{self.base_path}/50_percent{suffix}"))
        else:
            self.charging_indicator.setIcon(QtGui.QIcon(f"{self.base_path}/25_percent{suffix}"))

    @QtCore.pyqtSlot(bool)
    def update_valve_state(self, bypass: bool):
        if bypass:
            self.bypass.setStyleSheet("background-color : green")
        else:
            self.bypass.setStyleSheet("background-color : light gray")

    @QtCore.pyqtSlot(bool, float)
    def update_battery_state(self, charging: bool, percentage: int) -> None:
        self._set_battery_icon(percentage, charging)
        # We clip up every decimal place because so preciouse information about percentage is rather confusing
        if charging:
            self.charging_indicator.setToolTip(f"{int(percentage)} (charging)")
        else:
            self.charging_indicator.setToolTip(str(int(percentage)))
