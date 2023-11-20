from abc import abstractmethod

import matplotlib
import numpy as np
import pyqtgraph as pg
from PyQt5 import QtCore, QtWidgets
from matplotlib import pyplot as plt
from matplotlib.backends.backend_qt import NavigationToolbar2QT
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from overrides import override

from minipti.gui import model

matplotlib.use('Qt5Agg')


class _MatplotlibColors:
    BLUE = "#045993"
    ORANGE = "#db6000"
    GREEN = "#118011"


class Plotting(pg.PlotWidget):
    def __init__(self):
        pg.PlotWidget.__init__(self)
        pg.setConfigOption('leftButtonPan', False)
        pg.setConfigOptions(antialias=True)
        self.window = pg.GraphicsLayoutWidget()
        self.plot = self.window.addPlot()
        self.curves = self.plot.plot(pen=pg.mkPen(_MatplotlibColors.BLUE))
        self.plot.showGrid(x=True, y=True)
        self.legend = self.plot.addLegend()

    def update_theme(self, theme: str) -> None:
        if theme == "Dark":
            background = "k"
            color = "w"
        else:
            background = "w"
            color = "k"
        self.window.setBackground(background)
        try:
            self.legend.setLabelTextColor(color)
        except RuntimeError:
            pass  # No legend existent
        try:
            self.plot.getAxis('bottom').setPen(color)
            self.plot.getAxis("left").setPen(color)
        except AttributeError:
            for channel in range(len(self.plot)):
                self.plot[channel].getAxis('bottom').setPen(color)
                self.plot[channel].getAxis('bottom').setTextPen(color)
                self.plot[channel].getAxis('left').setPen(color)
                self.plot[channel].getAxis('left').setTextPen(color)

    @QtCore.pyqtSlot()
    def clear(self) -> None:
        self.window.clear()

    @abstractmethod
    def update_data_live(self, data: model.buffer.BaseClass) -> None:
        ...


class DAQPlots(Plotting):
    def __init__(self):
        Plotting.__init__(self)
        model.signals.DAQ.clear.connect(self.clear)
        self.name = ""

    @abstractmethod
    def update_data_live(self, data: model.buffer.BaseClass) -> None:
        ...


class OfflinePlot(QtWidgets.QMainWindow):
    def __init__(self):
        QtWidgets.QMainWindow.__init__(self)
        self.parent = QtWidgets.QWidget()
        self.parent.setLayout(QtWidgets.QVBoxLayout())
        self.figure = plt.Figure()
        self.canvas = FigureCanvasQTAgg(self.figure)
        self.toolbar = NavigationToolbar2QT(self.canvas, self)
        self.parent.layout().addWidget(self.canvas)
        self.parent.layout().addWidget(self.toolbar)
        self.setCentralWidget(self.parent)

    @abstractmethod
    def plot(self, data: np.ndarray) -> None:
        ...


class DCOffline(OfflinePlot):
    def __init__(self):
        OfflinePlot.__init__(self)
        self.setWindowTitle("DC Signals")

    @override
    def plot(self, data: np.ndarray) -> None:
        ax = self.figure.add_subplot()
        for channel in range(3):
            ax.plot(data[channel], label=f"CH{channel + 1}")
        ax.grid()
        ax.set_xlabel("Time [s]")
        ax.set_ylabel("Intensity [V]")
        self.canvas.draw()
        self.show()


class DC(DAQPlots):
    def __init__(self):
        DAQPlots.__init__(self)
        self.curves = [self.plot.plot(pen=pg.mkPen(_MatplotlibColors.BLUE), name="DC CH1"),
                       self.plot.plot(pen=pg.mkPen(_MatplotlibColors.ORANGE), name="DC CH2"),
                       self.plot.plot(pen=pg.mkPen(_MatplotlibColors.GREEN), name="DC CH3")]
        self.plot.setLabel(axis="bottom", text="Time [s]")
        self.plot.setLabel(axis="left", text="Intensity [V]")
        self.name = "DC Plots"
        model.signals.DAQ.interferometry.connect(self.update_data_live)

    @override(check_signature=False)
    def update_data_live(self, data: model.buffer.Interferometer) -> None:
        for channel in range(3):
            self.curves[channel].setData(data.time, data.dc_values[channel])


def amplitudes_offline(data: np.ndarray) -> None:
    plt.figure()
    for channel in range(3):
        plt.plot(data[channel], label=f"CH{channel + 1}")
    plt.grid()
    plt.xlabel("Time [s]")
    plt.ylabel(r"Amplitude [V]")
    plt.legend()
    plt.show()


class Amplitudes(DAQPlots):
    def __init__(self):
        DAQPlots.__init__(self)
        self.curves = [self.plot.scatterPlot(pen=pg.mkPen(_MatplotlibColors.BLUE),
                                             brush=pg.mkBrush(_MatplotlibColors.BLUE),
                                             name="Amplitude CH1"),
                       self.plot.scatterPlot(pen=pg.mkPen(_MatplotlibColors.ORANGE),
                                             brush=pg.mkBrush(_MatplotlibColors.ORANGE),
                                             name="Amplitude CH2"),
                       self.plot.scatterPlot(pen=pg.mkPen(_MatplotlibColors.GREEN),
                                             brush=pg.mkBrush(_MatplotlibColors.GREEN),
                                             name="Amplitude CH3")]
        self.plot.setLabel(axis="bottom", text="Time [s]")
        self.plot.setLabel(axis="left", text="Amplitude [V]")
        self.name = "Amplitudes"
        model.signals.DAQ.characterization.connect(self.update_data_live)

    @override(check_signature=False)
    def update_data_live(self, data: model.buffer.Characterisation) -> None:
        for channel in range(3):
            self.curves[channel].setData(data.time, data.amplitudes[channel])


def output_phases_offline(data: np.ndarray) -> None:
    plt.figure()
    for channel in range(1, 3):
        plt.plot(data[channel], label=f"CH{channel + 1}")
    plt.grid()
    plt.xlabel("Time [s]")
    plt.ylabel(r"Output Phase [rad]")
    plt.legend()
    plt.show()


class OutputPhases(DAQPlots):
    def __init__(self):
        DAQPlots.__init__(self)
        self.curves = [self.plot.scatterPlot(pen=pg.mkPen(_MatplotlibColors.ORANGE), name="Output Phase CH2",
                                             brush=pg.mkBrush(_MatplotlibColors.ORANGE)),
                       self.plot.scatterPlot(pen=pg.mkPen(_MatplotlibColors.GREEN), name="Output Phase CH3",
                                             brush=pg.mkBrush(_MatplotlibColors.GREEN))]
        self.plot.setLabel(axis="bottom", text="Time [s]")
        self.plot.setLabel(axis="left", text="Output Phase [deg]")
        self.name = "Output Phases"
        model.signals.DAQ.characterization.connect(self.update_data_live)

    @override(check_signature=False)
    def update_data_live(self, data: model.buffer.Characterisation) -> None:
        for channel in range(2):
            self.curves[channel].setData(data.time, np.rad2deg(data.output_phases[channel]))


class InterferometricPhaseOffline(OfflinePlot):
    def __init__(self):
        OfflinePlot.__init__(self)
        self.setWindowTitle("Interferometric Phase")

    def plot(self, data: np.ndarray) -> None:
        ax = self.figure.add_subplot()
        ax.plot(data)
        ax.grid()
        ax.set_xlabel("Time [s]")
        ax.set_ylabel(r"Interferometric [rad]")
        self.canvas.draw()
        self.show()


class InterferometricPhase(DAQPlots):
    def __init__(self):
        DAQPlots.__init__(self)
        self.curves = self.plot.plot(pen=pg.mkPen(_MatplotlibColors.BLUE))
        self.plot.setLabel(axis="bottom", text="Time [s]")
        self.plot.setLabel(axis="left", text="Interferometric Phase [rad]")
        self.name = "Interferometric Phase"
        model.signals.DAQ.interferometry.connect(self.update_data_live)

    @override(check_signature=False)
    def update_data_live(self, data: model.buffer.Interferometer) -> None:
        self.curves.setData(data.time, data.interferometric_phase)


def sensitivity_offline(data: np.ndarray) -> None:
    plt.figure()
    for channel in range(3):
        plt.plot(data[f"Sensitivity CH{channel + 1}"], label=f"CH{channel + 1}")
    plt.grid()
    plt.xlabel("Time [s]")
    plt.ylabel(r"Sensitivity [$\frac{1}{rad}]")
    plt.legend()
    plt.show()


class Sensitivity(DAQPlots):
    def __init__(self):
        DAQPlots.__init__(self)
        self.curves = [self.plot.plot(pen=pg.mkPen(_MatplotlibColors.BLUE), name="CH1"),
                       self.plot.plot(pen=pg.mkPen(_MatplotlibColors.ORANGE), name="CH2"),
                       self.plot.plot(pen=pg.mkPen(_MatplotlibColors.GREEN), name="CH3")]
        self.plot.setLabel(axis="bottom", text="Time [s]")
        self.plot.setLabel(axis="left", text="Sensitivity [V/rad]")
        self.name = "Sensitivity"
        model.signals.DAQ.interferometry.connect(self.update_data_live)

    @override(check_signature=False)
    def update_data_live(self, data: model.buffer.Interferometer) -> None:
        for channel in range(3):
            self.curves[channel].setData(data.time, data.sensitivity[channel])


class Symmetry(DAQPlots):
    def __init__(self):
        DAQPlots.__init__(self)
        self.curves = [self.plot.scatterPlot(pen=pg.mkPen(_MatplotlibColors.BLUE), name="Absolute Symmetry",
                                             brush=pg.mkBrush(_MatplotlibColors.BLUE)),
                       self.plot.scatterPlot(pen=pg.mkPen(_MatplotlibColors.ORANGE), name="Relative Symmetry",
                                             brush=pg.mkBrush(_MatplotlibColors.ORANGE))]
        self.plot.setLabel(axis="bottom", text="Time [s]")
        self.plot.setLabel(axis="left", text="Symmetry [%]")
        self.name = "Symmetry"
        model.signals.DAQ.characterization.connect(self.update_data_live)

    @override(check_signature=False)
    def update_data_live(self, data: model.buffer.Characterisation) -> None:
        self.curves[0].setData(data.time, data.symmetry)
        self.curves[1].setData(data.time, data.relative_symmetry)


def pti_signal_offline(data: dict[str]) -> None:
    plt.figure()
    try:
        plt.plot(data["PTI Signal"], label="1-s Data")
        plt.plot(data["PTI Signal 60 s Mean"], label="60-s Mean")
        plt.grid()
        plt.xlabel("Time [s]")
        plt.ylabel("PTI Signal [µrad]")
        plt.legend()
        plt.show()
    except KeyError:
        pass


class Characterisation(QtWidgets.QTabWidget):
    def __init__(self):
        QtWidgets.QTabWidget.__init__(self)
        self.setLayout(QtWidgets.QHBoxLayout())
        self.amplitudes = Amplitudes()
        self.output_phase = OutputPhases()
        self.symmetry = Symmetry()
        self.layout().addWidget(self.amplitudes.window)
        self.layout().addWidget(self.output_phase.window)
        self.layout().addWidget(self.symmetry.window)


class Interferometrie(QtWidgets.QTabWidget):
    def __init__(self):
        QtWidgets.QTabWidget.__init__(self)
        self.setLayout(QtWidgets.QHBoxLayout())
        self.dc_plot = DC()
        self.phase_plot = InterferometricPhase()
        self.layout().addWidget(self.dc_plot.window)
        self.layout().addWidget(self.phase_plot.window)


class PTISignal(DAQPlots):
    def __init__(self):
        DAQPlots.__init__(self)
        self.curves = {"PTI Signal": self.plot.scatterPlot(pen=pg.mkPen(_MatplotlibColors.BLUE), name="1 s", size=6),
                       "PTI Signal Mean": self.plot.plot(pen=pg.mkPen(_MatplotlibColors.ORANGE), name="60 s Mean")}
        self.plot.setLabel(axis="bottom", text="Time [s]")
        self.plot.setLabel(axis="left", text="PTI Signal [µrad]")
        self.name = "PTI Signal"
        model.signals.DAQ.inversion.connect(self.update_data_live)

    @override(check_signature=False)
    def update_data_live(self, data: model.buffer.PTI) -> None:
        self.curves["PTI Signal"].setData(data.time, data.pti_signal)
        self.curves["PTI Signal Mean"].setData(data.time, data.pti_signal_mean)


class Measurement(QtWidgets.QTabWidget):
    def __init__(self):
        QtWidgets.QTabWidget.__init__(self)
        self.setLayout(QtWidgets.QHBoxLayout())
        self.sensitivity = Sensitivity()
        self.pti = PTISignal()
        self.layout().addWidget(self.sensitivity.window)
        self.layout().addWidget(self.pti.window)


class PumpLaserCurrent(Plotting):
    def __init__(self):
        Plotting.__init__(self)
        self.curves = self.plot.plot(pen=pg.mkPen(_MatplotlibColors.BLUE))
        self.plot.setLabel(axis="bottom", text="Time [s]")
        self.plot.setLabel(axis="left", text="Current [mA]")
        model.signals.LASER.data.connect(self.update_data_live)

    @override(check_signature=False)
    def update_data_live(self, data: model.buffer.Laser) -> None:
        self.curves.setData(data.time, data.pump_laser_current)


class ProbeLaserCurrent(Plotting):
    def __init__(self):
        Plotting.__init__(self)
        self.curves = self.plot.plot(pen=pg.mkPen(_MatplotlibColors.BLUE))
        self.plot.setLabel(axis="bottom", text="Time [s]")
        self.plot.setLabel(axis="left", text="Current [mA]")
        model.signals.LASER.data.connect(self.update_data_live)

    @override(check_signature=False)
    def update_data_live(self, data: model.buffer.Laser) -> None:
        self.curves.setData(data.time, data.probe_laser_current)


class TecTemperature(Plotting):
    SET_POINT = 0
    MEASURED = 1

    def __init__(self, channel: int):
        Plotting.__init__(self)
        self.curves = [self.plot.plot(pen=pg.mkPen(_MatplotlibColors.BLUE), name="Setpoint Temperature"),
                       self.plot.plot(pen=pg.mkPen(_MatplotlibColors.ORANGE), name="Measured Temperature")]
        self.plot.setLabel(axis="bottom", text="Time [s]")
        self.plot.setLabel(axis="left", text="Temperature [°C]")
        self.laser = channel
        model.signals.GENERAL_PURPORSE.tec_data.connect(self.update_data_live)

    @override(check_signature=False)
    def update_data_live(self, data: model.buffer.Tec) -> None:
        self.curves[TecTemperature.SET_POINT].setData(data.time, data.set_point[self.laser])
        self.curves[TecTemperature.MEASURED].setData(data.time, data.actual_value[self.laser])
