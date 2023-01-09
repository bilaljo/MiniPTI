import abc

import pyqtgraph as pg
from PySide6 import QtWidgets, QtGui, QtCore


class _Tab(QtWidgets.QTabWidget):
    def __init__(self, name="_Tab"):
        QtWidgets.QTabWidget.__init__(self)
        self.name = name
        self.frames = {}
        self.setLayout(QtWidgets.QGridLayout())

    def create_frame(self, title, x_position, y_position):
        self.frames[title] = QtWidgets.QGroupBox()
        self.frames[title].setTitle(title)
        self.frames[title].setLayout(QtWidgets.QGridLayout())
        self.layout().addWidget(self.frames[title], x_position, y_position)


class CreateButton:
    def __init__(self):
        self.buttons = {}

    def create_button(self, master, title, slot):
        self.buttons[title] = QtWidgets.QPushButton(master, text=title)
        self.buttons[title].clicked.connect(slot)
        master.layout().addWidget(self.buttons[title])

    @abc.abstractmethod
    def _init_buttons(self, controller):
        pass


class SettingsView(QtWidgets.QTableView):
    def __init__(self, parent):
        QtWidgets.QTableView.__init__(self, parent=parent)
        header = self.horizontalHeader()
        header.setStretchLastSection(True)
        index = self.verticalHeader()
        index.setSectionResizeMode(QtWidgets.QHeaderView.Stretch)
        header.setSectionResizeMode(QtWidgets.QHeaderView.Stretch)
        index.setStretchLastSection(True)
        self.resizeColumnsToContents()
        self.resizeRowsToContents()


class Home(_Tab, CreateButton):
    def __init__(self, logging_window, controller, name="Home"):
        _Tab.__init__(self, name=name)
        CreateButton.__init__(self)
        self._init_frames()
        self.settings = SettingsView(parent=self.frames["Setting"])
        self.frames["Setting"].layout().addWidget(self.settings, 0, 0)
        self.frames["Log"].layout().addWidget(logging_window)
        self._init_buttons(controller)

    def _init_frames(self):
        self.create_frame(title="Log", x_position=0, y_position=1)
        self.create_frame(title="Setting", x_position=0, y_position=0)
        self.create_frame(title="Offline Processing", x_position=1, y_position=0)
        self.create_frame(title="Plot Data", x_position=2, y_position=0)
        self.create_frame(title="Drivers", x_position=3, y_position=0)

    def _init_buttons(self, controller):
        assert (controller is not None)

        # Settings buttons
        sub_layout = QtWidgets.QWidget()
        self.frames["Setting"].layout().addWidget(sub_layout)
        sub_layout.setLayout(QtWidgets.QHBoxLayout())
        self.create_button(master=sub_layout, title="Save Settings", slot=controller.save_settings)
        self.create_button(master=sub_layout, title="Load Settings", slot=controller.load_settings)
        # TODO: Implement autosave slot
        self.create_button(master=sub_layout, title="Auto Save", slot=controller.load_settings)

        # Offline Processing buttons
        sub_layout = QtWidgets.QWidget()
        sub_layout.setLayout(QtWidgets.QHBoxLayout())
        self.frames["Offline Processing"].layout().addWidget(sub_layout)
        self.create_button(master=sub_layout, title="Decimation", slot=controller.calculate_decimation)
        self.create_button(master=sub_layout, title="Inversion", slot=controller.calculate_inversion)
        self.create_button(master=sub_layout, title="Characterisation", slot=controller.calculate_characterisation)

        # Plotting buttons
        sub_layout = QtWidgets.QWidget(parent=self.frames["Plot Data"])
        sub_layout.setLayout(QtWidgets.QHBoxLayout())
        self.frames["Plot Data"].layout().addWidget(sub_layout)
        self.create_button(master=sub_layout, title="Decimation", slot=controller.plot_dc)
        self.create_button(master=sub_layout, title="Inversion", slot=controller.plot_inversion)
        self.create_button(master=sub_layout, title="Characterisation", slot=controller.plot_characterisation)

        # Driver buttons
        sub_layout = QtWidgets.QWidget(parent=self.frames["Drivers"])
        sub_layout.setLayout(QtWidgets.QHBoxLayout())
        self.frames["Drivers"].layout().addWidget(sub_layout)
        self.create_button(master=sub_layout, title="Scan Ports", slot=controller.plot_dc)
        self.create_button(master=sub_layout, title="Connect Devices", slot=controller.plot_dc)


class ValveSlider(QtWidgets.QWidget):
    def __init__(self):
        QtWidgets.QWidget.__init__(self)
        self.slider = QtWidgets.QSlider()
        self.setLayout(QtWidgets.QHBoxLayout())
        self.layout().addWidget(self.slider)
        # self.slider.setTickPosition(QtWidgets.QSlider.TickPosition.TicksBothSides)
        self.slider.setOrientation(QtCore.Qt.Orientation.Horizontal)
        self.slider_value = QtWidgets.QLabel()
        self.layout().addWidget(self.slider_value)
        self.slider_value.setText(f"{self.slider.value() / ((1 << 16) - 1)} %")
        self.slider.setMaximum((1 << 16) - 1)
        self.slider.valueChanged.connect(self.update_value)

    def update_value(self):
        self.slider_value.setText(f"{round(self.slider.value() / ((1 << 16) - 1) * 100, 2)} %")


class DAQ(_Tab, CreateButton):
    def __init__(self, controller, name="DAQ"):
        _Tab.__init__(self, name=name)
        CreateButton.__init__(self)
        self._init_frames()
        self._init_buttons(controller)

    def _init_frames(self):
        self.create_frame(title="Port", x_position=0, y_position=0)
        self.create_frame(title="Information", x_position=1, y_position=0)
        self.create_frame(title="Valves", x_position=2, y_position=0)

    def _init_buttons(self, controller):
        sub_layout = QtWidgets.QWidget()
        self.frames["Port"].layout().addWidget(sub_layout)
        sub_layout.setLayout(QtWidgets.QVBoxLayout())
        information_box = QtWidgets.QLabel()
        information_box.setText("COM3")
        sub_layout.layout().addWidget(information_box)
        information_box = QtWidgets.QLabel()
        information_box.setText("Connected")
        sub_layout.layout().addWidget(information_box)

        sub_layout = QtWidgets.QWidget()
        self.frames["Information"].layout().addWidget(sub_layout)
        sub_layout.setLayout(QtWidgets.QHBoxLayout())
        self.create_button(master=sub_layout, title="Device ID", slot=controller.save_settings)
        self.create_button(master=sub_layout, title="Device Version", slot=controller.save_settings)
        self.create_button(master=sub_layout, title="Firmware Version", slot=controller.save_settings)

        self.frames["Valves"].layout().addWidget(QtWidgets.QLabel("Valve 1"))
        self.frames["Valves"].layout().addWidget(ValveSlider())
        self.frames["Valves"].layout().addWidget(QtWidgets.QLabel("Valve 2"))
        self.frames["Valves"].layout().addWidget(ValveSlider())


class _MatplotlibColors:
    BLUE = "#045993"
    ORANGE = "#db6000"
    GREEN = "#118011"


class _Plotting(pg.PlotWidget):
    def __init__(self):
        pg.PlotWidget.__init__(self)
        pg.setConfigOption('leftButtonPan', False)
        pg.setConfigOptions(antialias=True)
        pg.setConfigOption('background', "white")
        pg.setConfigOption('foreground', 'k')
        self.curves = None
        self.window = pg.GraphicsLayoutWidget()


class DC(_Tab):
    def __init__(self, name="DC Signals"):
        _Tab.__init__(self, name)
        self.plot = _Plotting()
        plot = self.plot.window.addPlot()
        plot.addLegend()
        self.plot.curves = [plot.plot(pen=pg.mkPen(_MatplotlibColors.BLUE), name="DC CH1"),
                            plot.plot(pen=pg.mkPen(_MatplotlibColors.ORANGE), name="DC CH2"),
                            plot.plot(pen=pg.mkPen(_MatplotlibColors.GREEN), name="DC CH3")]
        plot.setLabel(axis="bottom", text="Time [s]")
        plot.setLabel(axis="left", text="Intensity [V]")
        plot.showGrid(x=True, y=True)
        self.layout().addWidget(self.plot.window)


class Amplitudes(_Tab):
    def __init__(self, name="Amplitudes"):
        _Tab.__init__(self, name)
        self.plot = _Plotting()
        plot = self.plot.window.addPlot()
        plot.addLegend()
        self.curves = [plot.plot(pen=pg.mkPen(_MatplotlibColors.BLUE), name="Amplitude CH1"),
                       plot.plot(pen=pg.mkPen(_MatplotlibColors.ORANGE), name="Amplitude CH2"),
                       plot.plot(pen=pg.mkPen(_MatplotlibColors.GREEN), name="Amplitude CH3")]
        plot.setLabel(axis="bottom", text="Time [s]")
        plot.setLabel(axis="left", text="Amplitude [V]")
        plot.showGrid(x=True, y=True)
        self.layout().addWidget(self.plot.window)


class OutputPhases(_Tab):
    def __init__(self, name="Output Phases"):
        _Tab.__init__(self, name)
        self.plot = _Plotting()
        plot = self.plot.window.addPlot()
        plot.addLegend()
        self.curves = [plot.plot(pen=pg.mkPen(_MatplotlibColors.ORANGE), name="Output Phase CH2"),
                       plot.plot(pen=pg.mkPen(_MatplotlibColors.GREEN), name="Output Phase CH3")]
        plot.setLabel(axis="bottom", text="Time [s]")
        plot.setLabel(axis="left", text="Output Phase [deg]")
        plot.showGrid(x=True, y=True)
        self.layout().addWidget(self.plot.window)


class InterferometricPhase(_Tab):
    def __init__(self, name="Interferometric Phase"):
        _Tab.__init__(self, name)
        self.plot = _Plotting()
        plot = self.plot.window.addPlot()
        plot.addLegend()
        self.curves = plot.plot(pen=pg.mkPen(_MatplotlibColors.BLUE))
        plot.setLabel(axis="bottom", text="Time [s]")
        plot.setLabel(axis="left", text="Interferometric Phase [rad]")
        plot.showGrid(x=True, y=True)
        self.layout().addWidget(self.plot.window)


class Sensitivity(_Tab):
    def __init__(self, name="Sensitivity"):
        _Tab.__init__(self, name)
        self.plot = _Plotting()
        plot = self.plot.window.addPlot()
        self.curves = plot.plot(pen=pg.mkPen(_MatplotlibColors.BLUE))
        plot.setLabel(axis="bottom", text="Time [s]")
        plot.setLabel(axis="left", text="Sensitivity [1/rad]")
        plot.showGrid(x=True, y=True)
        self.layout().addWidget(self.plot.window)


class PTISignal(_Tab):
    def __init__(self, name="PTI Signal"):
        _Tab.__init__(self, name)
        self.plot = _Plotting()
        plot = self.plot.window.addPlot()
        plot.addLegend()
        self.curves = {}
        self.curves["PTI Signal"] = plot.scatterPlot(pen=pg.mkPen(_MatplotlibColors.BLUE), name="1 s", size=6)
        self.curves["PTI Signal Mean"] = plot.plot(pen=pg.mkPen(_MatplotlibColors.ORANGE), name="60 s Mean")
        plot.setLabel(axis="bottom", text="Time [s]")
        plot.setLabel(axis="left", text="PTI Signal [µrad]")
        plot.showGrid(x=True, y=True)
        self.layout().addWidget(self.plot.window)
