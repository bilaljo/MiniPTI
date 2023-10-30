import itertools
from collections import deque

from overrides import override

from minipti import algorithm


class Buffer:
    """
    The buffer contains the queues for incoming data and the timer for them.
    """
    QUEUE_SIZE = 100

    def __init__(self):
        self.time_counter = itertools.count()
        self.time = deque(maxlen=Buffer.QUEUE_SIZE)

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
                    setattr(self, member, deque(maxlen=Buffer.QUEUE_SIZE))


class PTI(Buffer):
    MEAN_SIZE = 60
    CHANNELS = 3

    def __init__(self):
        Buffer.__init__(self)
        self._pti_signal = deque(maxlen=Buffer.QUEUE_SIZE)
        self._pti_signal_mean = deque(maxlen=Buffer.QUEUE_SIZE)
        self._pti_signal_mean_queue = deque(maxlen=PTIBuffer.MEAN_SIZE)

    @property
    @override
    def is_empty(self) -> bool:
        return len(self._pti_signal) == 0

    def append(self, pti: PTI, average_period: int) -> None:
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


class Interferometer(Buffer):
    CHANNELS = 3

    def __init__(self):
        Buffer.__init__(self)
        self._dc_values = [deque(maxlen=Buffer.QUEUE_SIZE) for _ in range(PTI.CHANNELS)]
        self._interferometric_phase = deque(maxlen=Buffer.QUEUE_SIZE)
        self._sensitivity = [deque(maxlen=Buffer.QUEUE_SIZE) for _ in range(PTI.CHANNELS)]

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
        for i in range(InterferometerBuffer.CHANNELS):
            self._dc_values[i].append(interferometer.intensities[i])
            self._sensitivity[i].append(interferometer.sensitivity[i])
        self._interferometric_phase.append(interferometer.phase)
        self.time.append(next(self.time_counter))


class Characterisation(Buffer):
    CHANNELS = 3

    def __init__(self):
        Buffer.__init__(self)
        # The first channel has always the phase 0 by definition hence it is not needed.
        self._output_phases = [deque(maxlen=Buffer.QUEUE_SIZE) for _ in range(self.CHANNELS - 1)]
        self._amplitudes = [deque(maxlen=Buffer.QUEUE_SIZE) for _ in range(Characterisation.CHANNELS)]
        self._symmetry = deque(maxlen=Buffer.QUEUE_SIZE)
        self._relative_symmetry = deque(maxlen=Buffer.QUEUE_SIZE)

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
