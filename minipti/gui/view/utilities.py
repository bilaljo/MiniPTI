from abc import abstractmethod

from PyQt5 import QtWidgets, QtGui
from matplotlib import pyplot as plt
from overrides import override

import minipti
from minipti.gui import controller, model
from minipti.gui.view import helper


class UtilitiesWindow(QtWidgets.QMainWindow):
    def __init__(self, utilities_controller: controller.interface.Utilities):
        QtWidgets.QMainWindow.__init__(self)
        self.parent = QtWidgets.QWidget()
        self.parent.setLayout(QtWidgets.QGridLayout())
        self.calculation = Calculation(utilities_controller)
        self.plotting = Plotting(utilities_controller)
        self.setWindowTitle("Utilities")
        self.parent.layout().addWidget(self.calculation, 0, 0)
        self.parent.layout().addWidget(self.plotting, 1, 0)
        self.setCentralWidget(self.parent)
        self.setFixedSize(300, 400)
        self.setWindowIcon(QtGui.QIcon(f"{minipti.module_path}/gui/images/Utilities.png"))
        self.progessbar = QtWidgets.QProgressBar()


class UtilitiesBase(QtWidgets.QGroupBox):
    def __init__(self, utilities_controller: controller.interface.Utilities):
        QtWidgets.QGroupBox.__init__(self)
        self.controller = utilities_controller
        self.setLayout(QtWidgets.QVBoxLayout())
        self._init_button()

    @abstractmethod
    def _init_button(self) -> None:
        ...


def update_matplotlib_theme(theme: str):
    if theme == "Dark":
        plt.style.use('dark_background')
    else:
        plt.style.use('light_background')


class Calculation(UtilitiesBase):
    def __init__(self, utilities_controller: controller.interface.Utilities):
        UtilitiesBase.__init__(self, utilities_controller)
        self.setTitle("Calculation")

    @override
    def _init_button(self) -> None:
        if model.configuration.GUI.utilities.calculate.decimation:
            self.decimation = helper.create_button(parent=self, title="Decimation",
                                                   slot=self.controller.calculate_decimation)
        if model.configuration.GUI.utilities.calculate.interferometry:
            self.interferometry = helper.create_button(parent=self, title="Interferometry",
                                                       slot=self.controller.calculate_interferometry)
        if model.configuration.GUI.utilities.calculate.response_phases:
            self.response_phases = helper.create_button(parent=self, title="Response Phase",
                                                        slot=self.controller.calculate_response_phases)
        if model.configuration.GUI.utilities.calculate.inversion:
            self.pti_inversion = helper.create_button(parent=self, title="PTI Inversion",
                                                      slot=self.controller.calculate_pti_inversion)
        if model.configuration.GUI.utilities.calculate.characterisation:
            self.characterisation = helper.create_button(parent=self, title="Interferometer Characterisation",
                                                         slot=self.controller.calculate_characterisation)


class Plotting(UtilitiesBase):
    def __init__(self, utilities_controller: controller.interface.Utilities):
        UtilitiesBase.__init__(self, utilities_controller)
        self.controller = utilities_controller
        self.setTitle("Plotting")

    def _init_button(self) -> None:
        if model.configuration.GUI.utilities.plot.dc:
            self.dc_signals = helper.create_button(parent=self, title="DC Signals",
                                                   slot=self.controller.plot_dc)
        if model.configuration.GUI.utilities.plot.interferometry:
            self.interferometric_phase = helper.create_button(parent=self, title="Interferometric Phase",
                                                              slot=self.controller.plot_interferometric_phase)

        if model.configuration.GUI.utilities.plot.lock_in_phases:
            self.lock_in_phases = helper.create_button(parent=self, title="Lock In Phases",
                                                       slot=self.controller.plot_lock_in_phases)

        if model.configuration.GUI.utilities.plot.inversion:
            self.pti_signal = helper.create_button(parent=self, title="PTI Signal",
                                                   slot=self.controller.plot_inversion)
