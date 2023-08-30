from typing import Any, Callable, Union

from PyQt5 import QtWidgets


def toggle_button(checked, button: QtWidgets.QPushButton) -> None:
    if checked:
        button.setStyleSheet("background-color : lightgreen")
    else:
        button.setStyleSheet("background-color : light gray")


def create_button(parent, title: str, slot: Callable[[Any], Any], only_icon=False) -> Union[QtWidgets.QPushButton,
                                                                                            QtWidgets.QToolButton]:
    if only_icon:
        button: QtWidgets.QToolButton = QtWidgets.QToolButton()
    else:
        button: QtWidgets.QPushButton = QtWidgets.QPushButton()
    button.setParent(parent)
    button.setText(title)
    button.clicked.connect(slot)
    parent.layout().addWidget(button)
    return button


def create_frame(parent, title: str, x_position: int, y_position: int, x_span: int = 1,
                 y_span: int = 1) -> QtWidgets.QGroupBox:
    frame: QtWidgets.QGroupBox = QtWidgets.QGroupBox()
    frame.setTitle(title)
    frame.setLayout(QtWidgets.QGridLayout())
    if isinstance(parent.layout(), QtWidgets.QGridLayout):
        parent.layout().addWidget(frame, x_position, y_position, x_span, y_span)
    else:
        parent.layout().addWidget(frame)
    return frame
