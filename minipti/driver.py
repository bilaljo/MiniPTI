import configparser
import itertools
import logging
import queue
import threading
from collections import deque
from dataclasses import dataclass

import serial
from PySide6 import QtSerialPort, QtCore
from fastcrc import crc16
from serial import SerialException
from serial.tools import list_ports


@dataclass
class DAQData:
    ref_signal = None
    ac_coupled = None
    dc_coupled = None


class DAQ(QtCore.QObject):
    """
    This class provides an interface for receiving data from the serial port of a USB connected DAQ system.
    The data is accordingly to a defined protocol encoded and build into a packages of samples.
    """
    TERMINATION_SYMBOL = b"\r\n"
    PACKAGE_SIZE_START_INDEX = 2
    PACKAGE_SIZE_END_INDEX = 10
    CRC_START_INDEX = 4
    PACKAGE_SIZE = 4110
    WORD_SIZE = 32

    QUEUE_SIZE = 15
    WAIT_TIME_TIMEOUT = 100e-3  # 100 ms
    WAIT_TIME_DATA = 10e-3  # 10 ms

    CHANNELS = 3
    REF_PERIOD = 100
    NUMBER_OF_SAMPLES = 8000

    def __init__(self):
        QtCore.QObject.__init__(self)
        self.package_data = DAQData()
        self.buffers = DAQData()
        self.buffers.ref_signal = deque()
        self.buffers.ac_coupled = [deque(), deque(), deque()]
        self.buffers.dc_coupled = [deque(), deque(), deque()]
        self.received_data = queue.Queue(maxsize=DAQ.QUEUE_SIZE)
        self.package_data.ref_signal = queue.Queue(maxsize=DAQ.QUEUE_SIZE)
        self.package_data.dc_coupled = queue.Queue(maxsize=DAQ.QUEUE_SIZE)
        self.package_data.ac_coupled = queue.Queue(maxsize=DAQ.QUEUE_SIZE)
        self.device = QtSerialPort.QSerialPort()
        self.device.readyRead.connect(self.__receive)
        self.buffer = b""
        self.running = threading.Event()
        self.sample_numbers = deque(maxlen=2)
        self.receive_daq = None
        self.encode_daq = None
        self.synchronize = True
        self.ready = False

    def open_port(self):
        """
        To recognise the correct port the ports are checked for their correct behavior. The correct port would produce
        the correct size of package in the given time.
        """
        for port in list_ports.comports():
            try:
                device = serial.Serial(port.device, timeout=DAQ.WAIT_TIME_TIMEOUT)
                dummy_data = device.read(size=DAQ.PACKAGE_SIZE + 2)
                if len(dummy_data) >= DAQ.PACKAGE_SIZE + 2:
                    device.close()
                    self.device.setPortName(device.name)
                    if self.device.open(QtSerialPort.QSerialPort.ReadWrite):
                        break
                    else:
                        raise IOError("Device not connected")
            except SerialException:
                continue
        else:
            raise IOError("Device not connected")

    def __call__(self):
        self.running.set()
        self.__reset()
        while self.running.is_set():
            self.__encode_data()
            if len(self.buffers.ref_signal) >= DAQ.NUMBER_OF_SAMPLES:
                self.__build_sample_package()

    def close(self):
        if self.device.isOpen():
            self.device.close()

    def __receive(self):
        self.received_data.put(bytes(self.device.readAll()))

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


class Driver:
    TERMINATION_SYMBOL = ord("\n")
    WORD_SIZE = 8
    VALUE_SIZE = 4
    COMMAND = ord("C")
    SETTER = ord("S")
    GETTER = ord("G")

    def __init__(self):
        self._message = bytearray(self.WORD_SIZE)
        self._message[self.WORD_SIZE - 1] = Driver.TERMINATION_SYMBOL

    def send(self):
        if self._message[self.WORD_SIZE - 1] != Driver.TERMINATION_SYMBOL:
            raise ValueError("No termination symbol")
        logging.info(f"Send {self._message}")


class Laser(Driver):
    VOLTAGE = ord("V")
    CURRENT = ord("I")
    HIGH = ord("H")
    LOW = ord("L")
    ENABLE = ord("E")
    MODE = ord("M")
    GAIN = ord("G")

    def __init__(self) -> None:
        super().__init__()
        self._high_voltage = 0
        self._high_current = 0
        self.enabled = False

    def init_settings(self, config_file="laser_driver.ini"):
        laser_driver_config = configparser.ConfigParser()
        laser_driver_config.read(config_file)
        self.high_voltage = int(laser_driver_config["High"]["Voltage"])
        self.high_current = int(laser_driver_config["High"]["Current"])

    def init_laser(self):
        self._message[0] = Driver.COMMAND
        self._message[1] = Laser.HIGH
        self._message[1] = Laser.VOLTAGE
        self.send()

    def set_voltage(self):
        self._message[0] = Driver.SETTER
        self._message[1] = Laser.HIGH
        self._message[2] = Laser.VOLTAGE
        self._message[3:Driver.WORD_SIZE] = self._high_voltage.to_bytes(length=Driver.VALUE_SIZE, byteorder="big")
        self.send()

    def set_current(self):
        self._message[0] = Driver.SETTER
        self._message[1] = Laser.HIGH
        self._message[2] = Laser.CURRENT  # FIXME: Does this work?
        self._message[3:Driver.WORD_SIZE] = self._high_current.to_bytes(length=Driver.VALUE_SIZE, byteorder="big")
        self.send()

    def set_mode(self):
        self._message[0] = Driver.SETTER
        self._message[1] = Laser.LOW
        self._message[2] = Laser.MODE
        self.send()

    def set_gain(self):
        self._message[0] = Driver.SETTER
        self._message[1] = Laser.LOW
        self._message[2] = Laser.GAIN

    def enable(self):
        self._message[0] = Driver.SETTER
        self._message[2] = Laser.ENABLE
        self._message[1] = Laser.HIGH
        self.send()  # Enable high
        self._message[1] = Laser.LOW
        self.send()  # Enable low

    @property
    def high_voltage(self):
        return self._high_voltage

    @high_voltage.setter
    def high_voltage(self, voltage):
        if voltage > 2 ** Driver.VALUE_SIZE - 1:
            raise ValueError("Value exceeds maximum size")
        self._high_voltage = voltage

    @property
    def high_current(self):
        return self._high_current

    @high_current.setter
    def high_current(self, current):
        if current > 2 ** Driver.VALUE_SIZE - 1:
            raise ValueError("Value exceeds maximum size")
        self._high_current = current

    def __repr__(self):
        representation = f"Laser Driver\nVoltage: {self.high_voltage} Bit\n"
        representation += f"Current: {self.high_current} Bit\nEnabled: {self.enabled}"
        return representation
