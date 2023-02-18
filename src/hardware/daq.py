import itertools
import logging
import queue
import threading
from collections import deque
from dataclasses import dataclass
from typing import Sequence

from fastcrc import crc16

import hardware.serial


@dataclass
class Data:
    ref_signal: queue.Queue | deque | Sequence
    ac_coupled: queue.Queue | deque | Sequence
    dc_coupled: queue.Queue | deque | Sequence


class Driver(hardware.serial.Driver):
    """
    This class provides an interface for receiving data from the serial port of a USB connected DAQ system.
    The data is accordingly to a defined protocol encoded and build into a packages of samples.
    """
    _PACKAGE_SIZE_START_INDEX = 2
    _PACKAGE_SIZE_END_INDEX = 10
    _CRC_START_INDEX = 4
    _PACKAGE_SIZE = 4110
    _WORD_SIZE = 32

    ID = "0001"
    NAME = "DAQ"

    _CHANNELS = 3
    REF_PERIOD = 100
    NUMBER_OF_SAMPLES = 8000

    def __init__(self):
        hardware.serial.Driver.__init__(self)
        self.connected = threading.Event()
        self._package_data = Data(queue.Queue(maxsize=Driver._QUEUE_SIZE), queue.Queue(maxsize=Driver._QUEUE_SIZE),
                                  queue.Queue(maxsize=Driver._QUEUE_SIZE))
        self._encoded_buffer = Data(deque(), [deque(), deque(), deque()], [deque(), deque(), deque()])
        self._received_buffer = ""
        self._sample_numbers = deque(maxlen=2)
        self._synchronize = True

    @property
    def device_id(self):
        return Driver.ID

    @property
    def device_name(self):
        return Driver.NAME

    @property
    def ref_signal(self):
        return self._package_data.ref_signal.get(block=True)

    @property
    def dc_coupled(self):
        return self._package_data.dc_coupled.get(block=True)

    @property
    def ac_coupled(self):
        return self._package_data.ac_coupled.get(block=True)

    @staticmethod
    def _binary_to_2_complement(number, byte_length):
        if number & (1 << (byte_length - 1)):
            return number - (1 << byte_length)
        return number

    @staticmethod
    def _encode(raw_data):
        """
        A block of data has the following structure:
        Ref, DC 1, DC 2, DC 3, DC, 4 AC 1, AC 2, AC 3, AC 4
        These byte words are 4 bytes wide and hex decimal decoded. These big byte word of size 32 repeats periodically.
        It starts with below the first 10 bytes (meta information) and ends before the last 4 bytes (crc checksum).
        """
        raw_data = raw_data[Driver._PACKAGE_SIZE_END_INDEX:Driver._PACKAGE_SIZE - Driver._CRC_START_INDEX]
        ref = []
        ac = [[], [], []]
        dc = [[], [], [], []]
        for i in range(0, len(raw_data), Driver._WORD_SIZE):
            ref.append(int(raw_data[i:i + 4], 16))
            # AC signed
            ac_value = Driver._binary_to_2_complement(int(raw_data[i + 4:i + 8], base=16), 16)
            ac[0].append(ac_value)
            ac_value = Driver._binary_to_2_complement(int(raw_data[i + 8:i + 12], base=16), 16)
            ac[1].append(ac_value)
            ac_value = Driver._binary_to_2_complement(int(raw_data[i + 12:i + 16], base=16), 16)
            ac[2].append(ac_value)
            # DC unsigned
            dc[0].append(int(raw_data[i + 16:i + 20], base=16))
            dc[1].append(int(raw_data[i + 20:i + 24], base=16))
            dc[2].append(int(raw_data[i + 24:i + 28], base=16))
            dc[3].append(int(raw_data[i + 28:i + 32], base=16))
        return ref, ac, dc

    def _reset(self):
        self._synchronize = True
        self._received_buffer = ""
        self._encoded_buffer.ref_signal = deque()
        self._encoded_buffer.dc_coupled = [deque(), deque(), deque()]
        self._encoded_buffer.ac_coupled = [deque(), deque(), deque()]

    def _encode_data(self):
        """
        The data is encoded according to the following protocol:
            - The first two bytes describes the send command
            - Byte 2 up to 10 describe the package number of the send package
            - Byte 10 to 32 contain the data as period sequence of blocks in hex decimal
            - The last 4 bytes represent a CRC checksum in hex decimal
        """
        print("called")
        self._received_buffer += self.received_data.get(block=True)
        print(self._received_buffer)
        if len(self._received_buffer) >= Driver._PACKAGE_SIZE + len(Driver.TERMINATION_SYMBOL):
            split_data = self._received_buffer.split(Driver.TERMINATION_SYMBOL)
            self._received_buffer = ""
            for data in split_data:
                if data[0] == "G":
                    self.ready_write.set()
                if len(data) != Driver._PACKAGE_SIZE:  # Broken package with missing beginning
                    continue
                crc_calculated = crc16.arc(data[:-Driver._CRC_START_INDEX].encode())
                crc_received = int(data[-Driver._CRC_START_INDEX:], base=16)
                if crc_calculated != crc_received:  # Corrupted data
                    logging.error(f"CRC value isn't equal to transmitted. Got {crc_received} "
                                  f"instead of {crc_calculated}.")
                    self._synchronize = True
                    self._sample_numbers.popleft()
                    self._sample_numbers.popleft()
                    self._reset()  # The data is not trustful, and it should be waited for new
                    continue
                self._sample_numbers.append(data[Driver._PACKAGE_SIZE_START_INDEX:Driver._PACKAGE_SIZE_END_INDEX])
                if len(self._sample_numbers) > 1:
                    package_difference = int(self._sample_numbers[1], base=16) - int(self._sample_numbers[0], base=16)
                    if package_difference != 1:
                        logging.error(f"Missing {package_difference} packages.")
                        logging.info("Start resynchronisation.")
                        self._sample_numbers.popleft()
                        self._reset()
                ref_signal, ac_coupled, dc_coupled = Driver._encode(data)
                if self._synchronize:
                    while sum(itertools.islice(ref_signal, Driver.REF_PERIOD // 2)):
                        ref_signal.pop(0)
                        for channel in range(Driver._CHANNELS):
                            ac_coupled[channel].pop(0)
                            dc_coupled[channel].pop(0)
                    if len(ref_signal) < Driver.REF_PERIOD // 2:
                        continue
                    self._synchronize = False
                else:
                    self._encoded_buffer.ref_signal.extend(ref_signal)
                    for channel in range(Driver._CHANNELS):
                        self._encoded_buffer.dc_coupled[channel].extend(dc_coupled[channel])
                        self._encoded_buffer.ac_coupled[channel].extend(ac_coupled[channel])
            if split_data[-1]:  # Data without termination symbol
                self._received_buffer = split_data[-1]

    def _build_sample_package(self):
        """
        Creates a package of samples that represents approximately 1 s data. It contains 8000 samples.
        """
        if len(self._encoded_buffer.ref_signal) >= Driver.NUMBER_OF_SAMPLES:
            if sum(itertools.islice(self._encoded_buffer.ref_signal, Driver.REF_PERIOD // 2)):
                logging.error("Phase shift in reference signal detected.")
                logging.info("Start resynchronisation for next package.")
                try:
                    self._sample_numbers.popleft()
                except IndexError:
                    return
                self._synchronize = True
                return
            self._package_data.ref_signal.put([self._encoded_buffer.ref_signal.popleft() for _ in
                                               range(Driver.NUMBER_OF_SAMPLES)])
            dc_package = [[], [], []]
            ac_package = [[], [], []]
            for _ in itertools.repeat(None, Driver.NUMBER_OF_SAMPLES):
                for channel in range(Driver._CHANNELS):
                    dc_package[channel].append(self._encoded_buffer.dc_coupled[channel].popleft())
                    ac_package[channel].append(self._encoded_buffer.ac_coupled[channel].popleft())
            self._package_data.dc_coupled.put(dc_package)
            self._package_data.ac_coupled.put(ac_package)

    def _process_data(self) -> None:
        self._reset()
        while self.connected.is_set():
            self._encode_data()
            if len(self._encoded_buffer.ref_signal) >= Driver.NUMBER_OF_SAMPLES:
                self._build_sample_package()
