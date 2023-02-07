import abc
import logging
import queue
import re
import threading
import time
from dataclasses import dataclass
from enum import Enum

import serial
from serial.tools import list_ports
import clr
import System.IO.Ports


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


class Serial:
    QUEUE_SIZE = 15
    WAIT_TIME = 50  # ms

    TERMINATION_SYMBOL = b"\n"
    NUMBER_OF_HEX_BYTES = 4

    def __init__(self):
        self.device = serial.Serial()
        self.received_data = queue.Queue(maxsize=Serial.QUEUE_SIZE)
        self.connected = False
        self.running = threading.Event()
        self.serial_port = System.IO.Ports.SerialPort()
        self.write_buffer = queue.Queue()
        self.ready_write = threading.Event()
        self.last_written_message = b""

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
        representation += f"device={self.device}, received_data={self.received_data})"
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
        self.last_written_message = message
        self.write_buffer.put(message, block=False)

    def _write(self):
        while self.connected:
            if self.ready_write.wait() and self.write_buffer.not_empty:
                self.device.write(self.write_buffer.get() + Serial.TERMINATION_SYMBOL)
                self.ready_write.clear()

    def __enter__(self):
        self.find_port()

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    @abc.abstractmethod
    def _encode_data(self):
        ...

    def find_port(self):
        """
        To recognise the correct port the ports are checked for their correct behavior. The correct port would produce
        the correct size of package in the given time.
        """
        for port in list_ports.comports():
            try:
                device = serial.Serial(port=port.device, write_timeout=Serial.WAIT_TIME,
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
                self.device.port = port.device
                logging.info(f"Found {self.device_name} at {self.device.port}")
                break
            else:
                device.close()
        else:
            logging.error(f"Could not find {self.device_name}")
            raise SerialError("Could not find {self.device_name}")

    def open(self):
        if self.device.port:
            logging.info(f"Connected with {self.device_name}")
            self.serial_port = System.IO.Ports.SerialPort(self.device.port)
            self.serial_port += System.IO.Ports.SerialDataReceivedEventHandler(self.receive)
            self.serial_port.open()
            self.running.set()
            self.connected = True
            threading.Thread(target=self._write).start()
            threading.Thread(target=self.encode).start()
        else:
            logging.error(f"Could not connect with {self.device_name}")
            raise SerialError(f"Could not connect with {self.device_name}")

    def is_open(self):
        pass

    def close(self):
        if self.device.is_open:
            self.serial_port.close()
            self.connected = False

    def receive(self, sender: System.IO.Ports.SerialPort, e: System.IO.Ports.SerialDataReceivedEventArgs):
        serial_port = sender
        self.received_data.put(serial_port.ReadExisting())

    def encode(self):
        while self.running:
            self._encode_data()
