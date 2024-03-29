from collections import deque
from dataclasses import dataclass
from typing import Final

import numpy as np
import pandas as pd
from PyQt5 import QtCore

from minipti import hardware, algorithm
from minipti.gui.model import buffer


@dataclass(init=False, frozen=True)
class _Calculation(QtCore.QObject):
    settings_pti = QtCore.pyqtSignal()
    settings_interferometer = QtCore.pyqtSignal(algorithm.interferometry.CharacteristicParameter)
    dc_signals = QtCore.pyqtSignal(np.ndarray)
    inversion = QtCore.pyqtSignal(dict)
    characterization = QtCore.pyqtSignal(pd.DataFrame)
    interferometric_phase = QtCore.pyqtSignal(np.ndarray)
    lock_in_phases = QtCore.pyqtSignal(np.ndarray)
    response_phases = QtCore.pyqtSignal(np.ndarray)
    settings_path_changed = QtCore.pyqtSignal(str)

    def __init__(self):
        QtCore.QObject.__init__(self)


@dataclass(init=False, frozen=True)
class _GeneralPurporse(QtCore.QObject):
    logging_update = QtCore.pyqtSignal(deque)
    destination_folder_changed = QtCore.pyqtSignal(str)
    theme_changed = QtCore.pyqtSignal(str)
    tec_data = QtCore.pyqtSignal(buffer.Tec)
    tec_data_display = QtCore.pyqtSignal(hardware.tec.Data)
    progess_bar = QtCore.pyqtSignal(int)
    progess_bar_start = QtCore.pyqtSignal()
    progess_bar_stop = QtCore.pyqtSignal()

    def __init__(self):
        QtCore.QObject.__init__(self)


@dataclass(init=False, frozen=True)
class _Laser(QtCore.QObject):
    photo_gain = QtCore.pyqtSignal(int)
    current_probe_laser = QtCore.pyqtSignal(int, float)
    max_current_probe_laser = QtCore.pyqtSignal(float)
    probe_laser_mode = QtCore.pyqtSignal(int)
    laser_voltage = QtCore.pyqtSignal(int, float)
    current_dac = QtCore.pyqtSignal(int, int)
    matrix_dac = QtCore.pyqtSignal(int, list)
    data = QtCore.pyqtSignal(buffer.BaseClass)
    data_display = QtCore.pyqtSignal(hardware.laser.Data)
    pump_laser_enabled = QtCore.pyqtSignal(bool)
    probe_laser_enabled = QtCore.pyqtSignal(bool)

    def __init__(self):
        QtCore.QObject.__init__(self)


@dataclass(init=False, frozen=True)
class _Tec(QtCore.QObject):
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
class _Valve(QtCore.QObject):
    bypass = QtCore.pyqtSignal(bool)
    period = QtCore.pyqtSignal(int)
    duty_cycle = QtCore.pyqtSignal(int)
    automatic_switch = QtCore.pyqtSignal(bool)

    def __init__(self):
        QtCore.QObject.__init__(self)


@dataclass(init=False, frozen=True)
class _Pump(QtCore.QObject):
    flow_Rate = QtCore.pyqtSignal(float)
    enabled = QtCore.pyqtSignal(bool)

    def __init__(self):
        QtCore.QObject.__init__(self)


@dataclass(init=False, frozen=True)
class _DAQ(QtCore.QObject):
    decimation = QtCore.pyqtSignal(buffer.BaseClass)
    inversion = QtCore.pyqtSignal(buffer.BaseClass)
    interferometry = QtCore.pyqtSignal(buffer.BaseClass)
    characterization = QtCore.pyqtSignal(buffer.BaseClass)
    samples_changed = QtCore.pyqtSignal(int)
    running = QtCore.pyqtSignal(bool)
    clear = QtCore.pyqtSignal()

    def __init__(self):
        QtCore.QObject.__init__(self)


@dataclass(init=False, frozen=True)
class _BMS(QtCore.QObject):
    battery_state = QtCore.pyqtSignal(bool, float)
    battery_data = QtCore.pyqtSignal(float, float, float, float, float, float)

    def __init__(self):
        QtCore.QObject.__init__(self)


LASER: Final = _Laser()
TEC: Final = [_Tec(), _Tec()]
DAQ: Final = _DAQ()
VALVE: Final = _Valve()
CALCULATION: Final = _Calculation()
GENERAL_PURPORSE: Final = _GeneralPurporse()
PUMP: Final = _Pump()
BMS: Final = _BMS()
