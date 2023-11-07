from dataclasses import dataclass
from typing import Union, Callable

from PyQt5 import QtWidgets, QtCore, QtGui

import minipti
from minipti.gui import controller, model
from minipti.gui.view import plots, helper


@dataclass
class HomeButtons:
    run: Union[QtWidgets.QToolButton, None] = None
    valve: Union[QtWidgets.QToolButton, None] = None
    settings: Union[QtWidgets.QToolButton, None] = None
    utilities: Union[QtWidgets.QToolButton, None] = None
    connect: Union[QtWidgets.QToolButton, None] = None
    destination_folder: Union[QtWidgets.QToolButton, None] = None

    def __setitem__(self, name: str, value: QtWidgets.QToolButton) -> None:
        return self.__setattr__(HomeButtons._name_to_key(name), value)

    def __getitem__(self, name: str) -> QtWidgets.QToolButton:
        return self.__getattribute__(HomeButtons._name_to_key(name))

    @staticmethod
    def _name_to_key(name: str) -> str:
        return name.casefold().replace(" ", "_")


class MainWindow(QtWidgets.QTabWidget):
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
        if model.configuration.GUI.home.plots.dc_signals:
            sublayout.layout().addWidget(self.dc.window)
        if model.configuration.GUI.home.plots.interferometric_phase:
            sublayout.layout().addWidget(self.interferometric_phase.window)
        if model.configuration.GUI.home.plots.pti_signal:
            sublayout.layout().addWidget(self.pti_signal.window)
        self.layout().addWidget(sublayout, 0, 0)
        self.run_pressed = False

    def _init_buttons(self) -> None:
        sub_layout = QtWidgets.QWidget()
        sub_layout.setLayout(QtWidgets.QHBoxLayout())
        sub_layout.layout().setAlignment(QtCore.Qt.AlignHCenter)
        self._init_button(sub_layout, "Run", self.controller.on_run, image="png")
        if model.configuration.GUI.settings.use:
            self._init_button(sub_layout, "Settings", self.controller.show_settings, image="png")
        if model.configuration.GUI.home.use_valve:
            self._init_button(sub_layout, "Valve", self.controller.toggle_valve)
        if model.configuration.GUI.utilities.use:
            self._init_button(sub_layout, "Utilities", self.controller.show_utilities, image="png")
        if model.configuration.GUI.home.connect.use:
            self._init_button(sub_layout, "Connect", self.controller.connect_devices)
        if model.configuration.GUI.destination_folder.use:
            self._init_button(sub_layout, "Directory", self.controller.update_destination_folder)
        if model.configuration.GUI.home.use_shutdown:
            self._init_button(sub_layout, "Shutdown", self.controller.shutdown)
        self.layout().addWidget(sub_layout, 1, 0)

    def _init_button(self, parent: QtWidgets.QWidget, text: str, slot: Callable, image="svg") -> None:
        button_layout = QtWidgets.QWidget()
        button_layout.setLayout(QtWidgets.QVBoxLayout())
        self.buttons[text] = helper.create_button(parent=button_layout, title=text, only_icon=True, slot=slot)
        self.buttons[text].setIcon(QtGui.QIcon(f"{minipti.module_path}/gui/images/{text}.{image}"))
        self.buttons[text].setIconSize(QtCore.QSize(50, 50))
        self.buttons[text].setToolTip(text)
        button_layout.layout().addWidget(self.buttons[text])
        label = QtWidgets.QLabel(text)
        label.setAlignment(QtCore.Qt.AlignCenter)
        button_layout.layout().addWidget(label)
        parent.layout().addWidget(button_layout)

    @QtCore.pyqtSlot(bool)
    def update_run_measurement(self, state: bool) -> None:
        if state:
            icon = QtGui.QIcon(f"{minipti.module_path}/gui/images/Stop.svg")
        else:
            icon = QtGui.QIcon(f"{minipti.module_path}/gui/images/Run.png")
        self.buttons.run.setIcon(icon)

    @QtCore.pyqtSlot(bool)
    def update_clean_air(self, state: bool) -> None:
        if state:
            icon = QtGui.QIcon(f"{minipti.module_path}/gui/images/Valve_on.svg")
        else:
            icon = QtGui.QIcon(f"{minipti.module_path}/gui/images/Valve.svg")
        self.buttons.valve.setIcon(icon)

    def _init_signals(self) -> None:
        model.signals.DAQ.running.connect(self.update_run_measurement)
        model.signals.VALVE.bypass.connect(self.update_clean_air)
