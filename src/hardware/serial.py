import abc
import logging
import queue
import re
import threading
import time
import typing
from dataclasses import dataclass
from enum import Enum
import os

import platform

import serial
from serial.tools import list_ports
from PySide6 import QtCore, QtSerialPort


@dataclass
class Data:
    ...


class Error(Enum):
    REQUEST = "0000"
    PARAMETER = "0001"
    COMMAND = "0002"
    UNKNOWN_COMMAND = "0003"


@dataclass
class Patterns:
    """
    The first bytes stand for get (G) the second byte for the required thing (H for Hardware, F for Firmware etc.).
    The third bytes stands for the required Information (I for ID, V for version). \n is the termination symbol.
    """
    HARDWARE_ID = re.compile(b"GHI[0-9a-fA-F]{4}", flags=re.MULTILINE)
    ERROR = re.compile(b"ERR[0-9a-fA-F]{4}", flags=re.MULTILINE)
    HEX_VALUE = re.compile(b"[0-9a-fA-F]{4}", flags=re.MULTILINE)


class Command:
    HARDWARE_ID = b"GHI0000"


class Driver(QtCore.QObject):
    _QUEUE_SIZE = 15
    MAX_RESPONSE_TIME = 100e-3  # 50 ms response time

    TERMINATION_SYMBOL = b"\n"
    _NUMBER_OF_HEX_BYTES = 4
    _START_DATA_FRAME = 1  # First symbol is the header

    def __init__(self):
        QtCore.QObject.__init__(self)
        self.received_data = queue.Queue(maxsize=Driver._QUEUE_SIZE)
        self.connected = threading.Event()
        self.device = QtSerialPort.QSerialPort()
        self.device.readyRead.connect(self.receive)
        self.port_name = ""
        self._write_buffer = queue.Queue()
        self.ready_write = threading.Event()
        self.ready_write.set()
        self.last_written_message = ""
        self.data = queue.Queue()
        self.running = False

    if platform.system() == "Windows":
        def find_port(self) -> None:
            for port in list_ports.comports():
                try:
                    device = serial.Serial(port.device, timeout=Driver.MAX_RESPONSE_TIME)
                except serial.SerialException:
                    continue
                device.write(Command.HARDWARE_ID + Driver.TERMINATION_SYMBOL)
                time.sleep(0.1)
                avaiable_bytes = device.in_waiting
                self.received_data.put(device.read(avaiable_bytes))
                hardware_id = self.get_hardware_id()
                if hardware_id == self.device_id:
                    self.port_name = port.device
                    self.device.setPortName(self.port_name)
                    logging.info(f"Found {self.device_name} at {self.port_name}")
                    device.close()
                    break
                else:
                    device.close()
            else:
                raise OSError("Could not find {self.device_name}")
    else:
        def find_port(self) -> None:
            for port in list_ports.comports():
                self.file_descriptor = os.open(path=port.device, flags=os.O_RDWR | os.O_NOCTTY | os.O_NONBLOCK)
                if self.file_descriptor == -1 or not os.isatty(self.file_descriptor):
                    continue
                os.write(self.file_descriptor, (Command.HARDWARE_ID + Driver.TERMINATION_SYMBOL).encode())
                hardware_id = self.get_hardware_id()
                if hardware_id is not None and hardware_id == self.device_id:
                    self.port_name = port.device
                    logging.info(f"Found {self.device_name} at {self.port_name}")
                    os.close(self.file_descriptor)
                else:
                    os.close(self.file_descriptor)
                    self.file_descriptor = -1  # Reset it since we found no valid one
            else:
                raise OSError("Could not find {self.device_name}")

    def open(self) -> bool:
        if self.port_name:
            logging.info(f"Connected with {self.device_name}")
            self.device.open(QtSerialPort.QSerialPort.ReadWrite)
            self.connected.set()
            return True
        else:
            raise OSError("Could not find {self.device_name}")

    def run(self) -> None:
        self.running = True
        threading.Thread(target=self._write, daemon=True).start()
        threading.Thread(target=self._read, daemon=True).start()

    def _read(self):
        try:
            print("called")
            self._process_data()
        finally:
            self.close()

    @property
    @abc.abstractmethod
    def device_id(self) -> str | int:
        ...

    @property
    @abc.abstractmethod
    def device_name(self) -> str:
        ...

    def __repr__(self) -> str:
        class_name = self.__class__.__name__
        representation = f"{class_name}(termination_symbol={Driver.TERMINATION_SYMBOL}," \
                         f" device_id={self.device_id}, port_name={self.port_name}, received_data={self.received_data})"
        return representation

    def get_hardware_id(self) -> bytes | None:
        try:
            received_data = self.received_data.get(timeout=Driver.MAX_RESPONSE_TIME)  # type: bytes
            hardware_id = Patterns.HARDWARE_ID.search(received_data)
        except queue.Empty:
            return
        if hardware_id is not None:
            hardware_id = hardware_id.group()
            return Patterns.HEX_VALUE.search(hardware_id).group()

    def command_error_handing(self, received: str) -> None:
        if Patterns.ERROR.search(received) is not None:
            match Patterns.HEX_VALUE.search(Patterns.ERROR.search(received).group()).group():
                case Error.COMMAND:
                    raise OSError(f"Packet length != 7 characters ('\n' excluded) from {self.port_name}")
                case Error.PARAMETER:
                    raise OSError(f"Error converting the hex parameter from {self.port_name}")
                case Error.COMMAND:
                    raise OSError(f"Request consists of an unknown/invalid command from {self.port_name}")
                case Error.UNKNOWN_COMMAND:
                    raise OSError(f"Unknown command from {self.port_name}")

    def write(self, message: str | bytes | bytearray) -> None:
        if isinstance(message, str):
            self._write_buffer.put(message.encode())
        else:
            self._write_buffer.put(message, block=False)

    if platform.system() == "Windows":
        def _write(self) -> None:
            while self.connected.is_set():
                if self.ready_write.wait(timeout=Driver.MAX_RESPONSE_TIME):
                    self.last_written_message = self._write_buffer.get(block=True)
                    self.device.write(self.last_written_message + Driver.TERMINATION_SYMBOL)
                    self.ready_write.clear()
    else:
        def _write(self) -> None:
            while self.connected.is_set():
                if self.ready_write.wait(timeout=Driver.MAX_RESPONSE_TIME):
                    self.last_written_message = self._write_buffer.get(block=True)
                    os.write(self.file_descriptor, (self.last_written_message + Driver.TERMINATION_SYMBOL).encode())
                    self.ready_write.clear()

    if platform.system() == "Windows":
        def is_open(self) -> bool:
            return self.device.isOpen()
    else:
        def is_open(self) -> bool:
            return self.file_descriptor != -1

    if platform.system() == "Windows":
        def close(self) -> None:
            if self.device.isOpen():
                self.connected.clear()
                self.device.close()
    else:
        def close(self) -> None:
            if self.file_descriptor != -1:
                os.close(self.file_descriptor)

    if platform.system() == "Windows":
        def receive(self) -> None:
            if self.running:
                self.received_data.put(self.device.readAll())
    else:
        def receive(self, signum, frame) -> None:
            buffer_size = os.stat(self.file_descriptor).st_size
            self.received_data.put(os.read(self.file_descriptor, buffer_size).decode())

    @abc.abstractmethod
    def _encode_data(self) -> None:
        ...

    @abc.abstractmethod
    def _process_data(self) -> None:
        ...
