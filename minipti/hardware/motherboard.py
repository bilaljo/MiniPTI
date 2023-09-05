import dataclasses
import enum
import logging
import os
import queue
import threading
import time
from collections import deque
from dataclasses import dataclass
from typing import Final, Union
import json

import dacite
from numba import njit, prange
from fastcrc import crc16
from overrides import override
import numpy as np
from . import _json_parser

from . import serial_device
from . import protocolls


@dataclass
class ValveConfiguration:
    automatic_switch: bool
    period: int
    duty_cycle: int


class Valve:
    def __init__(self, driver: "Driver"):
        self.bypass = False
        self._set_bypass = protocolls.ASCIIHex("SBP0000")
        self.automatic_switch = threading.Event()
        self.configuration: Union[ValveConfiguration, None] = None
        self.driver: Union[None, "Driver"] = driver
        self.bypass = False
        self.config_path = f"{os.path.dirname(__file__)}/configs/motherboard/valve.json"
        self.load_configuration()

    def automatic_valve_change(self) -> None:
        """
        Periodically bypass a valve. The duty cycle defines how much time for each part (bypassed
        or not) is spent.
        """
        def switch() -> None:
            while self.driver.connected.is_set() and self.automatic_switch.is_set():
                self.set_valve()
                if self.bypass:
                    time.sleep(self.configuration.period * self.configuration.duty_cycle / 100)
                else:
                    time.sleep(self.configuration.period * (1 - self.configuration.duty_cycle / 100))
        threading.Thread(target=switch, daemon=True).start()

    def set_valve(self) -> None:
        self._set_bypass.value = self.bypass
        self.bypass = not self.bypass
        self.driver.write(self._set_bypass)

    def load_configuration(self) -> None:
        with open(self.config_path) as config:
            loaded_config = json.load(config)
            self.configuration = dacite.from_dict(ValveConfiguration, loaded_config["Valve"])

    def save_configuration(self) -> None:
        with open(self.config_path, "w") as configuration:
            valve = {"Valve": dataclasses.asdict(self.configuration)}
            configuration.write(_json_parser.to_json(valve) + "\n")
            logging.info("Saved valve configuration in %s", self.config_path)


class BMSIndex(enum.IntEnum):
    SHUTDOWN = 1
    VALID_IDENTIFIER = 3
    EXTERNAL_DC_POWER = 5
    CHARGING = 7
    MINUTES_LEFT = 9
    BATTERY_PERCENTAGE = 13
    BATTERY_TEMPERATURE = 15
    CURRENT = 19
    VOLTAGE = 23
    FULL_CHARGED_CAPACITY = 27
    REMAINING_CAPACITY = 31


@dataclass
class BMSData:
    external_dc_power: bool
    charging: bool
    minutes_left: Union[int, float]
    battery_percentage: int
    battery_temperature: float  # °C
    battery_current: int  # mA
    battery_voltage: int  # mV
    full_charged_capacity: int  # mAh
    remaining_capacity: int  # mAh


@dataclass
class BMSConfiguration:
    use_battery: bool


class BMS:
    PACKAGE_SIZE: Final = 39
    SHUTDOWN = 0xFF

    def __init__(self, driver: "Driver"):
        self._do_shutdown = protocolls.ASCIIHex("SHD0001")
        self.driver: Union[None, "Driver"] = None
        self.configuration: Union[None, BMSConfiguration] = None
        self.config_path = f"{os.path.dirname(__file__)}/configs/motherboard/bms.json"
        self.driver = driver
        self.load_configuration()

    def encode(self, data: str) -> None:
        shutdown = int(data[BMSIndex.SHUTDOWN:BMSIndex.SHUTDOWN + 2], base=16) < BMS.SHUTDOWN
        """
        The BMS data is encoded according to the following scheme:
        Every byte is an ASCII symbol. The bytes have the following meanings:
        1 - 2:
        Represent the package identifier
        2 - 4:
        - The next two bytes are the countdown of a shutdown. Attention: if this value is below 255 (0xFF),
        the motherboard will shut down itself soon.
        - The next
        """
        if not int(data[BMSIndex.VALID_IDENTIFIER:BMSIndex.VALID_IDENTIFIER + 2], base=16):
            logging.error("Invalid package from BMS")
            return
        bms = BMSData(
            external_dc_power=bool(int(data[BMSIndex.EXTERNAL_DC_POWER:BMSIndex.EXTERNAL_DC_POWER + 2], base=16)),
            charging=bool(int(data[BMSIndex.CHARGING:BMSIndex.CHARGING + 2], base=16)),
            minutes_left=int(data[BMSIndex.MINUTES_LEFT:BMSIndex.MINUTES_LEFT + 4], base=16),
            battery_percentage=int(data[BMSIndex.BATTERY_PERCENTAGE:BMSIndex.BATTERY_PERCENTAGE + 2], base=16),
            battery_temperature=int(data[BMSIndex.BATTERY_TEMPERATURE:BMSIndex.BATTERY_TEMPERATURE + 4], base=16),
            battery_current=Driver.binary_to_2_complement(int(data[BMSIndex.CURRENT:BMSIndex.CURRENT + 4], base=16)),
            battery_voltage=int(data[BMSIndex.VOLTAGE: BMSIndex.VOLTAGE + 4], base=16),
            full_charged_capacity=int(data[BMSIndex.FULL_CHARGED_CAPACITY:BMSIndex.FULL_CHARGED_CAPACITY + 4], base=16),
            remaining_capacity=int(data[BMSIndex.REMAINING_CAPACITY:BMSIndex.REMAINING_CAPACITY + 4], base=16),
            shutdown=shutdown)
        if bms.charging:
            bms.minutes_left = float("inf")
        self.driver.data.BMS.put(bms)

    def do_shutdown(self) -> None:
        self.driver.write(self._do_shutdown)

    def load_configuration(self) -> None:
        with open(self.config_path) as config:
            loaded_config = json.load(config)
            self.configuration = dacite.from_dict(BMSConfiguration, loaded_config["BMS"])

    def save_configuration(self) -> None:
        with open(self.config_path, "w") as configuration:
            valve = {"BMS": dataclasses.asdict(self.configuration)}
            configuration.write(_json_parser.to_json(valve) + "\n")
            logging.info("Saved valve BMS in %s", self.config_path)


@dataclass
class DAQConfiguration:
    number_of_samples: int
    ref_period: int


@dataclass
class DAQData:
    ref_signal: np.ndarray[np.uint16]
    ac_coupled: np.ndarray[np.int16]
    dc_coupled: np.ndarray[np.uint16]


class DAQ:
    _SEQUENCE_NUMBER: Final = 9
    PACKAGE_SIZE: Final = 4109
    _WORD_SIZE: Final = 32

    def __init__(self, driver: "Driver"):
        self._sample_numbers = deque(maxlen=2)
        self.synchronize = False
        self.configuration: Union[DAQConfiguration, None] = None
        self.encoded_buffer: Union[DAQData, None] = None
        self.current_sample = 0
        self.config_path = f"{os.path.dirname(__file__)}/configs/motherboard/daq.json"
        self.driver = driver
        self.load_configuration()

    def update_buffer_size(self) -> None:
        if self.driver.running.is_set():
            logging.warning("Encoding is running. Need to pause is to update the buffer size")
            self.driver.running.clear()
        self.encoded_buffer = DAQData(np.empty(self.configuration.number_of_samples),
                                      np.empty(shape=(3, self.configuration.ref_period)),
                                      np.empty(shape=(3, self.configuration.number_of_samples)))

    @njit(parallel=True)
    def _encode_binary(self, raw_data: str) -> None:
        """
        A block of data has the following structure:
        Ref, DC 1, DC 2, DC 3, DC, 4 AC 1, AC 2, AC 3, AC 4
        These byte words are 4 bytes wide and hex decimal decoded. These big byte word of size 32
        repeats periodically. It starts with below the first 10 bytes (meta information) and ends
        before the last 4 bytes (crc checksum).
        """
        raw_data = raw_data[DAQ._SEQUENCE_NUMBER:]
        for i in prange(0, len(raw_data), DAQ._WORD_SIZE):
            self.encoded_buffer.ref_signal[i] = int(raw_data[i:i + 4], base=16)
            for channel in range(3):
                dc = int(raw_data[i + 16 + channel * 4:i + 20 + channel * 4], base=16)
                self.encoded_buffer.dc_coupled[channel][i] = dc
                ac = Driver.binary_to_2_complement(int(raw_data[i + 16 + channel * 4:i + 20 + channel * 4], base=16))
                self.encoded_buffer.dc_coupled[channel][i] = ac
        self._sample_numbers += len(raw_data) // DAQ._WORD_SIZE

    def encode(self, data: str) -> None:
        """
        The data is encoded according to the following protocol:
            - The first two bytes describes the send command
            - Byte 2 up to 10 describe the package number of the send package
            - Byte 10 to 32 contain the data as period sequence of blocks in hex decimal
            - The last 4 bytes represent a CRC checksum in hex decimal
        """
        self._sample_numbers.append(data[:DAQ._SEQUENCE_NUMBER])
        if len(self._sample_numbers) > 1 and not self._check_package_difference():
            self.reset()
            self.synchronize = True
        self._encode_binary(data)
        if self.synchronize:
            self.reset()
            self._synchronize_with_ref()

    def _synchronize_with_ref(self) -> None:
        logging.warning("Trying to synchronise")
        self.current_sample -= np.argmin(self.encoded_buffer.ref_signal[:self.configuration.ref_period // 2])
        if self.current_sample < self.configuration.ref_period // 2:
            return
        self.synchronize = False

    def reset(self) -> None:
        self.current_sample = 0
        self._sample_numbers = deque(maxlen=2)
        self.synchronize = True

    def _check_package_difference(self) -> bool:
        package_difference = int(self._sample_numbers[1], base=16) - int(self._sample_numbers[0],  base=16)
        if package_difference != 1:
            logging.error(f"Missing {package_difference} packages.")
            return False
        return True

    def load_configuration(self) -> None:
        with open(self.config_path) as config:
            loaded_config = json.load(config)
            self.configuration = dacite.from_dict(DAQConfiguration, loaded_config["DAQ"])
        self.update_buffer_size()

    def save_configuration(self) -> None:
        with open(self.config_path, "w") as configuration:
            valve = {"DAQ": dataclasses.asdict(self.configuration)}
            configuration.write(_json_parser.to_json(valve) + "\n")
            logging.info("Saved valve DAQ configuration in %s", self.config_path)


@dataclass
class PackageData:
    DAQ: list[queue.Queue, queue.Queue, queue.Queue]
    BMS: queue.Queue


class PackageIndex(enum.IntEnum):
    REF = 0
    AC = 1
    DC = 2


class Driver(serial_device.Driver):
    """
    This class provides an interface for receiving data from the serial port of a USB connected DAQ
    system. The data is accordingly to a defined protocol encoded and build into a packages of
    samples.
    """
    _CRC_START: Final = 4

    HARDWARE_ID: Final = b"0001"
    NAME: Final = "Motherboard"

    _CHANNELS: Final = 3

    def __init__(self):
        serial_device.Driver.__init__(self)
        self.running = threading.Event()
        self.daq = DAQ(self)
        self.bms = BMS(self)
        self.valve = Valve(self)
        self.new_run = True
        self.data = PackageData([queue.Queue(maxsize=Driver._QUEUE_SIZE) for _ in range(3)],
                                queue.Queue(maxsize=Driver._QUEUE_SIZE))

    @property
    def device_id(self) -> bytes:
        return Driver.HARDWARE_ID

    @property
    def device_name(self) -> str:
        return Driver.NAME

    @property
    def bms_data(self) -> BMSData:
        return self.data.BMS.get(block=True)

    @property
    def ref_signal(self) -> deque:
        return self.data.DAQ[PackageIndex.REF].get(block=True)

    @property
    def dc_coupled(self) -> deque:
        return self.data.DAQ[PackageIndex.DC].get(block=True)

    @property
    def ac_coupled(self) -> deque:
        return self.data.DAQ[PackageIndex.AC].get(block=True)

    @property
    def buffer_size(self) -> int:
        return len(self._package_buffer)

    @property
    def bms_package_empty(self) -> bool:
        return self.data.BMS.empty()

    def clear_buffer(self) -> None:
        self._package_buffer = ""
        self.data.DAQ = [queue.Queue(maxsize=Driver._QUEUE_SIZE) for _ in range(3)]

    @staticmethod
    def binary_to_2_complement(number: int, byte_length: int = 16) -> int:
        if number & (1 << (byte_length - 1)):
            return number - (1 << byte_length)
        return number

    def reset(self) -> None:
        self.clear_buffer()

    @override
    def _encode(self, data: str) -> None:
        if data[0] == "D" and len(data) == DAQ.PACKAGE_SIZE:
            if not self._crc_check(data[1:], "DAQ"):
                return
            self.daq.encode(data[1:-Driver._CRC_START])
        elif data[0] == "B" and len(data) == BMS.PACKAGE_SIZE:
            if not self._crc_check(data[1:-Driver._CRC_START], "BMS"):
                return
            self.bms.encode(data)
        elif data[0] == "S" and len(data) == 7:
            self._check_ack(data)

    @staticmethod
    def _crc_check(data: str, source: str) -> bool:
        crc_calculated = crc16.arc(data[:-Driver._CRC_START].encode())
        crc_received = int(data[-Driver._CRC_START:], base=16)
        if crc_calculated != crc_received:  # Corrupted data
            logging.error(f"CRC value of {source} isn't equal to transmitted. Got {crc_received:04X} "
                          f"instead of {crc_calculated:04X}.")
            return False
        return True

    def build_sample_package(self) -> None:
        """
        Creates a package of samples that represents approximately 1 s data. It contains 8000
        samples.
        """
        if np.argmin(self.daq.encoded_buffer.ref_signal[:self.daq.configuration.ref_period // 2]):
            logging.warning("Not synchron with reference signal")
            self.daq.reset()
            return
        self.data.DAQ[PackageIndex.REF].put(self.daq.encoded_buffer.ref_signal.copy())
        self.data.DAQ[PackageIndex.AC].put(self.daq.encoded_buffer.ac_coupled.copy())
        self.data.DAQ[PackageIndex.DC].put(self.daq.encoded_buffer.dc_coupled.copy())

    def _process_data(self) -> None:
        self.daq.reset()
        self.data = PackageData([queue.Queue(maxsize=Driver._QUEUE_SIZE),
                                 queue.Queue(maxsize=Driver._QUEUE_SIZE),
                                 queue.Queue(maxsize=Driver._QUEUE_SIZE)],
                                queue.Queue(maxsize=Driver._QUEUE_SIZE))
        self._package_buffer = ""
        while self.connected.is_set():
            if self.new_run:
                self.reset()
                self.new_run = False
            self._encode_data()
            if self.running.is_set() and self.daq.current_sample == self.daq.configuration.number_of_samples:
                self.build_sample_package()
        self.new_run = True
