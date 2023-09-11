from abc import abstractmethod, ABC

import pandas as pd
import pyqtgraph as pg
from PyQt5 import QtCore
from overrides import override

from .. import model


class _MatplotlibColors:
    BLUE = "#045993"
    ORANGE = "#db6000"
    GREEN = "#118011"


class Plotting(pg.PlotWidget):
    def __init__(self):
        pg.PlotWidget.__init__(self)
        pg.setConfigOption('leftButtonPan', False)
        pg.setConfigOption("useNumba", True)
        # pg.setConfigOptions(antialias=True)
        self.window = pg.GraphicsLayoutWidget()
        self.plot = self.window.addPlot()
        self.curves = self.plot.plot(pen=pg.mkPen(_MatplotlibColors.BLUE))
        self.plot.showGrid(x=True, y=True)
        self.legend = self.plot.addLegend()

    def update_theme(self, theme: str) -> None:
        if theme == "Dark":
            self.window.setBackground("k")
            try:
                self.plot.getAxis('bottom').setPen('w')
                self.plot.getAxis("left").setPen('w')
                self.legend.setLabelTextColor("w")
            except TypeError:
                for channel in range(len(self.plot)):
                    self.plot[channel].getAxis('bottom').setPen('w')
                    self.plot[channel].getAxis('bottom').setTextPen('w')
                    self.plot[channel].getAxis('left').setPen('w')
                    self.plot[channel].getAxis('left').setTextPen('w')
        else:
            self.window.setBackground("w")
            self.legend.setLabelTextColor("r")
            try:
                self.plot.getAxis('bottom').setPen('k')
                self.plot.getAxis("left").setPen('k')
                self.plot.getAxis('bottom').setTextPen('k')
                self.plot.getAxis("left").setTextPen('k')
            except TypeError:
                for channel in range(len(self.plot)):
                    self.plot[channel].getAxis('bottom').setPen('k')
                    self.plot[channel].getAxis('bottom').setTextPen('k')
                    self.plot[channel].getAxis('left').setPen('k')
                    self.plot[channel].getAxis('left').setTextPen('k')

    @QtCore.pyqtSlot()
    def clear(self) -> None:
        self.window.clear()

    @abstractmethod
    def update_data_live(self, data: model.Buffer) -> None:
        ...


class DAQPlots(Plotting):
    def __init__(self):
        Plotting.__init__(self)
        model.daq_signals.clear.connect(self.clear)
        self.name = ""

    @abstractmethod
    def update_data(self, data: pd.DataFrame) -> None:
        ...


class DC(DAQPlots):
    def __init__(self):
        DAQPlots.__init__(self)
        self.curves = [self.plot.plot(pen=pg.mkPen(_MatplotlibColors.BLUE), name="DC CH1"),
                       self.plot.plot(pen=pg.mkPen(_MatplotlibColors.ORANGE), name="DC CH2"),
                       self.plot.plot(pen=pg.mkPen(_MatplotlibColors.GREEN), name="DC CH3")]
        self.plot.setLabel(axis="bottom", text="Time [s]")
        self.plot.setLabel(axis="left", text="Intensity [V]")
        self.name = "DC Plots"
        model.daq_signals.decimation.connect(self.update_data)
        model.daq_signals.decimation_live.connect(self.update_data_live)

    @override
    def update_data(self, data: pd.DataFrame) -> None:
        for channel in range(3):
            try:
                self.curves[channel].setData(data[f"DC CH{channel + 1}"].to_numpy())
            except KeyError:
                self.curves[channel].setData(data[f"PD{channel + 1}"].to_numpy())

    #@override
    def update_data_live(self, data: model.PTIBuffer) -> None:
        for channel in range(3):
            self.curves[channel].setData(data.time, data.dc_values[channel])


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
        model.daq_signals.characterization.connect(self.update_data)
        model.daq_signals.characterization_live.connect(self.update_data_live)

    @override
    def update_data(self, data: pd.DataFrame) -> None:
        for channel in range(3):
            self.curves[channel].setData(data.index, data[f"Amplitude CH{channel + 1}"].to_numpy())

    #@override
    def update_data_live(self, data: model.CharacterisationBuffer) -> None:
        for channel in range(3):
            self.curves[channel].setData(data.time, data.amplitudes[channel])


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
        model.daq_signals.characterization.connect(self.update_data)
        model.daq_signals.characterization_live.connect(self.update_data_live)

    @override
    def update_data(self, data: pd.DataFrame) -> None:
        for channel in range(2):
            self.curves[channel].setData(data.index, data[f"Output Phase CH{channel + 2}"].to_numpy())

    #@override
    def update_data_live(self, data: model.CharacterisationBuffer) -> None:
        for channel in range(2):
            self.curves[channel].setData(data.time, data.output_phases[channel])


class InterferometricPhase(DAQPlots):
    def __init__(self):
        DAQPlots.__init__(self)
        self.curves = self.plot.plot(pen=pg.mkPen(_MatplotlibColors.BLUE))
        self.plot.setLabel(axis="bottom", text="Time [s]")
        self.plot.setLabel(axis="left", text="Interferometric Phase [rad]")
        self.name = "Interferometric Phase"
        model.daq_signals.inversion.connect(self.update_data)
        model.daq_signals.inversion_live.connect(self.update_data_live)

    @override
    def update_data(self, data: pd.DataFrame) -> None:
        self.curves.setData(data["Interferometric Phase"].to_numpy())

    #@override
    def update_data_live(self, data: model.PTIBuffer) -> None:
        self.curves.setData(data.time, data.interferometric_phase)


class Sensitivity(DAQPlots):
    def __init__(self):
        DAQPlots.__init__(self)
        self.curves = [self.plot.plot(pen=pg.mkPen(_MatplotlibColors.BLUE), name="CH1"),
                       self.plot.plot(pen=pg.mkPen(_MatplotlibColors.ORANGE), name="CH2"),
                       self.plot.plot(pen=pg.mkPen(_MatplotlibColors.GREEN), name="CH3")]
        self.plot.setLabel(axis="bottom", text="Time [s]")
        self.plot.setLabel(axis="left", text="Sensitivity [V/rad]")
        self.name = "Sensitivity"
        model.daq_signals.inversion.connect(self.update_data)
        model.daq_signals.inversion_live.connect(self.update_data_live)

    @override
    def update_data(self, data: pd.DataFrame) -> None:
        for channel in range(3):
            self.curves[channel].setData(data[f"Sensitivity CH{channel + 1}"].to_numpy())

    #@override
    def update_data_live(self, data: model.PTIBuffer) -> None:
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
        model.daq_signals.characterization.connect(self.update_data)
        model.daq_signals.characterization_live.connect(self.update_data_live)

    @override
    def update_data(self, data: pd.DataFrame) -> None:
        self.curves[0].setData(data.index, data["Symmetry"].to_numpy())
        self.curves[1].setData(data.index, data["Relative Symmetry"].to_numpy())

    #@override
    def update_data_live(self, data: model.CharacterisationBuffer) -> None:
        self.curves[0].setData(data.time, data.symmetry)
        self.curves[1].setData(data.time, data.relative_symmetry)


class PTISignal(DAQPlots):
    def __init__(self):
        DAQPlots.__init__(self)
        self.curves = {"PTI Signal": self.plot.scatterPlot(pen=pg.mkPen(_MatplotlibColors.BLUE), name="1 s", size=6),
                       "PTI Signal Mean": self.plot.plot(pen=pg.mkPen(_MatplotlibColors.ORANGE), name="60 s Mean")}
        self.plot.setLabel(axis="bottom", text="Time [s]")
        self.plot.setLabel(axis="left", text="PTI Signal [µrad]")
        self.name = "PTI Signal"
        model.daq_signals.inversion.connect(self.update_data)
        model.daq_signals.inversion_live.connect(self.update_data_live)

    @override
    def update_data(self, data: pd.DataFrame) -> None:
        try:
            self.curves["PTI Signal"].setData(data["PTI Signal"].to_numpy())
            self.curves["PTI Signal Mean"].setData(data["PTI Signal 60 s Mean"].to_numpy())
        except KeyError:
            pass

    #@override
    def update_data_live(self, data: model.PTIBuffer, calculate_mean: bool) -> None:
        self.curves["PTI Signal"].setData(data.time, data.pti_signal)
        if calculate_mean:
            self.curves["PTI Signal Mean"].setData(data.time, data.pti_signal_mean)


class PumpLaserCurrent(Plotting):
    def __init__(self):
        Plotting.__init__(self)
        self.curves = self.plot.plot(pen=pg.mkPen(_MatplotlibColors.BLUE))
        self.plot.setLabel(axis="bottom", text="Time [s]")
        self.plot.setLabel(axis="left", text="Current [mA]")
        model.laser_signals.data.connect(self.update_data_live)
        model.laser_signals.clear_pumplaser.connect(self.clear)

    #@override
    def update_data_live(self, data: model.LaserBuffer) -> None:
        self.curves.setData(data.time, data.pump_laser_current)


class ProbeLaserCurrent(Plotting):
    def __init__(self):
        Plotting.__init__(self)
        self.curves = self.plot.plot(pen=pg.mkPen(_MatplotlibColors.BLUE))
        self.plot.setLabel(axis="bottom", text="Time [s]")
        self.plot.setLabel(axis="left", text="Current [mA]")
        model.laser_signals.data.connect(self.update_data_live)
        model.laser_signals.clear_probelaser.connect(self.clear)

    #@override
    def update_data_live(self, data: model.LaserBuffer) -> None:
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
        model.tec_signals[channel].clear_plots.connect(self.clear)
        model.signals.tec_data.connect(self.update_data_live)

    #@override
    def update_data_live(self, data: model.TecBuffer) -> None:
        self.curves[TecTemperature.SET_POINT].setData(data.time, data.set_point[self.laser])
        self.curves[TecTemperature.MEASURED].setData(data.time, data.actual_value[self.laser])
