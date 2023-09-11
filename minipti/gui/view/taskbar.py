from ctypes import Union

from PyQt5 import QtWidgets
from dataclasses import dataclass

from PyQt5 import QtGui


class Connected(QtWidgets.QWidget):
    def __init__(self, on_icon_path: str, off_icon_path: str):
        QtWidgets.QWidget.__init__(self)
        self.connect: Union[QtWidgets.QToolButton, None] = None
        self.on_icon = QtGui.QIcon(on_icon_path)
        self.off_icon = QtGui.QIcon(off_icon_path)


class TaskBar(QtWidgets):
    def __init__(self):
        QtWidgets.QWidget.__init__(self)
