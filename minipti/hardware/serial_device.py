import multiprocessing
from abc import abstractmethod, ABC
import functools
import logging
import os
import platform
import re
import time
from dataclasses import dataclass
from enum import Enum
from typing import Union
import queue
import itertools

from overrides import final
import threading

if platform.system() == "Windows":
    import clr
    import System
else:
    import termios
import serial
from serial.tools import list_ports

from . import protocolls


class Driver(ABC):
    """
    Base class for serial port reading and writing. Note that the class uses for reading, writing and proceeding of
    incoming data respectively their own event loops, e.g. the reading is done blocking synchronously (without polling).
    It is not intended to be used asynchron (with an event-driven approach).
    """
    _QUEUE_SIZE = 4095
    _MAX_RESPONSE_TIME = 500e-3  # s
    _MAX_WAIT_TIME = 5  # s

    _TERMINATION_SYMBOL = "\n"
    _START_DATA_FRAME = 1
    _IO_BUFFER_SIZE = 8000
    _SEARCH_ATTEMPTS = 3

    def __init__(self):
        self._port_name = ""
        self._package_buffer = ""
        self._ready_write = threading.Event()
        self._received_data = queue.Queue(maxsize=Driver._QUEUE_SIZE)
        self._ready_write.set()
        self.last_written_message = ""
        self.data = queue.Queue(maxsize=Driver._QUEUE_SIZE)
        self._write_buffer = queue.Queue(maxsize=Driver._QUEUE_SIZE)
        if platform.system() == "Windows":
            self._serial_port = System.IO.Ports.SerialPort()
        else:
            self._file_descriptor = -1
        self.connected = threading.Event()

    @property
    def port_name(self) -> str:
        return self._port_name

    @port_name.setter
    def port_name(self, port_name: str) -> None:
        old_port_name = self.port_name
        try:
            self.port_name = port_name
            self.open()
        except OSError:
            self.port_name = old_port_name

    @property
    @abstractmethod
    def device_id(self) -> bytes:
        ...

    @property
    @abstractmethod
    def device_name(self) -> str:
        ...

    @property
    def is_found(self) -> bool:
        return self._is_found

    def __repr__(self) -> str:
        name_space = os.path.splitext(os.path.basename(__file__))[0]
        class_name = self.__class__.__name__
        representation = f"{name_space}.{class_name}(device_name={self.device_name}," \
                         f" termination_symbol=\\n, device_id={self.device_id}," \
                         f" port_name={self.port_name})"
        return representation

    @final
    def find_port(self) -> None:
        if self.is_open:
            return
        for _ in itertools.repeat(None, Driver._SEARCH_ATTEMPTS):
            for port in list_ports.comports():
                try:
                    if platform.system() != "Windows":
                        port_name = "/dev/" + port.name
                    else:
                        port_name = port.name
                    with serial.Serial(port_name, timeout=Driver._MAX_RESPONSE_TIME,
                                       write_timeout=Driver._MAX_RESPONSE_TIME) as device:
                        if self._check_hardware_id(device):
                            self._port_name = port_name
                            logging.info(f"Found {self.device_name} at {self.port_name}")
                            self._is_found = True
                            return
                except serial.SerialException:
                    continue
        else:
            raise OSError(f"Could not find {self.device_name}. Maybe it is already connected")

    @final
    def _check_hardware_id(self, device) -> bool:
        device.write(Command.HARDWARE_ID + Driver._TERMINATION_SYMBOL.encode())
        time.sleep(0.1)
        available_bytes = device.in_waiting
        self._received_data.put(device.read(available_bytes))
        return self.get_hardware_id() == self.device_id

    @final
    def _clear(self) -> None:
        self._write_buffer = queue.Queue()
        self.last_written_message = ""
        self._received_data = queue.Queue()
        self._ready_write.set()

    if platform.system() == "Windows":
        #@final
        def open(self) -> None:
            if self.port_name and not self.is_open:
                self._clear()
                self._serial_port = System.IO.Ports.SerialPort()
                self._serial_port.PortName = self.port_name
                self._serial_port.DataReceived += System.IO.Ports.SerialDataReceivedEventHandler(self._receive)
                self._serial_port.Open()
                self.connected.set()
                logging.info("Connected with %s", self.device_name)
            else:
                raise OSError("Could not connect with %s", self.device_name)
    else:
        #@final
        def open(self) -> None:
            if self.port_name and not self.is_open:
                try:
                    self._clear()
                    self._file_descriptor = os.open(path=self.port_name, flags=os.O_RDWR)
                    old_attribute = termios.tcgetattr(self._file_descriptor)
                    iflag, oflag, cflag, lflag, ispeed, ospeed, cc = old_attribute

                    iflag &= ~termios.BRKINT
                    lflag = 0
                    oflag = 0

                    cc[termios.VMIN] = 1
                    cc[termios.VTIME] = Driver._MAX_WAIT_TIME * 1000  # in ms on Unix

                    iflag &= ~(termios.IXON | termios.IXOFF | termios.IXANY)

                    cflag |= (termios.CLOCAL | termios.CREAD)

                    cflag &= ~(termios.PARENB | termios.PARODD)

                    cflag &= ~termios.CSTOPB

                    new_attribute = [iflag, oflag, cflag, lflag, ispeed, ospeed, cc]
                    termios.tcsetattr(self._file_descriptor, termios.TCSANOW, new_attribute)
                except OSError:
                    raise OSError("Could not connect with %s", self.device_name)
                self.connected.set()
                logging.info(f"Connected with {self.device_name}")
            else:
                raise OSError("Could not connect with %s", self.device_name)

    @final
    def run(self) -> None:
        threading.Thread(target=self._write, daemon=True, name=f"{self.device_name} Write Thread").start()
        if platform.system() != "Windows":
            threading.Thread(target=self._receive, daemon=True, name=f"{self.device_name} Receive Thread").start()
        threading.Thread(target=self._process_data, daemon=True, name=f"{self.device_name} Processing Thread").start()

    @final
    def get_hardware_id(self) -> Union[bytes, None]:
        try:
            received_data: bytes = self._received_data.get(timeout=Driver._MAX_RESPONSE_TIME)
            hardware_id = Patterns.HARDWARE_ID.search(received_data)
        except queue.Empty:
            return
        if hardware_id is not None:
            hardware_id = hardware_id.group()
            return Patterns.HEX_VALUE.search(hardware_id).group()

    @functools.singledispatchmethod
    @final
    def write(self, message: str) -> bool:
        if self.connected.is_set():
            self._write_buffer.put(message, block=False)
            return True
        return False

    @write.register(protocolls.ASCIIProtocoll)
    @final
    def _(self, message: protocolls.ASCIIProtocoll) -> bool:
        if self.connected.is_set():
            self._write_buffer.put(str(message), block=False)
            return True
        return False

    @write.register(bytes)
    @write.register(bytearray)
    @final
    def _(self, message: Union[bytes, bytearray]) -> bool:
        if self.connected.is_set():
            self._write_buffer.put(message.decode(), block=False)
            return True
        return False

    @final
    def _write(self) -> None:
        while self.connected.is_set():
            self._ready_write.wait(timeout=Driver._MAX_RESPONSE_TIME)
            self._ready_write.clear()
            self.last_written_message = self._write_buffer.get(block=True) + Driver._TERMINATION_SYMBOL
            try:
                self._transfer()
            except OSError:
                logging.error("Could not transfer %s to %s", self.last_written_message)
                break
            logging.debug("%s written to %s", self.last_written_message[:-1], self.device_name)

    @final
    def _transfer(self) -> None:
        if platform.system() == "Windows":
            self._serial_port.Write(self.last_written_message)
        else:
            os.write(self._file_descriptor, self.last_written_message.encode())

    @final
    def _check_ack(self, data: str) -> bool:
        last_written = self.last_written_message[:-1]
        if data != last_written and data != last_written.capitalize():
            logging.error("Received message %s message, expected  %s", data, self.last_written_message)
            success = False
        else:
            logging.debug("Command %s successfully applied", data)
            success = True
        self._ready_write.set()
        return success

    if platform.system() == "Windows":
        @property
        def is_open(self) -> bool:
            return self._serial_port.IsOpen
    else:
        @property
        def is_open(self) -> bool:
            return self._file_descriptor != -1

    if platform.system() == "Windows":
        def close(self) -> None:
            if self.is_open:
                self.connected.clear()
                self._serial_port.Close()
                logging.info("Closed connection to %s", self.device_name)
    else:
        def close(self) -> None:
            if self.is_open:
                self.connected.clear()
                os.close(self._file_descriptor)
                logging.info("Closed connection to %s", self.device_name)

    if platform.system() == "Windows":
        """
        Serial Port Reading Implementation on Windows.
        """
        @final
        def _receive(self, _sender, _arg: System.IO.Ports.SerialDataReceivedEventArgs) -> None:
            if self._serial_port.BytesToRead:
                self._received_data.put(self._serial_port.ReadExisting())

    else:
        """
        Serial Port Reading Implementation on Unix.
        """
        @final
        def _receive(self) -> None:
            """
            This threads blocks until data on the serial port is available. If after 5 s now data has come it is assumed
            that the connection is lost.
            """
            while self.connected.is_set():
                received = os.read(self._file_descriptor, Driver._IO_BUFFER_SIZE)
                if not received:
                    logging.error("Connection to %s lost", self.device_name)
                    self._file_descriptor = -1
                    self._is_found = False
                    self.connected.clear()
                else:
                    self._received_data.put(received.decode())

    @final
    def get_data(self) -> str:
        try:
            received_data: str = self._received_data.get(block=True, timeout=Driver._MAX_WAIT_TIME)
            return received_data
        except queue.Empty:
            self.connected.clear()
            logging.error("Connection to %s lost", self.device_name)
            if platform.system() != "Windows":
                self._file_descriptor = -1
            raise OSError

    @final
    def _encode_data(self) -> None:
        """
        Encodes incoming data of the serial device. Each package has a package identifier, to decide the decoding
        algorithm of it.
        """
        try:
            received_data: str = self._package_buffer + self.get_data()
        except OSError:
            return
        split_data = received_data.split(Driver._TERMINATION_SYMBOL)
        for received in split_data[:-1]:
            self._encode(received)
        self._package_buffer = split_data[-1]

    @abstractmethod
    def _encode(self, data: str) -> None:
        ...

    @abstractmethod
    def _process_data(self) -> None:
        ...


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
    The first bytes stand for get (G) the second byte for the required thing (H for Hardware).
    The third bytes stands for the required Information (I for ID, V for version).
    \n is the termination symbol.
    """
    HARDWARE_ID = re.compile(b"GHI[0-9a-fA-F]{4}", flags=re.MULTILINE)
    ERROR = re.compile(b"ERR[0-9a-fA-F]{4}", flags=re.MULTILINE)
    HEX_VALUE = re.compile(b"[0-9a-fA-F]{4}", flags=re.MULTILINE)


class Command:
    HARDWARE_ID = b"GHI0000"
