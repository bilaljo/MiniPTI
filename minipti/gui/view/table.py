from typing import Union

from PyQt5 import QtWidgets

from minipti.gui import model


class Table(QtWidgets.QTableView):
    def __init__(self, parent, table_model: Union[model.general_purpose.Table, None] = None):
        QtWidgets.QTableView.__init__(self, parent=parent)
        header = self.horizontalHeader()
        header.setStretchLastSection(True)
        index = self.verticalHeader()
        index.setSectionResizeMode(QtWidgets.QHeaderView.Stretch)
        header.setSectionResizeMode(QtWidgets.QHeaderView.Stretch)
        index.setStretchLastSection(True)
        self.resizeColumnsToContents()
        self.resizeRowsToContents()
        self.setModel(table_model)
