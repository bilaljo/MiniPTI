import abc
import copy
import logging
import queue
import re
import threading
from dataclasses import dataclass
from enum import Enum
import io
import os
import platform
if platform.system() == "Windows":
    import clr
    import System.IO.Ports
else:
    import termios
    import signal

from statemachine import StateMachine, State
from serial.tools import list_ports_posix


@dataclass
class Data:
    ...


class DriverStateMachine(StateMachine):
    disconnected = State("Disconnected", initial=True)
    connected = State("Connected")
    disabled = State("Disabled")
    initialized = State("Init")
    enabled = State("Enabled")

    connect = disconnected.to(connected)
    initialize = connected.to(initialized)
    enable = initialized.to(enabled) | disabled.to(enabled)
    disable = enabled.to(disabled) | connected.to(connected)


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
    HARDWARE_ID = re.compile("GHI[0-9a-fA-F]{4}", flags=re.MULTILINE)
    ERROR = re.compile("ERR[0-9a-fA-F]{4}", flags=re.MULTILINE)
    HEX_VALUE = re.compile("[0-9a-fA-F]{4}", flags=re.MULTILINE)


class SerialError(Exception):
    pass


class Command:
    HARDWARE_ID = "GHI0000"


class Driver:
    QUEUE_SIZE = 15
    WAIT_TIME = 50

    TERMINATION_SYMBOL = "\n"
    NUMBER_OF_HEX_BYTES = 4
    START_DATA_FRAME = 1  # First symbol is the header

    def __init__(self):
        self.received_data = queue.Queue(maxsize=Driver.QUEUE_SIZE)
        self.connected = threading.Event()
        if platform.system() == "Windows":
            self.serial_port = System.IO.Ports.SerialPort()
        else:
            self.receive_signal = signal.signal(signal.SIGIO, self.receive)
            self.device = None
        self.port_name = ""
        self._write_buffer = queue.Queue()
        self.ready_write = threading.Event()
        self.ready_write.set()
        self.last_written_message = ""
        self.data = queue.Queue()
        self.state_machine = DriverStateMachine()

    if platform.system() == "Windows":
        def find_port(self) -> None:
            ports = System.IO.Ports.SerialPort.GetPortNames()
            for port in ports:
                serialport = System.IO.Ports.SerialPort(port)
                serialport.ReadTimeout = 500
                serialport.DataReceived += System.IO.Ports.SerialDataReceivedEventHandler(self.receive)
                try:
                    serialport.Open()
                except System.UnauthorizedAccessException:
                    continue
                serialport.WriteLine(Command.HARDWARE_ID)
                if self.get_hardware_id() == self.device_id:
                    self.port_name = port
                    logging.info(f"Found {self.device_name} at {self.port_name}")
                    serialport.Close()
                    break
                else:
                    serialport.Close()
            else:
                logging.error(f"Could not find {self.device_name}")
                raise SerialError("Could not find {self.device_name}")
    else:
        def find_port(self) -> None:
            for port in list_ports_posix.comports():
                self.device = os.open(path=port, flags=os.O_RDWR | os.O_NOCTTY | os.O_SYNC)

    def open(self) -> None:
        if self.port_name:
            logging.info(f"Connected with {self.device_name}")
            self.serial_port = System.IO.Ports.SerialPort()
            self.serial_port.PortName = self.port_name
            self.serial_port.DataReceived += System.IO.Ports.SerialDataReceivedEventHandler(self.receive)
            self.serial_port.Open()
            self.connected.set()
            self.state_machine.connect()
            threading.Thread(target=self._write, daemon=True).start()
            threading.Thread(target=self.encode, daemon=True).start()
        else:
            logging.error(f"Could not connect with {self.device_name}")
            raise SerialError(f"Could not connect with {self.device_name}")

    @property
    @abc.abstractmethod
    def device_id(self) -> str | int:
        ...

    @property
    @abc.abstractmethod
    def device_name(self) -> str:
        ...

    @property
    @abc.abstractmethod
    def end_data_frame(self) -> int:
        ...

    def __repr__(self) -> str:
        class_name = self.__class__.__name__
        representation = f"{class_name}(termination_symbol={Driver.TERMINATION_SYMBOL}," \
                         f" device_id={self.device_id}, portname={self.port_name}, received_data={self.received_data})"
        return representation

    def get_hardware_id(self) -> str:
        hardware_id = Patterns.HARDWARE_ID.search(self.received_data.get())
        if hardware_id is not None:
            hardware_id = hardware_id.group()
            return Patterns.HEX_VALUE.search(hardware_id).group()
        else:
            self.get_hardware_id()

    def command_error_handing(self, received: bytes | bytearray) -> None:
        if Patterns.ERROR.search(received) is not None:
            match Patterns.HEX_VALUE.search(Patterns.ERROR.search(received).group()).group():
                case Error.COMMAND:
                    raise SerialError(f"Packet length != 7 characters ('\n' excluded) from {self.serial_port}")
                case Error.PARAMETER:
                    raise SerialError(f"Error converting the hex parameter from {self.serial_port}")
                case Error.COMMAND:
                    raise SerialError(f"Request consists of an unknown/invalid command from {self.serial_port}")
                case Error.UNKNOWN_COMMAND:
                    raise SerialError(f"Unknown command from {self.serial_port}")

    def write(self, message: str) -> None:
        self._write_buffer.put(message, block=False)

    def _write(self) -> None:
        while self.connected.is_set():
            if self.ready_write.wait():
                self.last_written_message = self._write_buffer.get(block=True)
                self.serial_port.WriteLine(self.last_written_message)
                self.ready_write.clear()

    def is_open(self) -> bool:
        return self.serial_port.IsOpen

    def close(self) -> None:
        if self.serial_port.IsOpen:
            self.connected.clear()
            self.serial_port.Close()

    if platform.system() == "Windows":
        def receive(self, sender: System.IO.Ports.SerialPort, arg: System.IO.Ports.SerialDataReceivedEventArgs) -> None:
            self.received_data.put(sender.ReadExisting())
    else:
        def receive(self, status: int) -> None:
            self.received_data.put()

    @abc.abstractmethod
    def _extract_data(self, data: list[str]) -> Data:
        ...

    def _encode_data(self) -> None:
        received_data = self.received_data.get(block=True)  # type: str
        for received in received_data.split(Driver.TERMINATION_SYMBOL):
            if not received:
                continue
            match received[0]:
                case "N":
                    logging.error(f"Invalid command {received}")
                    self.ready_write.set()
                case "S" | "C":
                    last_written = self.last_written_message
                    if received != last_written and received != last_written.capitalize():
                        logging.error(f"Received message {received} message, expteced {last_written}")
                    else:
                        logging.debug(f"Command {received} successfully applied")
                    self.ready_write.set()
                case "L":
                    data_frame = received.split("\t")[Driver.START_DATA_FRAME:self.end_data_frame]
                    extracted_data = self._extract_data(data_frame)
                    self.data.put(copy.deepcopy(extracted_data))
                case _:  # Broken data frame without header char
                    logging.error("Received invalid package without header")
                    self.ready_write.set()
                    continue

    def encode(self) -> None:
        while self.connected.is_set():
            self._encode_data()
