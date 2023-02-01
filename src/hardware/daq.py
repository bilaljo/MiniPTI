import itertools
import logging
import queue
import threading
from collections import deque
from dataclasses import dataclass
from typing import Sequence

from fastcrc import crc16

import hardware.driver


@dataclass
class Data:
    ref_signal: queue.Queue | deque | Sequence
    ac_coupled: queue.Queue | deque | Sequence
    dc_coupled: queue.Queue | deque | Sequence


class Driver(hardware.driver.Serial):
    """
    This class provides an interface for receiving data from the serial port of a USB connected DAQ system.
    The data is accordingly to a defined protocol encoded and build into a packages of samples.
    """
    PACKAGE_SIZE_START_INDEX = 2
    PACKAGE_SIZE_END_INDEX = 10
    CRC_START_INDEX = 4
    PACKAGE_SIZE = 4110
    WORD_SIZE = 32

    ID = b"0001"
    NAME = "Driver"

    WAIT_TIME_TIMEOUT = 100e-3  # 100 ms
    WAIT_TIME_DATA = 10e-3  # 10 ms

    CHANNELS = 3
    REF_PERIOD = 100
    NUMBER_OF_SAMPLES = 8000

    def __init__(self):
        hardware.driver.Serial.__init__(self)
        self.package_data = Data(queue.Queue(maxsize=Driver.QUEUE_SIZE), queue.Queue(maxsize=Driver.QUEUE_SIZE),
                                 queue.Queue(maxsize=Driver.QUEUE_SIZE))
        self.buffers = Data(deque(), [deque(), deque(), deque()], [deque(), deque(), deque()])
        self.buffers.dc_coupled = [deque(), deque(), deque()]
        self.buffer = b""
        self.running = threading.Event()
        self.sample_numbers = deque(maxlen=2)
        self.receive_daq = None
        self.encode_daq = None
        self.synchronize = True
        self.ready = False

    @property
    def device_id(self):
        return Driver.ID

    @property
    def device_name(self):
        return Driver.NAME

    @property
    def ref_signal(self):
        return self.package_data.ref_signal.get(block=True)

    @property
    def dc_coupled(self):
        return self.package_data.dc_coupled.get(block=True)

    @property
    def ac_coupled(self):
        return self.package_data.ac_coupled.get(block=True)

    def __call__(self):
        self.running.set()
        self.__reset()
        try:
            while self.running.is_set():
                self.encode_data()
                if len(self.buffers.ref_signal) >= Driver.NUMBER_OF_SAMPLES:
                    self.__build_sample_package()
        finally:
            self.close()

    @staticmethod
    def __binary_to_2_complement(byte, byte_length):
        if byte & (1 << (byte_length - 1)):
            return byte - 2 ** byte_length
        return byte

    @staticmethod
    def __encode(raw_data):
        """
        A block of data has the following structure:
        Ref, DC 1, DC 2, DC 3, DC, 4 AC 1, AC 2, AC 3, AC 4
        These byte words are 4 bytes wide and hex decimal decoded. These big byte word of size 32 repeats periodically.
        It starts with below the first 10 bytes (meta information) and ends before the last 4 bytes (crc checksum).
        """
        raw_data = raw_data[Driver.PACKAGE_SIZE_END_INDEX:Driver.PACKAGE_SIZE - Driver.CRC_START_INDEX]
        ref = []
        ac = [[], [], []]
        dc = [[], [], [], []]
        for i in range(0, len(raw_data), Driver.WORD_SIZE):
            ref.append(int(raw_data[i:i + 4], 16))
            # AC signed
            ac_value = Driver.__binary_to_2_complement(int(raw_data[i + 4:i + 8], base=16), 16)
            ac[0].append(ac_value)
            ac_value = Driver.__binary_to_2_complement(int(raw_data[i + 8:i + 12], base=16), 16)
            ac[1].append(ac_value)
            ac_value = Driver.__binary_to_2_complement(int(raw_data[i + 12:i + 16], base=16), 16)
            ac[2].append(ac_value)
            # DC unsigned
            dc[0].append(int(raw_data[i + 16:i + 20], base=16))
            dc[1].append(int(raw_data[i + 20:i + 24], base=16))
            dc[2].append(int(raw_data[i + 24:i + 28], base=16))
            dc[3].append(int(raw_data[i + 28:i + 32], base=16))
        return ref, ac, dc

    def __reset(self):
        self.synchronize = True
        self.buffer = b""
        self.buffers.ref_signal = deque()
        self.buffers.dc_coupled = [deque(), deque(), deque()]
        self.buffers.ac_coupled = [deque(), deque(), deque()]

    def encode_data(self):
        """
        The data is encoded according to the following protocol:
            - The first two bytes describes the send command
            - Byte 2 up to 10 describe the package number of the send package
            - Byte 10 to 32 contain the data as period sequence of blocks in hex decimal
            - The last 4 bytes represent a CRC checksum in hex decimal
        """
        self.buffer += self.received_data.get(block=True)
        if len(self.buffer) >= Driver.PACKAGE_SIZE + len(Driver.TERMINATION_SYMBOL):
            splitted_data = self.buffer.split(Driver.TERMINATION_SYMBOL)
            self.buffer = b""
            for data in splitted_data:
                if len(data) != Driver.PACKAGE_SIZE:  # Broken package with missing beginning
                    continue
                crc_calculated = crc16.arc(data[:-Driver.CRC_START_INDEX])
                crc_received = int(data[-Driver.CRC_START_INDEX:], base=16)
                if crc_calculated != crc_received:  # Corrupted data
                    logging.error(f"CRC value isn't equal to transmitted. Got {crc_received} "
                                  f"instead of {crc_calculated}.")
                    self.synchronize = True  # The data is not trustful, and it should be waited for new
                    self.sample_numbers.popleft()
                    self.sample_numbers.popleft()
                    self.__reset()
                    continue
                self.sample_numbers.append(data[Driver.PACKAGE_SIZE_START_INDEX:Driver.PACKAGE_SIZE_END_INDEX])
                if len(self.sample_numbers) > 1:
                    package_difference = int(self.sample_numbers[1], base=16) - int(self.sample_numbers[0], base=16)
                    if package_difference != 1:
                        logging.error(f"Missing {package_difference} packages.")
                        logging.info("Start resynchronisation.")
                        self.sample_numbers.popleft()
                        self.__reset()
                ref_signal, ac_coupled, dc_coupled = Driver.__encode(data)
                self.synchronize = False
                if self.synchronize:
                    while sum(itertools.islice(ref_signal, Driver.REF_PERIOD // 2)):
                        ref_signal.pop(0)
                        for channel in range(Driver.CHANNELS):
                            ac_coupled[channel].pop(0)
                            dc_coupled[channel].pop(0)
                    if len(ref_signal) < Driver.REF_PERIOD // 2:
                        continue
                    self.synchronize = False
                else:
                    self.buffers.ref_signal.extend(ref_signal)
                    for channel in range(Driver.CHANNELS):
                        self.buffers.dc_coupled[channel].extend(dc_coupled[channel])
                        self.buffers.ac_coupled[channel].extend(ac_coupled[channel])
            if splitted_data[-1]:  # Data without termination symbol
                self.buffer = splitted_data[-1]

    def __build_sample_package(self):
        """
        Creates a package of samples that represents approximately 1 s data. It contains 8000 samples.
        """
        if len(self.buffers.ref_signal) >= Driver.NUMBER_OF_SAMPLES:
            if sum(itertools.islice(self.buffers.ref_signal, Driver.REF_PERIOD // 2)):
                logging.error("Phase shift in reference signal detected.")
                logging.info("Start resynchronisation for next package.")
                self.sample_numbers.popleft()
                self.synchronize = True
                return
            self.package_data.ref_signal.put([self.buffers.ref_signal.popleft() for _ in
                                              range(Driver.NUMBER_OF_SAMPLES)])
            dc_package = [[], [], []]
            ac_package = [[], [], []]
            for _ in itertools.repeat(None, Driver.NUMBER_OF_SAMPLES):
                for channel in range(Driver.CHANNELS):
                    dc_package[channel].append(self.buffers.dc_coupled[channel].popleft())
                    ac_package[channel].append(self.buffers.ac_coupled[channel].popleft())
            self.package_data.dc_coupled.put(dc_package)
            self.package_data.ac_coupled.put(ac_package)
