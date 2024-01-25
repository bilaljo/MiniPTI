import logging
from abc import abstractmethod
from collections import deque

import darkdetect
import pandas as pd
from PyQt5 import QtCore

from minipti.gui.model import signals


class Table(QtCore.QAbstractTableModel):
    SIGNIFICANT_VALUES = 2

    def __init__(self):
        QtCore.QAbstractTableModel.__init__(self)
        self._data = pd.DataFrame()

    @property
    @abstractmethod
    def _headers(self) -> list[str]:
        ...

    @property
    @abstractmethod
    def _indices(self) -> list[str]:
        ...

    def rowCount(self, parent=None) -> int:
        return self._data.shape[0]

    def columnCount(self, parent=None) -> int:
        return self._data.shape[1]

    def data(self, index, role: int = ...) -> str | None:
        if index.isValid():
            if role == QtCore.Qt.DisplayRole or role == QtCore.Qt.EditRole:
                value = self._data.iloc[index.row()][self._headers[index.column()]]
                return f"{value:.2E}"

    def flags(self, index):
        return QtCore.Qt.ItemIsSelectable | QtCore.Qt.ItemIsEnabled | QtCore.Qt.ItemIsEditable

    def setData(self, index, value, role: int = ...):
        if index.isValid():
            if role == QtCore.Qt.EditRole:
                self._data.iloc[index.row()][self._headers[index.column()]] = float(value)
                return True

    def headerData(self, section, orientation, role=QtCore.Qt.DisplayRole):
        if orientation == QtCore.Qt.Horizontal and role == QtCore.Qt.DisplayRole:
            return self._headers[section]
        elif orientation == QtCore.Qt.Vertical and role == QtCore.Qt.DisplayRole:
            return self._indices[section]
        return super().headerData(section, orientation, role)

    @property
    def table_data(self) -> pd.DataFrame:
        return self._data

    @table_data.setter
    def table_data(self, data) -> None:
        self._data = data


def theme_observer() -> None:
    signals.GENERAL_PURPORSE.theme_changed.emit(darkdetect.theme())
    darkdetect.listener(lambda x: signals.GENERAL_PURPORSE.theme_changed.emit(x))


class Logging(logging.Handler):
    LOGGING_HISTORY = 50

    def __init__(self):
        logging.Handler.__init__(self)
        self.logging_messages = deque(maxlen=Logging.LOGGING_HISTORY)
        self.formatter = logging.Formatter("[%(threadName)s] %(levelname)s %(asctime)s: %(message)s",
                                           datefmt="%Y-%m-%d %H:%M:%S")
        logging.getLogger().addHandler(self)
        root_logger = logging.getLogger()
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(self.formatter)
        root_logger.addHandler(console_handler)

    def emit(self, record: logging.LogRecord) -> None:
        log = self.format(record)
        if "ERROR" in log:
            log = f"<p style='color:red'>{log}</p>"
        elif "INFO" in log:
            log = f"<p style='color:green'>{log}</p>"
        elif "WARNING" in log:
            log = f"<p style='color:orange'>{log}</p>"
        elif "DEBUG" in log:
            log = f"<p style='color:blue'>{log}</p>"
        elif "CRITICAL" in log:
            log = f"<b><p style='color:darkred'>{log}</p></b>"
        self.logging_messages.append(log)
        signals.GENERAL_PURPORSE.logging_update.emit(self.logging_messages)
