import abc
import logging
import queue
import re
import time
from dataclasses import dataclass
from enum import Enum

from PySide6 import QtSerialPort, QtCore
import serial


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
    HARDWARE_ID = re.compile(b"(GHI[0-9a-fA-F]{4}\n)", flags=re.MULTILINE)
    ERROR = re.compile(b"(ERR[0-9a-fA-F]{4}\n)", flags=re.MULTILINE)
    HEX_VALUE = re.compile(b"[0-9a-fA-F]{4}", flags=re.MULTILINE)


class SerialError(Exception):
    pass


class Command:
    HARDWARE_ID = b"GHI0000\n"


class Serial(QtCore.QObject):
    QUEUE_SIZE = 15
    WAIT_TIME = 50  # ms

    TERMINATION_SYMBOL = b"\n"
    NUMBER_OF_HEX_BYTES = 4

    def __init__(self):
        QtCore.QObject.__init__(self)
        self.port = None
        self.device = QtSerialPort.QSerialPort()
        self.device.readyRead.connect(self.__receive)
        self.received_data = queue.Queue(maxsize=Serial.QUEUE_SIZE)
        self.connected = False

    @property
    @abc.abstractmethod
    def device_id(self):
        pass

    @property
    @abc.abstractmethod
    def device_name(self):
        pass

    def __repr__(self):
        class_name = self.__class__.__name__
        representation = f"{class_name}(termination_symbol={Serial.TERMINATION_SYMBOL}," \
                         f" device_id={self.device_id}"
        representation += f"port={self.port}, device={self.device}, received_data={self.received_data})"
        return representation

    def get_hardware_id(self):
        hardware_id = Patterns.HARDWARE_ID.search(self.received_data.get())
        if hardware_id is not None:
            hardware_id = hardware_id.group()
            return Patterns.HEX_VALUE.search(hardware_id).group()

    def command_error_handing(self, received):
        if Patterns.ERROR.search(received) is not None:
            match Patterns.HEX_VALUE.search(Patterns.ERROR.search(received).group()).group():
                case Error.COMMAND:
                    raise SerialError(f"Packet length != 7 characters ('\n' excluded) from {self.device}")
                case Error.PARAMETER:
                    raise SerialError(f"Error converting the hex parameter from {self.device}")
                case Error.COMMAND:
                    raise SerialError(f"Request consists of an unknown/invalid command from {self.device}")
                case Error.UNKNOWN_COMMAND:
                    raise SerialError(f"Unknown command from {self.device}")

    def write(self, message):
        if self.connected:
            self.device.write(message + Serial.TERMINATION_SYMBOL)
            if not self.device.flush():
                logging.error(f"Could not write {message} to {self.port}")
                return False
            return True
        else:
            return False

    def __enter__(self):
        self.find_port()

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    @abc.abstractmethod
    def encode_data(self):
        ...

    def find_port(self):
        """
        To recognise the correct port the ports are checked for their correct behavior. The correct port would produce
        the correct size of package in the given time.
        """
        for port in QtSerialPort.QSerialPortInfo.availablePorts():
            try:
                device = serial.Serial(port=port.portName(), write_timeout=Serial.WAIT_TIME,
                                       timeout=Serial.WAIT_TIME)
            except serial.SerialException:
                continue
            if not device.is_open:
                continue
            if not device.writable():
                device.close()
            received_bytes = b""
            start_time = time.time() * 1000
            current_time = start_time
            device.write(Command.HARDWARE_ID)
            while current_time < start_time + Serial.WAIT_TIME:
                received_bytes += device.read(device.inWaiting())
                current_time = time.time() * 1000
            self.received_data.put(received_bytes)
            if self.get_hardware_id() == self.device_id:
                device.close()
                self.port = port.portName()
                logging.info(f"Found {self.device_name} at {self.port}")
                self.device.setPortName(port.portName())
                break
            else:
                device.close()
        else:
            logging.error(f"Could not find {self.device_name}")
            raise SerialError("Could not find {self.device_name}")

    def open(self):
        if self.device.portName():
            logging.info(f"Connected with {self.device_name}")
            self.device.open(QtSerialPort.QSerialPort.ReadWrite)
            self.connected = True
        else:
            logging.error(f"Could not connect with {self.device_name}")
            raise SerialError(f"Could not connect with {self.device_name}")

    def is_open(self):
        return self.device.isOpen()

    def close(self):
        if self.device.isOpen():
            self.device.close()
            self.connected = False

    def __receive(self):
        print(self.device.readAll().toStdString())
        try:
            self.received_data.put(bytes(self.device.readAll()), block=False)
        except queue.Full:
            logging.error(f"Buffer queue of device {self.device_name} is full")
            logging.info("Removed one item")
            self.received_data.get()  # Remove the oldest item since the queue is full
