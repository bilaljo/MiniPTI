import abc
import functools
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
    _STREAM_PATTERN = re.compile(r"[GSC][a-zA-Z][\da-zA-Z][\da-fA-F]{4}")  # 4 Hex Digits
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
    MAX_RESPONSE_TIME = 500e-3  # 100 ms response time
    _MAX_WAIT_TIME = 5  # s

    TERMINATION_SYMBOL = "\n"
    NUMBER_OF_HEX_BYTES = 4
    _START_DATA_FRAME = 1
    IO_BUFFER_SIZE = 8000
    SEARCH_ATTEMPTS = 3

    def __init__(self):
        self.port_name = ""
        self._write_buffer = queue.Queue()
        self.data = queue.Queue()
        self.ready_write = threading.Event()
        self.ready_write.set()
        self.last_written_message = ""
        if platform.system() == "Windows":
            self.serial_port = System.IO.Ports.SerialPort()
            self._received_flag = 0
            self._last_flag_value = 0
            self._flag_lock = threading.Lock()
        else:
            self.file_descriptor = -1
            self.file_descriptor_lock = threading.Lock()
        self.connected = threading.Event()
        self.received_data = queue.Queue()

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
        for _ in range(Driver.SEARCH_ATTEMPTS):
            for port in list_ports.comports():
                try:
                    with serial.Serial(port.name, timeout=Driver.MAX_RESPONSE_TIME,
                                       write_timeout=Driver.MAX_RESPONSE_TIME) as device:
                        device.write(Command.HARDWARE_ID + Driver.TERMINATION_SYMBOL.encode())
                        time.sleep(0.1)
                        available_bytes = device.in_waiting
                        self.received_data.put(device.read(available_bytes))
                        if self.get_hardware_id() == self.device_id:
                            self.port_name = port.name
                            logging.info(f"Found {self.device_name} at {self.port_name}")
                            return
                except serial.SerialException:
                    continue
        else:
            raise OSError(f"Could not find {self.device_name}. Maybe it is already connected")

    if platform.system() == "Windows":
        def open(self) -> None:
            if self.port_name and not self.is_open:
                self.serial_port = System.IO.Ports.SerialPort()
                self.serial_port.PortName = self.port_name
                self.serial_port.DataReceived += System.IO.Ports.SerialDataReceivedEventHandler(self._receive)
                self.serial_port.Open()
                self.connected.set()
                logging.info("Connected with %s", self.device_name)
            else:
                raise OSError("Could not find %s", self.device_name)
    else:
        def open(self) -> None:
            if self.port_name and not self.is_open:
                try:
                    self.file_descriptor = os.open(path=self.port_name, flags=os.O_RDWR | os.O_NOCTTY | os.O_SYNC)
                    old_attribute = termios.tcgetattr(self.file_descriptor)
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
                    termios.tcsetattr(self.file_descriptor, termios.TCSANOW, new_attribute)
                except OSError as e:
                    logging.debug("Error caused by %s", e)
                    raise OSError("Could not find %s", self.device_name)
                self.connected.set()
                logging.info(f"Connected with {self.device_name}")
            else:
                raise OSError("Could not find %s", self.device_name)

    def run(self) -> None:
        threading.Thread(target=self._write, daemon=True, name=f"{self.device_name} Write Thread").start()
        if platform.system() == "Windows":
            threading.Thread(target=self._timeout, daemon=True,
                             name=f"{self.device_name} Timeout Watchdog thread").start()
        threading.Thread(target=self._receive, daemon=True, name=f"{self.device_name} Receive Thread").start()
        threading.Thread(target=self._process_data, daemon=True, name=f"{self.device_name} Processing Thread").start()

    if platform.system() == "Windows":
        def _timeout(self) -> None:
            time.sleep(Driver.MAX_RESPONSE_TIME)
            with self._flag_lock:
                if self._last_flag_value != self._received_flag:
                    timeout = False
                    self._last_flag_value = self._received_flag
                else:
                    timeout = True
            if timeout:
                logging.error("Lost connection to %s", self.device_name)
                self.connected.clear()

    def get_hardware_id(self) -> Union[bytes, None]:
        try:
            received_data: bytes = self.received_data.get(timeout=Driver.MAX_RESPONSE_TIME)
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
            if self.ready_write.wait(timeout=Driver.MAX_RESPONSE_TIME):
                self.last_written_message = self._write_buffer.get(block=True) + Driver.TERMINATION_SYMBOL
                try:
                    self._transfer()
                except OSError:
                    logging.error("Could not transfer %s to %s", self.last_written_message)
                    break
                logging.debug("%s written to %s", self.last_written_message[:-1], self.device_name)
                self.ready_write.clear()

    def _transfer(self) -> None:
        if platform.system() == "Windows":
            self.serial_port.Write(self.last_written_message)
        else:
            with self.file_descriptor_lock:
                os.write(self.file_descriptor, self.last_written_message.encode())

    def _check_ack(self, data: str) -> bool:
        last_written = self.last_written_message[:-1]
        if data != last_written and data != last_written.capitalize():
            logging.error("Received message %s message, expected  %s", data, self.last_written_message)
            success = False
        else:
            logging.debug("Command %s successfully applied", data[:-1])
            success = True
        self.ready_write.set()
        return success

    if platform.system() == "Windows":
        @property
        def is_open(self) -> bool:
            return self.serial_port.IsOpen
    else:
        @property
        def is_open(self) -> bool:
            return self.file_descriptor != -1

    if platform.system() == "Windows":
        def close(self) -> None:
            if self.serial_port is not None:
                self.connected.clear()
                self.serial_port.Close()
                logging.info("Closed connection to %s", self.device_name)
    else:
        def close(self) -> None:
            if self.file_descriptor != -1:
                self.connected.clear()
                with self.file_descriptor_lock:
                    os.close(self.file_descriptor)
                logging.info("Closed connection to %s", self.device_name)

    if platform.system() == "Windows":
        """
        Serial Port Reading Implementation on Windows.
        """
        def _receive(self, sender, arg: System.IO.Ports.SerialDataReceivedEventArgs) -> None:
            self.received_data.put(self.serial_port.ReadExisting())
            self._received_flag ^= 1
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
                    with self.file_descriptor_lock:
                        received = os.read(self.file_descriptor, Driver.IO_BUFFER_SIZE)
                    self.received_data.put(received.decode())
                except OSError:
                    logging.error("Connection to %s lost", self.device_name)
                    # Device might not be closed properly, so we mark the descriptor as invalid
                    self.file_descriptor = -1
                    self.connected.clear()

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
