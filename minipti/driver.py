import itertools
import logging
import queue
import re
import threading
from collections import deque
from dataclasses import dataclass
from enum import Enum

from PySide6 import QtSerialPort, QtCore
from fastcrc import crc16


class Error(Enum):
    REQUEST = b"0000"
    PARAMETER = b"0001"
    COMMAND = b"0002"
    UNKNOWN_COMMAND = b"0003"


@dataclass
class Patterns:
    """
    The first bytes stand for get (G) the second byte for the required thing (H for Hardware, F for Firmware etc.).
    The third bytes stands for the required Information (I for ID, V for version). \n is the termination symbol.
    """
    HARDWARE_ID = re.compile(b"(GHI...\n)", flags=re.MULTILINE)
    FIRMWARE_VERSION = re.compile(b"(GFW...\n)", flags=re.MULTILINE)
    HARDWARE_VERSION = re.compile(b"(GHW...\n)", flags=re.MULTILINE)
    ERROR = re.compile(b"(ERR...\n)", flags=re.MULTILINE)
    VALUE = re.compile(b"[0-9a-fA-F]+")  # Hex value


class SerialError(Exception):
    pass


class SerialDevice(QtCore.QObject):
    QUEUE_SIZE = 15
    WAIT_TIME = 100  # ms
    GET_HARDWARE_ID = b"GHI0000\n"
    GET_FIRMWARE_VERSION = b"GFW0000\n"
    GET_HARDWARE_VERSION = b"GWW0000\n"

    def __init__(self, termination_symbol, device_id):
        QtCore.QObject.__init__(self)
        self.termination_symbol = termination_symbol
        self.device_id = bytes(device_id)
        self.port = None
        self.device = QtSerialPort.QSerialPort()
        self.device.readyRead.connect(self.__receive)
        self.received_data = queue.Queue(maxsize=SerialDevice.QUEUE_SIZE)

    def get_hardware_id(self):
        return Patterns.VALUE.search(Patterns.HARDWARE_ID.search(self.received_data.get())).group()

    def get_hardware_version(self):
        return Patterns.VALUE.search(Patterns.HARDWARE_VERSION.search(self.received_data.get())).group()

    def get_firmware_version(self):
        return Patterns.VALUE.search(Patterns.FIRMWARE_VERSION.search(self.received_data.get())).group()

    def command_error_handing(self, received):
        if Patterns.ERROR.search(received):
            match Patterns.VALUE.search(Patterns.ERROR.search(received)):
                case Error.COMMAND:
                    raise SerialError(f"Packet length != 7 characters ('\n' excluded) from {self.device}")
                case Error.PARAMETER:
                    raise SerialError(f"Error converting the hex parameter from {self.device}")
                case Error.COMMAND:
                    raise SerialError(f"Request consists of an unknown/invalid command from {self.device}")
                case Error.UNKNOWN_COMMAND:
                    raise SerialError(f"Unknown command from {self.device}")

    def __enter__(self):
        self.open()

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    def open(self):
        """
        To recognise the correct port the ports are checked for their correct behavior. The correct port would produce
        the correct size of package in the given time.
        """
        for port in QtSerialPort.QSerialPortInfo.availablePorts():
            self.device.setPortName(port.portName())
            self.device.open(QtSerialPort.QSerialPort.ReadWrite)
            if not self.device.isOpen():
                continue
            self.device.write(SerialDevice.GET_HARDWARE_ID)
            self.device.waitForBytesWritten(msecs=SerialDevice.WAIT_TIME)
            self.device.waitForReadyRead(msecs=SerialDevice.WAIT_TIME)
            received = self.device.readAll()
            self.command_error_handing(received)
            if not received:
                self.device.close()
                continue
            self.received_data.put(received)
            if self.get_hardware_id() == self.device_id:
                self.port = port.portName()
                break
        else:
            raise SerialError("Device not found")

    def close(self):
        if self.device.isOpen():
            self.device.close()

    def __receive(self):
        self.received_data.put(bytes(self.device.readAll()))

    def __repr__(self):
        pass


@dataclass
class DAQData:
    ref_signal = None
    ac_coupled = None
    dc_coupled = None


class DAQ(SerialDevice):
    """
    This class provides an interface for receiving data from the serial port of a USB connected DAQ system.
    The data is accordingly to a defined protocol encoded and build into a packages of samples.
    """
    PACKAGE_SIZE_START_INDEX = 2
    PACKAGE_SIZE_END_INDEX = 10
    CRC_START_INDEX = 4
    PACKAGE_SIZE = 4110
    WORD_SIZE = 32
    TERMINATION_SYMBOL = b"\n"
    ID = b"0000"

    WAIT_TIME_TIMEOUT = 100e-3  # 100 ms
    WAIT_TIME_DATA = 10e-3  # 10 ms

    CHANNELS = 3
    REF_PERIOD = 100
    NUMBER_OF_SAMPLES = 8000

    def __init__(self):
        SerialDevice.__init__(self, termination_symbol=DAQ.TERMINATION_SYMBOL, device_id=DAQ.ID)
        self.package_data = DAQData()
        self.buffers = DAQData()
        self.buffers.ref_signal = deque()
        self.buffers.ac_coupled = [deque(), deque(), deque()]
        self.buffers.dc_coupled = [deque(), deque(), deque()]
        self.package_data.ref_signal = queue.Queue(maxsize=DAQ.QUEUE_SIZE)
        self.package_data.dc_coupled = queue.Queue(maxsize=DAQ.QUEUE_SIZE)
        self.package_data.ac_coupled = queue.Queue(maxsize=DAQ.QUEUE_SIZE)
        self.buffer = b""
        self.running = threading.Event()
        self.sample_numbers = deque(maxlen=2)
        self.receive_daq = None
        self.encode_daq = None
        self.synchronize = True
        self.ready = False

    def __call__(self):
        self.running.set()
        self.__reset()
        try:
            while self.running.is_set():
                self.__encode_data()
                if len(self.buffers.ref_signal) >= DAQ.NUMBER_OF_SAMPLES:
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
        raw_data = raw_data[DAQ.PACKAGE_SIZE_END_INDEX:DAQ.PACKAGE_SIZE - DAQ.CRC_START_INDEX]
        ref = []
        ac = [[], [], []]
        dc = [[], [], [], []]
        for i in range(0, len(raw_data), DAQ.WORD_SIZE):
            ref.append(int(raw_data[i:i + 4], 16))
            # AC signed
            ac_value = DAQ.__binary_to_2_complement(int(raw_data[i + 4:i + 8], base=16), 16)
            ac[0].append(ac_value)
            ac_value = DAQ.__binary_to_2_complement(int(raw_data[i + 8:i + 12], base=16), 16)
            ac[1].append(ac_value)
            ac_value = DAQ.__binary_to_2_complement(int(raw_data[i + 12:i + 16], base=16), 16)
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

    def __encode_data(self):
        """
        The data is encoded according to the following protocol:
            - The first two bytes describes the send command
            - Byte 2 up to 10 describe the package number of the send package
            - Byte 10 to 32 contain the data as period sequence of blocks in hex decimal
            - The last 4 bytes represent a CRC checksum in hex decimal
        """
        self.buffer += self.received_data.get(block=True)
        if len(self.buffer) >= DAQ.PACKAGE_SIZE + len(DAQ.TERMINATION_SYMBOL):
            splitted_data = self.buffer.split(DAQ.TERMINATION_SYMBOL)
            self.buffer = b""
            for data in splitted_data:
                if len(data) != DAQ.PACKAGE_SIZE:  # Broken package with missing beginning
                    continue
                crc_calculated = crc16.arc(data[:-DAQ.CRC_START_INDEX])
                crc_received = int(data[-DAQ.CRC_START_INDEX:], base=16)
                if crc_calculated != crc_received:  # Corrupted data
                    logging.error(f"CRC value isn't equal to transmitted. Got {crc_received} "
                                  f"instead of {crc_calculated}.")
                    self.synchronize = True  # The data is not trustful, and it should be waited for new
                    self.sample_numbers.popleft()
                    self.sample_numbers.popleft()
                    self.__reset()
                    continue
                self.sample_numbers.append(data[DAQ.PACKAGE_SIZE_START_INDEX:DAQ.PACKAGE_SIZE_END_INDEX])
                if len(self.sample_numbers) > 1:
                    package_difference = int(self.sample_numbers[1], base=16) - int(self.sample_numbers[0], base=16)
                    if package_difference != 1:
                        logging.error(f"Missing {package_difference} packages.")
                        logging.info("Start resynchronisation.")
                        self.sample_numbers.popleft()
                        self.__reset()
                ref_signal, ac_coupled, dc_coupled = DAQ.__encode(data)
                self.synchronize = False
                if self.synchronize:
                    while sum(itertools.islice(ref_signal, DAQ.REF_PERIOD // 2)):
                        ref_signal.pop(0)
                        for channel in range(DAQ.CHANNELS):
                            ac_coupled[channel].pop(0)
                            dc_coupled[channel].pop(0)
                    if len(ref_signal) < DAQ.REF_PERIOD // 2:
                        continue
                    self.synchronize = False
                else:
                    self.buffers.ref_signal.extend(ref_signal)
                    for channel in range(DAQ.CHANNELS):
                        self.buffers.dc_coupled[channel].extend(dc_coupled[channel])
                        self.buffers.ac_coupled[channel].extend(ac_coupled[channel])
            if splitted_data[-1]:  # Data without termination symbol
                self.buffer = splitted_data[-1]

    def __build_sample_package(self):
        """
        Creates a package of samples that represents approximately 1 s data. It contains 8000 samples.
        """
        if len(self.buffers.ref_signal) >= DAQ.NUMBER_OF_SAMPLES:
            if sum(itertools.islice(self.buffers.ref_signal, DAQ.REF_PERIOD // 2)):
                logging.error("Phase shift in reference signal detected.")
                logging.info("Start resynchronisation for next package.")
                self.sample_numbers.popleft()
                self.synchronize = True
                return
            self.package_data.ref_signal.put([self.buffers.ref_signal.popleft() for _ in range(DAQ.NUMBER_OF_SAMPLES)])
            dc_package = [[], [], []]
            ac_package = [[], [], []]
            for _ in itertools.repeat(None, DAQ.NUMBER_OF_SAMPLES):
                for channel in range(DAQ.CHANNELS):
                    dc_package[channel].append(self.buffers.dc_coupled[channel].popleft())
                    ac_package[channel].append(self.buffers.ac_coupled[channel].popleft())
            self.package_data.dc_coupled.put(dc_package)
            self.package_data.ac_coupled.put(ac_package)
