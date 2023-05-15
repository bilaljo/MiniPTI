import abc
import logging
import os
import platform
import queue
import re
import threading
import time
from dataclasses import dataclass
from enum import Enum
from typing import Union

if platform.system() == "Windows":
    import win32con
    from win32 import win32file
    import pywintypes
else:
    import signal
import serial
from serial.tools import list_ports


class Driver:
    _QUEUE_SIZE = 15
    MAX_RESPONSE_TIME = 500e-3  # 100 ms response time

    TERMINATION_SYMBOL = "\n"
    NUMBER_OF_HEX_BYTES = 4
    _START_DATA_FRAME = 1

    def __init__(self):
        self.received_data = queue.Queue(maxsize=Driver._QUEUE_SIZE)
        self.device = None
        self.connected = threading.Event()
        self.port_name = ""
        self._write_buffer = queue.Queue()
        self.ready_write = threading.Event()
        self.ready_write.set()
        self.last_written_message = ""
        self.data = queue.Queue()
        self.running = threading.Event()
        self.device = None
        if platform.system() != "Windows":
            self.file_descriptor = -1

    def find_port(self) -> None:
        for port in list_ports.comports():
            try:
                device = serial.Serial(port.device, timeout=Driver.MAX_RESPONSE_TIME,
                                       write_timeout=Driver.MAX_RESPONSE_TIME)
            except serial.SerialException:
                continue
            device.write(Command.HARDWARE_ID + Driver.TERMINATION_SYMBOL.encode())
            time.sleep(0.1)
            available_bytes = device.in_waiting
            self.received_data.put(device.read(available_bytes))
            hardware_id = self.get_hardware_id()
            if hardware_id == self.device_id:
                self.port_name = port.device
                logging.info(f"Found {self.device_name} at {self.port_name}")
                device.close()
                break
            else:
                device.close()
        raise OSError("Could not find {self.device_name}")

    if platform.system() == "Windows":
        def open(self) -> None:
            if self.port_name:
                try:
                    self.device = win32file.CreateFile(self.port_name,
                                                       win32con.GENERIC_READ | win32con.GENERIC_WRITE,
                                                       0,
                                                       None,
                                                       win32con.OPEN_EXISTING,
                                                       win32con.FILE_ATTRIBUTE_NORMAL,
                                                       None)
                except pywintypes.error:
                    logging.error(f"Could not connect with {self.device_name}")
                    logging.info("The COM port of the device cannot be found anymore")

                win32file.SetCommMask(self.device, win32file.EV_RXCHAR)
                win32file.SetupComm(self.device, 4096, 4096)
                win32file.PurgeComm(self.device,
                                    win32file.PURGE_TXABORT | win32file.PURGE_RXABORT
                                    | win32file.PURGE_TXCLEAR | win32file.PURGE_RXCLEAR)
                self.connected.set()
                logging.info(f"Connected with {self.device_name}")
            else:
                raise OSError("Could not find {self.device_name}")
    else:
        def open(self) -> None:
            if self.port_name:
                signal.signal(signal.SIGIO, self._receive)
                self.file_descriptor = os.open(path=self.port_name, flags=os.O_RDWR | os.O_NOCTTY | os.O_NONBLOCK)
                self.connected.set()
                logging.info(f"Connected with {self.device_name}")
            else:
                raise OSError("Could not find {self.device_name}")

    def run(self) -> None:
        threading.Thread(target=self._write, daemon=True).start()
        if platform.system() == "Windows":
            threading.Thread(target=self._receive, daemon=True).start()
        threading.Thread(target=self._read, daemon=True).start()

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

    def write(self, message: Union[str, bytes, bytearray]) -> bool:
        """
        Sends data to the serial device if connected and no acknowledge is pending.
        """
        while self.connected.is_set():
            self.running.wait()
            if isinstance(message, str):
                self._write_buffer.put(message, block=False)
            else:
                self._write_buffer.put(message.decode(), block=False)
            return True
        return False

    if platform.system() == "Windows":
        def _write(self) -> None:
            while self.connected.is_set():
                self.running.wait()
                if self.ready_write.wait(timeout=Driver.MAX_RESPONSE_TIME):
                    self.last_written_message = self._write_buffer.get(block=True)
                    win32file.WriteFile(self.device, self.last_written_message + Driver.TERMINATION_SYMBOL, None)
                    self.ready_write.clear()
    else:
        def _write(self) -> None:
            while self.connected.is_set():
                self.running.wait()
                if self.ready_write.wait(timeout=Driver.MAX_RESPONSE_TIME):
                    self.last_written_message = self._write_buffer.get(block=True)
                    os.write(self.file_descriptor, (self.last_written_message + Driver.TERMINATION_SYMBOL).encode())
                    self.ready_write.clear()

    def _check_ack(self, data: str) -> bool:
        last_written = self.last_written_message
        if data != last_written and data != last_written.capitalize():
            logging.error(f"Received message {data} message, expected {last_written}")
            success = False
        else:
            logging.debug(f"Command {data} successfully applied")
            success = True
        self.ready_write.set()
        return success

    if platform.system() == "Windows":
        def is_open(self) -> bool:
            return self.device is not None
    else:
        def is_open(self) -> bool:
            return self.file_descriptor != -1

    if platform.system() == "Windows":
        def close(self) -> None:
            if self.device is not None:
                self.connected.clear()
                win32file.CloseHandle(self.device)
    else:
        def close(self) -> None:
            if self.file_descriptor != -1:
                os.close(self.file_descriptor)

    if platform.system() == "Windows":
        """
        Serial Port Reading Implementation on Windows.
        """
        def _receive(self) -> None:
            """
            Receiver thread for incoming data. The WaitComEvent method blocks the thread until a specific event occured.
            The event we are looking for has event mask value EV_RXCHAR. It is set, when a character (or more) is put
            into the input buffer.
            If the EV_RXCHAR event occurred the data can be read. While reading, a memoryview object is returned.
            """
            while self.connected.is_set():
                try:
                    self.running.wait()
                    rc, mask = win32file.WaitCommEvent(self.device, None)
                    flags, comstat = win32file.ClearCommError(self.device)
                    rc, data = win32file.ReadFile(self.device, comstat.cbInQue, None)
                    self.received_data.put(data.decode())
                except pywintypes.error:
                    logging.error(f"Connection to {self.device_name} lost")
    else:
        """
        Serial Port Reading Implementation on Unix.
        """
        def _receive(self, signum, frame) -> None:
            """
            Receiver signal handler for IO event. This function is chosen on a Unix based system.
            """
            buffer_size = os.stat(self.file_descriptor).st_size
            self.received_data.put(os.read(self.file_descriptor, buffer_size).decode())

    @abc.abstractmethod
    def encode_data(self) -> None:
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
