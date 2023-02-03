import abc
import threading
import logging
import queue
import re
import time
from dataclasses import dataclass
from enum import Enum

import asyncio
import serial_asyncio
import serial
from serial.tools import list_ports


class OutputProtocol(asyncio.Protocol):
    def __init__(self):
        asyncio.Protocol.__init__(self)
        self.received_data = queue.Queue()
        self.transport = None  # type: None | asyncio.Transport

    def connection_made(self, transport: asyncio.Transport) -> None:
        self.transport = transport

    def data_received(self, data: bytes) -> None:
        self.received_data.put(data)

    def write_data(self, data: bytes) -> None:
        self.transport.write(data)

    def connection_lost(self, exc: Exception | None) -> None:
        if exc:
            logging.error(f"Connection closed, caused by {exc}")
        else:
            logging.info("Connection closed")
        self.transport.close()


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
        self.port = None
        self.received_data = asyncio.Queue(maxsize=Serial.QUEUE_SIZE)
        self.connected = False
        self.serial_thread = None  # type: None | threading.Thread
        self.event_loop = asyncio.get_event_loop()
        self.protocol = None  # type: None | OutputProtocol
        self.transport = None  # type: None | asyncio.Transport

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
        representation += f"port={self.port}, device={self.device_name}, received_data={self.received_data})"
        return representation

    def get_hardware_id(self, received_data=None):
        if received_data is not None:
            hardware_id = Patterns.HARDWARE_ID.search(received_data)
        else:
            hardware_id = Patterns.HARDWARE_ID.search(self.received_data.get())
        if hardware_id is not None:
            hardware_id = hardware_id.group()
            return Patterns.HEX_VALUE.search(hardware_id).group()

    def command_error_handing(self, received):
        if Patterns.ERROR.search(received) is not None:
            match Patterns.HEX_VALUE.search(Patterns.ERROR.search(received).group()).group():
                case Error.COMMAND:
                    raise SerialError(f"Packet length != 7 characters ('\n' excluded) from {self.device_name}")
                case Error.PARAMETER:
                    raise SerialError(f"Error converting the hex parameter from {self.device_name}")
                case Error.COMMAND:
                    raise SerialError(f"Request consists of an unknown/invalid command from {self.device_name}")
                case Error.UNKNOWN_COMMAND:
                    raise SerialError(f"Unknown command from {self.device_name}")

    def write(self, message: bytes | bytearray):
        if self.connected:
            self.transport.write(message + Serial.TERMINATION_SYMBOL)

    def __enter__(self):
        self.find_port()
        self.open()

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    @abc.abstractmethod
    def _encode_data(self, received_data):
        ...

    async def encode(self):
        while True:
            received_data = await self.received_data.get()
            self._encode_data(received_data)

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
            if self.get_hardware_id(received_bytes) == self.device_id:
                device.close()
                self.port = port
                logging.info(f"Found {self.device_name} at {self.port}")
                break
            else:
                device.close()
        else:
            logging.error(f"Could not find {self.device_name}")
            raise SerialError("Could not find {self.device_name}")

    def open(self):
        if self.port:
            logging.info(f"Connected with {self.device_name}")

            async def main():
                receiver = serial_asyncio.create_serial_connection(self.event_loop, OutputProtocol, self.port)
                encoder = self.event_loop.create_task(self.encode())
                await receiver
                await encoder
            self.connected = True
            self.transport, self.protocol = self.event_loop.run_until_complete(main())
            self.serial_thread = threading.Thread(target=self.event_loop.run_forever)
            self.serial_thread.start()
        else:
            logging.error(f"Could not connect with {self.device_name}")
            raise SerialError(f"Could not connect with {self.device_name}")

    def close(self):
        if self.transport is not None:
            self.transport.close()
