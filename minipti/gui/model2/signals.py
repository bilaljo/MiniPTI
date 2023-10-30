from dataclasses import dataclass

from PyQt5 import QtCore

from minipti import hardware


@dataclass(init=False, frozen=True)
class Laser(QtCore.QObject):
    photo_gain = QtCore.pyqtSignal(int)
    current_probe_laser = QtCore.pyqtSignal(int, float)
    max_current_probe_laser = QtCore.pyqtSignal(float)
    probe_laser_mode = QtCore.pyqtSignal(int)
    laser_voltage = QtCore.pyqtSignal(int, float)
    current_dac = QtCore.pyqtSignal(int, int)
    matrix_dac = QtCore.pyqtSignal(int, list)
    data = QtCore.pyqtSignal(Buffer)
    data_display = QtCore.pyqtSignal(hardware.laser.Data)
    pump_laser_enabled = QtCore.pyqtSignal(bool)
    probe_laser_enabled = QtCore.pyqtSignal(bool)

    def __init__(self):
        QtCore.QObject.__init__(self)


@dataclass(init=False, frozen=True)
class Tec(QtCore.QObject):
    p_gain = QtCore.pyqtSignal(float)
    d_gain = QtCore.pyqtSignal(float)
    i_gain = QtCore.pyqtSignal(float)
    setpoint_temperature = QtCore.pyqtSignal(float)
    loop_time = QtCore.pyqtSignal(int)
    max_power = QtCore.pyqtSignal(float)
    enabled = QtCore.pyqtSignal(bool)

    def __init__(self):
        QtCore.QObject.__init__(self)


@dataclass(init=False, frozen=True)
class Valve(QtCore.QObject):
    bypass = QtCore.pyqtSignal(bool)
    period = QtCore.pyqtSignal(int)
    duty_cycle = QtCore.pyqtSignal(int)
    automatic_switch = QtCore.pyqtSignal(bool)

    def __init__(self):
        QtCore.QObject.__init__(self)


@dataclass(init=False, frozen=True)
class DAQ(QtCore.QObject):
    decimation = QtCore.pyqtSignal(Buffer)
    inversion = QtCore.pyqtSignal(Buffer, bool)
    interferometry = QtCore.pyqtSignal(Buffer)
    characterization = QtCore.pyqtSignal(Buffer)
    samples_changed = QtCore.pyqtSignal(int)
    running = QtCore.pyqtSignal(bool)
    clear = QtCore.pyqtSignal()

    def __init__(self):
        QtCore.QObject.__init__(self)


