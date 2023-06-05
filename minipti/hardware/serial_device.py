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
    import win32con
    from win32 import win32file
    import pywintypes
else:
    import termios, signal, fcntl
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

    TERMINATION_SYMBOL = "\n"
    NUMBER_OF_HEX_BYTES = 4
    _START_DATA_FRAME = 1
    IO_BUFFER_SIZE = 4096
    SEARCH_ATTEMPTS = 3

    def __init__(self):
        self.device = None
        self.port_name = ""
        self._write_buffer = queue.Queue()
        self.data = queue.Queue()
        self.ready_write = threading.Event()
        self.ready_write.set()
        self.last_written_message = ""
        if platform.system() == "Windows":
            self.device = None
        else:
            self.file_descriptor = -1
            self.file_descriptor_lock = threading.Lock()
            self.new_data_queue = queue.Queue()
            signal.signal(signal.SIGIO, lambda signum, frame: self.new_data_queue.put(1))
        self.connected = threading.Event()
        self.received_data = queue.Queue()

    def find_port(self) -> None:
        for _ in range(Driver.SEARCH_ATTEMPTS):
            for port in list_ports.comports():
                try:
                    with serial.Serial(port.device, timeout=Driver.MAX_RESPONSE_TIME,
                                       write_timeout=Driver.MAX_RESPONSE_TIME) as device:
                        device.write(Command.HARDWARE_ID + Driver.TERMINATION_SYMBOL.encode())
                        time.sleep(0.1)
                        available_bytes = device.in_waiting
                        if platform.system() == "Windows":
                            self.received_data.put(device.read(available_bytes))
                        else:
                            self.received_data.put(device.read(available_bytes))
                        hardware_id = self.get_hardware_id()
                        if hardware_id == self.device_id:
                            self.port_name = port.device
                            logging.info(f"Found {self.device_name} at {self.port_name}")
                            return
                except serial.SerialException:
                    continue
        else:
            raise OSError("Could not find {self.device_name}")

    if platform.system() == "Windows":
        def open(self) -> None:
            if self.port_name and not self.is_open:
                try:
                    self.device = win32file.CreateFile("\\\\.\\" + self.port_name,
                                                       win32con.GENERIC_READ | win32con.GENERIC_WRITE,
                                                       0,
                                                       None,
                                                       win32con.OPEN_EXISTING,
                                                       win32con.FILE_ATTRIBUTE_NORMAL,
                                                       None)
                except pywintypes.error as e:
                    logging.debug("Error caused by %s", e)
                    raise OSError("Could not find %s", self.device_name)
                else:
                    win32file.SetCommMask(self.device, win32file.EV_RXCHAR)
                    win32file.SetupComm(self.device, Driver.IO_BUFFER_SIZE, Driver.IO_BUFFER_SIZE)
                    win32file.PurgeComm(self.device, win32file.PURGE_TXABORT | win32file.PURGE_RXABORT
                                        | win32file.PURGE_TXCLEAR | win32file.PURGE_RXCLEAR)
                    self.connected.set()
                    logging.info("Connected with %s", self.device_name)
            else:
                raise OSError("Could not find %s", self.device_name)
    else:
        def open(self) -> None:
            if self.port_name and not self.is_open:
                try:
                    self.file_descriptor = os.open(path=self.port_name, flags=os.O_NDELAY | os.O_ASYNC)
                    old_attribute = termios.tcgetattr(self.file_descriptor)
                    iflag, oflag, cflag, lflag, ispeed, ospeed, cc = old_attribute
                    cflag &= ~termios.PARENB
                    cflag &= ~termios.CSTOPB
                    cflag &= ~termios.CSIZE
                    cflag |= termios.CS8
                    cflag |= (termios.CLOCAL | termios.CREAD)
                    cflag &= ~(termios.ICANON | termios.ECHO | termios.ECHOE | termios.ISIG)
                    iflag &= ~(termios.IXON | termios.IXOFF | termios.IXANY)
                    oflag &= ~termios.OPOST
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
        threading.Thread(target=self._receive, daemon=True, name=f"{self.device_name} Receive Thread").start()
        threading.Thread(target=self._read, daemon=True, name=f"{self.device_name} Proccessing Thread").start()

    def _read(self):
        try:
            self._process_data()
        finally:
            self.close()

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
                self._transfer()
                logging.debug("%s written to %s", self.last_written_message[:-1], self.device_name)
                self.ready_write.clear()

    def _transfer(self) -> None:
        if platform.system() == "Windows":
            win32file.WriteFile(self.device, self.last_written_message.encode(), None)
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
            return self.device is not None
    else:
        @property
        def is_open(self) -> bool:
            return self.file_descriptor != -1

    if platform.system() == "Windows":
        def close(self) -> None:
            if self.device is not None:
                self.connected.clear()
                win32file.CloseHandle(self.device)
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
        def _receive(self) -> None:
            """
            Receiver thread for incoming data. The WaitComEvent method blocks the thread until a specific event
            occurred. The event we are looking for has event mask value EV_RXCHAR. It is set, when a character
            (or more) is put into the input buffer.
            If the EV_RXCHAR event occurred the data can be read.
            """
            while self.connected.is_set():
                try:
                    win32file.WaitCommEvent(self.device, None)
                    _, comstat = win32file.ClearCommError(self.device)
                    rc, data = win32file.ReadFile(self.device, comstat.cbInQue, None)
                    self.received_data.put(data.decode())
                    logging.debug("Data received")
                except pywintypes.error as e:
                    logging.error("Connection to %s lost", self.device_name)
                    logging.debug("Error caused by %s", e)
    else:
        """
        Serial Port Reading Implementation on Unix.
        """
        def _receive(self) -> None:
            """
            This threads blocks until data on the serial port is available.
            """
            while self.connected.is_set():
                try:
                    with self.file_descriptor_lock:
                        received = os.read(self.file_descriptor, Driver.IO_BUFFER_SIZE)
                    self.received_data.put(received.decode())
                except OSError as e:
                    logging.error("Connection to %s lost", self.device_name)
                    logging.debug("Error caused by %s", e)

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
