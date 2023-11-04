import itertools
import typing
from abc import abstractmethod
from collections import deque

import numpy as np
from overrides import override

from minipti import algorithm, hardware
from minipti.gui.model import serial_devices
from minipti.gui.model import processing


class BaseClass:
    """
    The buffer contains the queues for incoming data and the timer for them.
    """
    QUEUE_SIZE = 100

    def __init__(self):
        self.time_counter = itertools.count()
        self.time = deque(maxlen=BaseClass.QUEUE_SIZE)

    def __getitem__(self, key):
        return getattr(self, key.casefold().replace(" ", "_"))

    def __setitem__(self, key, value) -> None:
        setattr(self, key.casefold().replace(" ", "_"), value)

    def __iter__(self):
        for member in dir(self):
            if not callable(getattr(self, member)) and not member.startswith("__") and member != "time_counter":
                yield getattr(self, member)

    @property
    @abstractmethod
    def is_empty(self) -> bool:
        ...

    @abstractmethod
    def append(self, *args: typing.Any) -> None:
        ...

    def clear(self) -> None:
        for member in dir(self):
            if not callable(getattr(self, member)) and not member.startswith("__"):
                if member == self.time_counter:
                    self.time_counter = itertools.count()  # Reset counter
                else:
                    setattr(self, member, deque(maxlen=BaseClass.QUEUE_SIZE))


class PTI(BaseClass):
    MEAN_SIZE = 60
    CHANNELS = 3

    def __init__(self):
        BaseClass.__init__(self)
        self._pti_signal = deque(maxlen=BaseClass.QUEUE_SIZE)
        self._pti_signal_mean = deque(maxlen=BaseClass.QUEUE_SIZE)
        self._pti_signal_mean_queue = deque(maxlen=PTI.MEAN_SIZE)

    @property
    @override
    def is_empty(self) -> bool:
        return len(self._pti_signal) == 0

    def append(self, pti: processing.PTI, average_period: int) -> None:
        self._pti_signal.append(pti.inversion.pti_signal)
        self._pti_signal_mean_queue.append(pti.inversion.pti_signal)
        time_scaler: float = algorithm.pti.Decimation.REF_PERIOD * algorithm.pti.Decimation.SAMPLE_PERIOD
        if average_period / time_scaler == 1:
            self._pti_signal_mean.append(np.mean(np.array(self._pti_signal_mean_queue)))
        self.time.append(next(self.time_counter) * average_period / time_scaler)

    @property
    def pti_signal(self) -> deque:
        return self._pti_signal

    @property
    def pti_signal_mean(self) -> deque:
        return self._pti_signal_mean


class Interferometer(BaseClass):
    CHANNELS = 3

    def __init__(self):
        BaseClass.__init__(self)
        self._dc_values = [deque(maxlen=BaseClass.QUEUE_SIZE) for _ in range(PTI.CHANNELS)]
        self._interferometric_phase = deque(maxlen=BaseClass.QUEUE_SIZE)
        self._sensitivity = [deque(maxlen=BaseClass.QUEUE_SIZE) for _ in range(PTI.CHANNELS)]

    @property
    @override
    def is_empty(self) -> bool:
        return len(self._interferometric_phase) == 0

    @property
    def dc_values(self) -> list[deque]:
        return self._dc_values

    @property
    def interferometric_phase(self) -> deque:
        return self._interferometric_phase

    @property
    def sensitivity(self) -> list[deque]:
        return self._sensitivity

    def append(self, interferometer: algorithm.interferometry.Interferometer) -> None:
        for i in range(Interferometer.CHANNELS):
            self._dc_values[i].append(interferometer.intensities[i])
            self._sensitivity[i].append(interferometer.sensitivity[i])
        self._interferometric_phase.append(interferometer.phase)
        self.time.append(next(self.time_counter))


class Characterisation(BaseClass):
    CHANNELS = 3

    def __init__(self):
        BaseClass.__init__(self)
        # The first channel has always the phase 0 by definition hence it is not needed.
        self._output_phases = [deque(maxlen=BaseClass.QUEUE_SIZE) for _ in range(self.CHANNELS - 1)]
        self._amplitudes = [deque(maxlen=BaseClass.QUEUE_SIZE) for _ in range(Characterisation.CHANNELS)]
        self._symmetry = deque(maxlen=BaseClass.QUEUE_SIZE)
        self._relative_symmetry = deque(maxlen=BaseClass.QUEUE_SIZE)

    @property
    def is_empty(self) -> bool:
        return len(self._output_phases) == 0

    def append(self, characterization: algorithm.interferometry.Characterization,
               interferometer: algorithm.interferometry.Interferometer) -> None:
        for i in range(3):
            self._amplitudes[i].append(interferometer.amplitudes[i])
        for i in range(2):
            self._output_phases[i].append(interferometer.output_phases[i + 1])
        self.symmetry.append(interferometer.symmetry.absolute)
        self.relative_symmetry.append(interferometer.symmetry.relative)
        self.time.append(characterization.time_stamp)

    @property
    def output_phases(self) -> list[deque]:
        return self._output_phases

    @property
    def amplitudes(self) -> list[deque]:
        return self._amplitudes

    @property
    def symmetry(self) -> deque:
        return self._symmetry

    @property
    def relative_symmetry(self) -> deque:
        return self._relative_symmetry


class Laser(BaseClass):
    def __init__(self):
        BaseClass.__init__(self)
        self._pump_laser_voltage = deque(maxlen=BaseClass.QUEUE_SIZE)
        self._pump_laser_current = deque(maxlen=BaseClass.QUEUE_SIZE)
        self._probe_laser_current = deque(maxlen=BaseClass.QUEUE_SIZE)

    @property
    def is_empty(self) -> bool:
        return len(self._pump_laser_voltage) == 0

    def append(self, laser_data: hardware.laser.Data) -> None:
        self.time.append(next(self.time_counter) / 10)
        self._pump_laser_voltage.append(laser_data.high_power_laser_voltage)
        self.pump_laser_current.append(laser_data.high_power_laser_current)
        self.probe_laser_current.append(laser_data.low_power_laser_current)

    @property
    def pump_laser_voltage(self) -> deque:
        return self._pump_laser_voltage

    @property
    def pump_laser_current(self) -> deque:
        return self._pump_laser_current

    @property
    def probe_laser_current(self) -> deque:
        return self._probe_laser_current


class Tec(BaseClass):
    def __init__(self):
        BaseClass.__init__(self)
        self._set_point: list[deque] = [deque(maxlen=BaseClass.QUEUE_SIZE), deque(maxlen=BaseClass.QUEUE_SIZE)]
        self._actual_value: list[deque] = [deque(maxlen=BaseClass.QUEUE_SIZE), deque(maxlen=BaseClass.QUEUE_SIZE)]

    @property
    def is_empty(self) -> bool:
        return len(self._set_point[0]) == 0

    def append(self, tec_data: hardware.tec.Data) -> None:
        self._set_point[serial_devices.Tec.PUMP_LASER].append(
            tec_data.set_point[serial_devices.Tec.PUMP_LASER])
        self._set_point[serial_devices.Tec.PROBE_LASER].append(
            tec_data.set_point[serial_devices.Tec.PROBE_LASER])
        self._actual_value[serial_devices.Tec.PUMP_LASER].append(
            tec_data.actual_temperature[serial_devices.Tec.PUMP_LASER])
        self._actual_value[serial_devices.Tec.PROBE_LASER].append(
            tec_data.actual_temperature[serial_devices.Tec.PROBE_LASER])
        self.time.append(next(self.time_counter))

    @property
    def set_point(self) -> list[deque]:
        return self._set_point

    @property
    def actual_value(self) -> list[deque]:
        return self._actual_value
