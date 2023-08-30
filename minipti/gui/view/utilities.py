from abc import abstractmethod

from PyQt5 import QtWidgets
from overrides import override

from minipti.gui.view import helper
from minipti.gui import controller


class UtilitiesWindow(QtWidgets.QMainWindow):
    def __init__(self, utilities_controller: controller.interface.Utilities):
        QtWidgets.QMainWindow.__init__(self)
        self.parent = QtWidgets.QWidget()
        self.parent.setLayout(QtWidgets.QGridLayout())
        self.decimation = Decimation(utilities_controller)
        self.inversion = PTIInversion(utilities_controller)
        self.characterisation = Characterisation(utilities_controller)
        self.setWindowTitle("Utilities")
        self.parent.layout().addWidget(self.decimation, 0, 0)
        self.parent.layout().addWidget(self.inversion, 1, 0)
        self.parent.layout().addWidget(self.characterisation, 2, 0)
        self.setCentralWidget(self.parent)
        self.setFixedSize(200, 400)


class Algorithm(QtWidgets.QGroupBox):
    def __init__(self, utilities_controller: controller.interface.Utilities):
        QtWidgets.QGroupBox.__init__(self)
        self.utilities_controller = utilities_controller
        self.calculate = QtWidgets.QPushButton()
        self.plot = QtWidgets.QPushButton()
        self.setLayout(QtWidgets.QVBoxLayout())
        self._init_button()

    @abstractmethod
    def _init_button(self) -> None:
        ...


class Decimation(Algorithm):
    def __init__(self, utilities_controller: controller.interface.Utilities):
        Algorithm.__init__(self, utilities_controller)
        self.setTitle("Decimation")

    @override
    def _init_button(self) -> None:
        self.calculate = helper.create_button(parent=self, title="Calculate",
                                              slot=self.utilities_controller.calculate_decimation)
        self.plot = helper.create_button(parent=self, title="Plot DC Signals",
                                         slot=self.utilities_controller.plot_dc)


class PTIInversion(Algorithm):
    def __init__(self, utilities_controller: controller.interface.Utilities):
        Algorithm.__init__(self, utilities_controller)
        self.setTitle("PTI Inversion")

    @override
    def _init_button(self) -> None:
        self.calculate = helper.create_button(parent=self, title="Calculate",
                                              slot=self.utilities_controller.calculate_decimation)
        self.plot = helper.create_button(parent=self, title="Plot",
                                         slot=self.utilities_controller.plot_dc)


class Characterisation(Algorithm):
    def __init__(self, utilities_controller: controller.interface.Utilities):
        Algorithm.__init__(self, utilities_controller)
        self.setTitle("Interferometer Characterisation")

    @override
    def _init_button(self) -> None:
        self.calculate = helper.create_button(parent=self, title="Calculates",
                                              slot=self.utilities_controller.calculate_decimation)
        self.plot = helper.create_button(parent=self, title="Plot",
                                         slot=self.utilities_controller.plot_dc)

