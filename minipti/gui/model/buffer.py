import itertools
import typing
from abc import abstractmethod
from collections import deque

import numpy as np
from overrides import override

from minipti import algorithm, hardware


class BaseClass:
    """
    The buffer contains the queues for incoming data and the timer for them.
    """
    QUEUE_SIZE = 100

    def __init__(self):
        self.time_counter = itertools.count()
        self.time = deque(maxlen=BaseClass.QUEUE_SIZE)

    @property
    @abstractmethod
    def is_empty(self) -> bool:
        ...

    @abstractmethod
    def append(self, *args: typing.Any) -> None:
        ...


class _DAQ(BaseClass):
    CHANNELS = 3

    def __init__(self):
        BaseClass.__init__(self)
        # signals.DAQ.clear.connect(self.clear)

    @abstractmethod
    def clear(self) -> None:
        """
        Resets all buffers.
        """


class PTI(_DAQ):
    MEAN_SIZE = 60

    def __init__(self):
        _DAQ.__init__(self)
        self._pti_signal = deque(maxlen=BaseClass.QUEUE_SIZE)
        self._pti_signal_mean = deque(maxlen=BaseClass.QUEUE_SIZE)
        self._pti_signal_mean_queue = deque(maxlen=PTI.MEAN_SIZE)

    @property
    @override
    def is_empty(self) -> bool:
        return len(self._pti_signal) == 0

    def append(self, pti, average_period: int) -> None:
        self._pti_signal.append(pti.inversion.pti_signal)
        self._pti_signal_mean_queue.append(pti.inversion.pti_signal)
        if average_period == algorithm.pti.Decimation.SAMPLE_PERIOD:
            self._pti_signal_mean.append(np.mean(np.array(self._pti_signal_mean_queue)))
        time_scaler = average_period / algorithm.pti.Decimation.SAMPLE_PERIOD
        self.time.append(next(self.time_counter) * time_scaler)

    @property
    def pti_signal(self) -> deque[float]:
        return self._pti_signal

    @property
    def pti_signal_mean(self) -> deque[float]:
        return self._pti_signal_mean

    @override
    def clear(self) -> None:
        self.time_counter = itertools.count()
        self.time = deque(maxlen=BaseClass.QUEUE_SIZE)
        self._pti_signal = deque(maxlen=BaseClass.QUEUE_SIZE)
        self._pti_signal_mean = deque(maxlen=BaseClass.QUEUE_SIZE)
        self._pti_signal_mean_queue = deque(maxlen=PTI.MEAN_SIZE)


class Interferometer(_DAQ):
    def __init__(self):
        _DAQ.__init__(self)
        self._dc_values = [deque(maxlen=BaseClass.QUEUE_SIZE) for _ in range(PTI.CHANNELS)]
        self._interferometric_phase = deque(maxlen=BaseClass.QUEUE_SIZE)
        self._sensitivity = [deque(maxlen=BaseClass.QUEUE_SIZE) for _ in range(PTI.CHANNELS)]

    @property
    @override
    def is_empty(self) -> bool:
        return len(self._interferometric_phase) == 0

    @property
    def dc_values(self) -> list[deque[float]]:
        return self._dc_values

    @property
    def interferometric_phase(self) -> deque[float]:
        return self._interferometric_phase

    @property
    def sensitivity(self) -> list[deque[float]]:
        return self._sensitivity

    def append(self, interferometer: algorithm.interferometry.Interferometer) -> None:
        for i in range(Interferometer.CHANNELS):
            self._dc_values[i].append(interferometer.intensities[i])
            self._sensitivity[i].append(interferometer.sensitivity[i])
        self._interferometric_phase.append(interferometer.phase)
        self.time.append(next(self.time_counter))

    @override
    def clear(self) -> None:
        self.time_counter = itertools.count()
        self.time = deque(maxlen=BaseClass.QUEUE_SIZE)
        self._dc_values = [deque(maxlen=BaseClass.QUEUE_SIZE) for _ in range(PTI.CHANNELS)]
        self._interferometric_phase = deque(maxlen=BaseClass.QUEUE_SIZE)
        self._sensitivity = [deque(maxlen=BaseClass.QUEUE_SIZE) for _ in range(PTI.CHANNELS)]


class Characterisation(_DAQ):
    def __init__(self):
        _DAQ.__init__(self)
        # The first channel has always the phase 0 by definition hence it is not needed.
        self._output_phases = [deque(maxlen=BaseClass.QUEUE_SIZE) for _ in range(_DAQ.CHANNELS - 1)]
        self._amplitudes = [deque(maxlen=BaseClass.QUEUE_SIZE) for _ in range(_DAQ.CHANNELS)]
        self._symmetry = deque(maxlen=BaseClass.QUEUE_SIZE)
        self._relative_symmetry = deque(maxlen=BaseClass.QUEUE_SIZE)

    @property
    def is_empty(self) -> bool:
        return len(self._output_phases) == 0

    def append(self, characterization: algorithm.interferometry.Characterization) -> None:
        for i in range(3):
            self._amplitudes[i].append(characterization.interferometer.amplitudes[i])
        for i in range(2):
            self._output_phases[i].append(characterization.interferometer.output_phases[i + 1])
        self.symmetry.append(characterization.interferometer.symmetry.absolute)
        self.relative_symmetry.append(characterization.interferometer.symmetry.relative)
        self.time.append(characterization.time_stamp)

    @property
    def output_phases(self) -> list[deque[float]]:
        return self._output_phases

    @property
    def amplitudes(self) -> list[deque[float]]:
        return self._amplitudes

    @property
    def symmetry(self) -> deque[float]:
        return self._symmetry

    @property
    def relative_symmetry(self) -> deque[float]:
        return self._relative_symmetry

    def clear(self) -> None:
        self.time_counter = itertools.count()
        self.time = deque(maxlen=BaseClass.QUEUE_SIZE)
        self._output_phases = [deque(maxlen=BaseClass.QUEUE_SIZE) for _ in range(_DAQ.CHANNELS - 1)]
        self._amplitudes = [deque(maxlen=BaseClass.QUEUE_SIZE) for _ in range(_DAQ.CHANNELS)]
        self._symmetry = deque(maxlen=BaseClass.QUEUE_SIZE)
        self._relative_symmetry = deque(maxlen=BaseClass.QUEUE_SIZE)


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
    def pump_laser_voltage(self) -> deque[float]:
        return self._pump_laser_voltage

    @property
    def pump_laser_current(self) -> deque[float]:
        return self._pump_laser_current

    @property
    def probe_laser_current(self) -> deque[float]:
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
        for channel in range(2):
            self._set_point[channel].append(tec_data.set_point[channel])
            self._actual_value[channel].append(tec_data.actual_temperature[channel])
        self.time.append(next(self.time_counter))

    @property
    def set_point(self) -> list[deque[float]]:
        return self._set_point

    @property
    def actual_value(self) -> list[deque[float]]:
        return self._actual_value
