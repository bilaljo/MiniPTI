from abc import abstractmethod

from PyQt5 import QtWidgets, QtGui
from matplotlib import pyplot as plt
from overrides import override

import minipti
from minipti.gui.view import helper
from minipti.gui import controller


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
        self.setWindowIcon(QtGui.QIcon(f"{minipti.module_path}/gui/images/calculation.svg"))


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
        self.setTitle("_Calculation")

    @override
    def _init_button(self) -> None:
        if self.controller.configuration.calculate.decimation:
            self.decimation = helper.create_button(parent=self, title="Decimation",
                                                   slot=self.controller.calculate_decimation)
        if self.controller.configuration.calculate.interferometry:
            self.interferometry = helper.create_button(parent=self, title="Interferometry",
                                                       slot=self.controller.calculate_interferometry)
        if self.controller.configuration.calculate.inversion:
            self.pti_inversion = helper.create_button(parent=self, title="PTI Inversion",
                                                      slot=self.controller.calculate_pti_inversion)
        if self.controller.configuration.calculate.characterisation:
            self.characterisation = helper.create_button(parent=self, title="Interferometer Characterisation",
                                                         slot=self.controller.calculate_characterisation)


class Plotting(UtilitiesBase):
    def __init__(self, utilities_controller: controller.interface.Utilities):
        UtilitiesBase.__init__(self, utilities_controller)
        self.controller = utilities_controller
        self.setTitle("Plotting")

    def _init_button(self) -> None:
        if self.controller.configuration.plot.dc:
            self.dc_signals = helper.create_button(parent=self, title="DC Signals",
                                                   slot=self.controller.plot_dc)
        if self.controller.configuration.plot.interferometry:
            self.interferometric_phase = helper.create_button(parent=self, title="Interferometric Phase",
                                                              slot=self.controller.plot_interferometric_phase)
        if self.controller.configuration.plot.inversion:
            self.pti_signal = helper.create_button(parent=self, title="PTI Signal",
                                                   slot=self.controller.plot_inversion)
