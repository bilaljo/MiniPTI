import abc
import functools
import itertools
import logging
import os
import platform
import re
import time
from dataclasses import dataclass
from enum import Enum
from typing import Union
import threading
import queue


if platform.system() == "Windows":
    import clr
    import System
else:
    import termios
import serial
from serial.tools import list_ports


class SerialStream:
    _COMMAND_PREFIX = 3
    _COMMAND = 0
    _VALUE = 1
    _NUMBER_OF_HEX_DIGITS = 4
    #_STREAM_PATTERN = re.compile(r"[GSC][a-zA-Z][\da-zA-Z][\da-fA-F]{4}")  # 4 Hex Digits
    _STREAM_PATTERN = re.compile(r"[G|S]et[a-zA-Z]+:\[? ]\?")  # 4 Hex Digits
    _MIN_VALUE = 0
    _MAX_VALUE = (1 << _NUMBER_OF_HEX_DIGITS * 4) - 1  # 1 hex byte corresponds to 4 binary bytes

    def __init__(self, stream: str):
        """
        A serial stream consistent of three bytes whereby the first represents a command for the serial device
        (G for Get, S for Set and C for Command ("execute")). The next 4 bytes represent the value that is needed for
        the command. The values are represented in hex strings.
        """
        if not SerialStream._STREAM_PATTERN.fullmatch(stream):
            raise ValueError(f"Stream {stream} is not valid")
        self._stream = stream
        self._package: list[str, str] = [stream[:SerialStream._COMMAND_PREFIX], stream[SerialStream._COMMAND_PREFIX:]]

    def __str__(self) -> str:
        return self._stream

    def __repr__(self) -> str:
        return f"SerialStream(command={self.command}, value={self.value}, stream={self.stream})"

    @property
    def command(self) -> str:
        return self._package[SerialStream._COMMAND]

    @property
    def value(self) -> int:
        return int(self._package[SerialStream._VALUE], base=16)

    @value.setter
    def value(self, value: Union[str, int]) -> None:
        if not (SerialStream._MIN_VALUE <= int(value) < SerialStream._MAX_VALUE):
            raise ValueError("Value is out of range for 4 digit hex values")
        elif not isinstance(value, str):
            value = f"{value:0{SerialStream._NUMBER_OF_HEX_DIGITS}X}"
        self._package[SerialStream._VALUE] = value
        self._stream = self._stream[:SerialStream._COMMAND_PREFIX] + self._package[SerialStream._VALUE]

    @property
    def stream(self) -> str:
        return self._stream


class Driver:
    """
    Base class for serial port reading and writing. Note that the class uses for reading, writing and proceeding of
    incoming data respectively their own event loops, e.g. the reading is done blocking synchronously (without polling).
    It is not intended to be used asynchron (with an event-driven approach).
    """
    _QUEUE_SIZE = 15
    _MAX_RESPONSE_TIME = 500e-3  # s
    _MAX_WAIT_TIME = 5  # s

    _TERMINATION_SYMBOL = "\n"
    _START_DATA_FRAME = 1
    _IO_BUFFER_SIZE = 8000
    _SEARCH_ATTEMPTS = 3

    def __init__(self):
        self._port_name = ""
        self._write_buffer = queue.Queue()
        self.data = queue.Queue()
        self._ready_write = threading.Event()
        self._ready_write.set()
        self.last_written_message = ""
        if platform.system() == "Windows":
            self._serial_port = System.IO.Ports.SerialPort()
        else:
            self._file_descriptor = -1
        self.connected = threading.Event()
        self.received_data = queue.Queue()

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
    @abc.abstractmethod
    def device_id(self) -> bytes:
        ...

    @property
    @abc.abstractmethod
    def device_name(self) -> str:
        ...

    def __repr__(self) -> str:
        name_space = os.path.splitext(os.path.basename(__file__))[0]
        class_name = self.__class__.__name__
        representation = f"{name_space}.{class_name}(device_name={self.device_name}," \
                         f" termination_symbol=\\n, device_id={self.device_id}," \
                         f" port_name={self.port_name})"
        return representation

    def find_port(self) -> None:
        if self.is_open:
            return
        for _ in itertools.repeat(None, Driver._SEARCH_ATTEMPTS):
            for port in list_ports.comports():
                try:
                    with serial.Serial(port.name, timeout=Driver._MAX_RESPONSE_TIME,
                                       write_timeout=Driver._MAX_RESPONSE_TIME) as device:
                        if self._check_hardware_id(device):
                            self._port_name = port.name
                            logging.info(f"Found {self.device_name} at {self.port_name}")
                            return
                except serial.SerialException:
                    continue
        else:
            raise OSError(f"Could not find {self.device_name}. Maybe it is already connected")

    def _check_hardware_id(self, device) -> bool:
        device.write(Command.HARDWARE_ID + Driver._TERMINATION_SYMBOL.encode())
        time.sleep(0.1)
        available_bytes = device.in_waiting
        self.received_data.put(device.read(available_bytes))
        return self.get_hardware_id() == self.device_id

    def _clear(self) -> None:
        self._write_buffer = queue.Queue()
        self.data = queue.Queue()
        self.last_written_message = ""
        self.received_data = queue.Queue()
        self._ready_write.set()

    if platform.system() == "Windows":
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
        def open(self) -> None:
            if self.port_name and not self.is_open:
                try:
                    self._clear()
                    self._file_descriptor = os.open(path=self.port_name, flags=os.O_RDWR | os.O_NOCTTY | os.O_SYNC)
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

                    cflag &= ~termios.CSTOPB

                    new_attribute = [iflag, oflag, cflag, lflag, ispeed, ospeed, cc]
                    termios.tcsetattr(self._file_descriptor, termios.TCSANOW, new_attribute)
                except OSError:
                    raise OSError("Could not connect find %s", self.device_name)
                self.connected.set()
                logging.info(f"Connected with {self.device_name}")
            else:
                raise OSError("Could not connect with %s", self.device_name)

    def run(self) -> None:
        threading.Thread(target=self._write, daemon=True, name=f"{self.device_name} Write Thread").start()
        if platform.system() != "Windows":
            threading.Thread(target=self._receive, daemon=True, name=f"{self.device_name} Receive Thread").start()
        threading.Thread(target=self._process_data, daemon=True, name=f"{self.device_name} Processing Thread").start()

    def get_hardware_id(self) -> Union[bytes, None]:
        try:
            received_data: bytes = self.received_data.get(timeout=Driver._MAX_RESPONSE_TIME)
            hardware_id = Patterns.HARDWARE_ID.search(received_data)
        except queue.Empty:
            return
        if hardware_id is not None:
            hardware_id = hardware_id.group()
            return Patterns.HEX_VALUE.search(hardware_id).group()

    def command_error_handing(self, received: str) -> None:
        if Patterns.ERROR.search(received) is not None:
            error = Patterns.HEX_VALUE.search(Patterns.ERROR.search(received).group()).group()
            if error == Error.COMMAND:
                raise OSError(f"Packet length != 7 characters ('\n' excluded) from {self.port_name}")
            elif error == Error.PARAMETER:
                raise OSError(f"Error converting the hex parameter from {self.port_name}")
            elif error == Error.COMMAND:
                raise OSError(f"Request consists of an unknown/invalid command from {self.port_name}")
            elif error == Error.UNKNOWN_COMMAND:
                raise OSError(f"Unknown command from {self.port_name}")

    @functools.singledispatchmethod
    def write(self, message: str) -> bool:
        if self.connected.is_set():
            self._write_buffer.put(message, block=False)
            return True
        return False

    @write.register
    def _(self, message: int) -> bool:
        if self.connected.is_set():
            self._write_buffer.put(str(message), block=False)
            return True
        return False

    @write.register(SerialStream)
    def _(self, message: SerialStream) -> bool:
        if self.connected.is_set():
            self._write_buffer.put(str(message), block=False)
            return True
        return False

    @write.register
    def _(self, message: bytes) -> bool:
        if self.connected.is_set():
            self._write_buffer.put(message.decode(), block=False)
            return True
        return False

    @write.register
    def _(self, message: bytearray) -> bool:
        if self.connected.is_set():
            self._write_buffer.put(message.decode(), block=False)
            return True
        return False

    def _write(self) -> None:
        while self.connected.is_set():
            self._ready_write.wait(timeout=Driver._MAX_RESPONSE_TIME)
            self.last_written_message = self._write_buffer.get(block=True) + Driver._TERMINATION_SYMBOL
            try:
                self._transfer()
            except OSError:
                logging.error("Could not transfer %s to %s", self.last_written_message)
                break
            logging.debug("%s written to %s", self.last_written_message[:-1], self.device_name)
            self._ready_write.clear()

    def _transfer(self) -> None:
        if platform.system() == "Windows":
            self._serial_port.Write(self.last_written_message)
        else:
            os.write(self._file_descriptor, self.last_written_message.encode())

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
        def _receive(self, sender, arg: System.IO.Ports.SerialDataReceivedEventArgs) -> None:
            self.received_data.put(self._serial_port.ReadExisting())

    else:
        """
        Serial Port Reading Implementation on Unix.
        """
        def _receive(self) -> None:
            """
            This threads blocks until data on the serial port is available. If after 5 s now data has come it is assumed
            that the connection is lost.
            """
            while self.connected.is_set():
                try:
                    received = os.read(self._file_descriptor, Driver._IO_BUFFER_SIZE)
                    self.received_data.put(received.decode())
                except OSError:
                    logging.error("Connection to %s lost", self.device_name)
                    # Device might not be closed properly, so we mark the descriptor as invalid
                    self._file_descriptor = -1
                    self.connected.clear()

    def get_data(self) -> str:
        try:
            received_data: str = self.received_data.get(block=True, timeout=Driver._MAX_WAIT_TIME)
            return received_data
        except queue.Empty:
            self.connected.clear()
            logging.error("Connection to %s lost", self.device_name)
            if platform.system() != "Windows":
                self._file_descriptor = -1
            raise OSError

    @abc.abstractmethod
    def _encode_data(self) -> None:
        """
        Encodes incoming data of the serial device. Each package has a package identifier, to decide the decoding
        algorithm of it.
        """

    @abc.abstractmethod
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
