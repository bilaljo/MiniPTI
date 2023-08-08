import enum
import itertools
import logging
import os
import queue
import threading
import time
from collections import deque
from configparser import ConfigParser
from dataclasses import dataclass, asdict
from typing import Final, Sequence, Union

from fastcrc import crc16
from overrides import override

from . import serial_device


@dataclass
class DAQData:
    ref_signal: Union[queue.Queue, deque, Sequence]
    ac_coupled: Union[queue.Queue, deque, Sequence]
    dc_coupled: Union[queue.Queue, deque, Sequence]


_Samples = deque[int]


class BMS(enum.IntEnum):
    SHUTDOWN = 0xFF
    SHUTDOWN_INDEX = 1
    VALID_IDENTIFIER_INDEX = 3
    EXTERNAL_DC_POWER_INDEX = 5
    CHARGING_INDEX = 7
    MINUTES_LEFT_INDEX = 9
    BATTERY_PERCENTAGE_INDEX = 13
    BATTERY_TEMPERATURE_INDEX = 15
    CURRENT_INDEX = 19
    VOLTAGE_INDEX = 23
    FULL_CHARGED_CAPACITY_INDEX = 27
    REMAINING_CAPACITY_INDEX = 31


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
class PackageData:
    DAQ: DAQData
    BMS: queue.Queue


@dataclass
class Valve:
    automatic_switch: bool
    period: int
    duty_cycle: int


@dataclass
class DAQ:
    number_of_samples: int
    ref_period: int


@dataclass
class MotherBoardConfig:
    valve: Valve
    daq: DAQ


class Driver(serial_device.Driver):
    """
    This class provides an interface for receiving data from the serial port of a USB connected DAQ
    system. The data is accordingly to a defined protocol encoded and build into a packages of
    samples.
    """
    _PACKAGE_SIZE_START_INDEX: Final[int] = 1
    _PACKAGE_SIZE_END_INDEX: Final[int] = 9
    _CRC_START_INDEX: Final[int] = 4
    _DAQ_PACKAGE_SIZE: Final[int] = 4109
    _BMS_PACKAGE_SIZE: Final[int] = 39
    _WORD_SIZE: Final[int] = 32

    HARDWARE_ID: Final[str] = b"0001"
    NAME: Final[str] = "Motherboard"

    _CHANNELS: Final[int] = 3

    def __init__(self):
        serial_device.Driver.__init__(self)
        self.connected = threading.Event()
        self.data = PackageData(DAQData(queue.Queue(maxsize=Driver._QUEUE_SIZE),
                                        queue.Queue(maxsize=Driver._QUEUE_SIZE),
                                        queue.Queue(maxsize=Driver._QUEUE_SIZE)),
                                queue.Queue(maxsize=Driver._QUEUE_SIZE))
        self._encoded_buffer = DAQData(deque(), [deque(), deque(), deque()],
                                       [deque(), deque(), deque()])
        self._sample_numbers = deque(maxlen=2)
        self.synchronize = False
        self.config: Union[MotherBoardConfig, None] = None
        self.shutdown = threading.Event()
        self.config_path = f"{os.path.dirname(__file__)}/configs/motherboard.ini"
        self.config_parser = ConfigParser()
        self.automatic_switch = threading.Event()
        self.bypass = False
        self.running = threading.Event()
        self.running.clear()
        self.new_run: bool = True
        self.load_config()

    @property
    def device_id(self) -> str:
        return Driver.HARDWARE_ID

    @property
    def device_name(self) -> str:
        return Driver.NAME

    @property
    def bms(self) -> BMSData:
        return self.data.BMS.get(block=True)

    @property
    def ref_signal(self) -> deque:
        return self.data.DAQ.ref_signal.get(block=True)

    @property
    def dc_coupled(self) -> deque:
        return self.data.DAQ.dc_coupled.get(block=True)

    @property
    def ac_coupled(self) -> deque:
        return self.data.DAQ.ac_coupled.get(block=True)

    @property
    def buffer_size(self) -> int:
        return len(self._package_buffer)

    @property
    def encoded_buffer_ref_size(self) -> int:
        return len(self._encoded_buffer.ref_signal)

    @property
    def encoded_buffer_ac_size(self) -> int:
        return len(self._encoded_buffer.ac_coupled[0])

    @property
    def encoded_buffer_dc_size(self) -> int:
        return len(self._encoded_buffer.dc_coupled[0])

    @property
    def bms_package_empty(self) -> bool:
        return self.data.BMS.empty()

    @property
    def saved_sample_numbers(self) -> int:
        return len(self._sample_numbers)

    def clear_buffer(self) -> None:
        self._package_buffer = ""
        self.data.DAQ = DAQData(queue.Queue(maxsize=Driver._QUEUE_SIZE),
                                queue.Queue(maxsize=Driver._QUEUE_SIZE),
                                queue.Queue(maxsize=Driver._QUEUE_SIZE))

    @staticmethod
    def _binary_to_2_complement(number: int, byte_length: int) -> int:
        if number & (1 << (byte_length - 1)):
            return number - (1 << byte_length)
        return number

    def load_config(self) -> None:
        self.config_parser.read(self.config_path)
        valve_config = Valve(automatic_switch=self.config_parser.getboolean("Valve", "automatic_switch"),
                             period=self.config_parser.getint("Valve", "period"),
                             duty_cycle=self.config_parser.getint("Valve", "duty_cycle"))
        daq_config = DAQ(number_of_samples=self.config_parser.getint("DAQ", "number_of_samples"),
                         ref_period=self.config_parser.getint("DAQ", "ref_period"))
        self.config = MotherBoardConfig(valve_config, daq_config)
        if valve_config.automatic_switch:
            self.automatic_switch.set()

    def save_config(self) -> None:
        self.config_parser["Valve"] = asdict(self.config.valve)
        with open(self.config_path, "w") as savefile:
            self.config_parser.write(savefile)

    @staticmethod
    def _encode_binary(raw_data: Sequence) -> tuple[_Samples, list[_Samples], list[_Samples]]:
        """
        A block of data has the following structure:
        Ref, DC 1, DC 2, DC 3, DC, 4 AC 1, AC 2, AC 3, AC 4
        These byte words are 4 bytes wide and hex decimal decoded. These big byte word of size 32
        repeats periodically. It starts with below the first 10 bytes (meta information) and ends
        before the last 4 bytes (crc checksum).
        """
        raw_data = raw_data[Driver._PACKAGE_SIZE_END_INDEX:Driver._DAQ_PACKAGE_SIZE - Driver._CRC_START_INDEX]
        ref: _Samples = deque()
        ac: list[_Samples] = [deque(), deque(), deque()]
        dc: list[_Samples] = [deque(), deque(), deque(), deque()]
        for i in range(0, len(raw_data), Driver._WORD_SIZE):
            ref.append(int(raw_data[i:i + 4], base=16))
            # AC signed
            ac_value = Driver._binary_to_2_complement(int(raw_data[i + 4:i + 8], base=16), 16)
            ac[0].append(ac_value)
            ac_value = Driver._binary_to_2_complement(int(raw_data[i + 8:i + 12], base=16), 16)
            ac[1].append(ac_value)
            ac_value = Driver._binary_to_2_complement(int(raw_data[i + 12:i + 16], base=16), 16)
            ac[2].append(ac_value)
            # DC unsigned
            dc[0].append(int(raw_data[i + 16:i + 20], base=16))
            dc[1].append(int(raw_data[i + 20:i + 24], base=16))
            dc[2].append(int(raw_data[i + 24:i + 28], base=16))
            dc[3].append(int(raw_data[i + 28:i + 32], base=16))
        return ref, ac, dc

    def reset(self) -> None:
        self._reset()
        self.clear_buffer()

    def _reset(self) -> None:
        self._encoded_buffer.ref_signal = deque()
        self._encoded_buffer.dc_coupled = [deque(), deque(), deque()]
        self._encoded_buffer.ac_coupled = [deque(), deque(), deque()]
        self._sample_numbers = deque(maxlen=2)
        self._package_buffer = ""
        self.synchronize = True

    @override
    def _encode(self, data: str) -> None:
        if data[0] == "D" and len(data) == Driver._DAQ_PACKAGE_SIZE:
            self._encode_daq(data)
        elif data[0] == "B" and len(data) == Driver._BMS_PACKAGE_SIZE:
            self._encode_bms(data)
        elif data[0] == "S" and len(data) == 7:
            self._check_ack(data)

    def _encode_daq(self, data: str) -> None:
        """
        The data is encoded according to the following protocol:
            - The first two bytes describes the send command
            - Byte 2 up to 10 describe the package number of the send package
            - Byte 10 to 32 contain the data as period sequence of blocks in hex decimal
            - The last 4 bytes represent a CRC checksum in hex decimal
        """
        if not Driver._crc_check(data, "DAQ"):
            self._reset()  # The data is not trustful, and it should be waited for new
            return
        self._sample_numbers.append(data[Driver._PACKAGE_SIZE_START_INDEX:Driver._PACKAGE_SIZE_END_INDEX])
        if len(self._sample_numbers) > 1 and not self._check_package_difference():
            self._reset()
            self.synchronize = True
        ref_signal, ac_coupled, dc_coupled = Driver._encode_binary(data)
        if self.synchronize:
            self._reset()
            self._synchronize_with_ref(ref_signal, ac_coupled, dc_coupled)
        self._encoded_buffer.ref_signal.extend(ref_signal)
        for channel in range(Driver._CHANNELS):
            self._encoded_buffer.dc_coupled[channel].extend(dc_coupled[channel])
            self._encoded_buffer.ac_coupled[channel].extend(ac_coupled[channel])

    def _encode_bms(self, data: str) -> None:
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
        if not Driver._crc_check(data, "BMS"):
            return
        if int(data[BMS.SHUTDOWN_INDEX:BMS.SHUTDOWN_INDEX + 2], base=16) < BMS.SHUTDOWN:
            self.shutdown.set()
        if not int(data[BMS.VALID_IDENTIFIER_INDEX:BMS.VALID_IDENTIFIER_INDEX + 2], base=16):
            logging.error("Invalid package from BMS")
            return
        bms = BMSData(
            external_dc_power=bool(int(data[BMS.EXTERNAL_DC_POWER_INDEX:BMS.EXTERNAL_DC_POWER_INDEX + 2], base=16)),
            charging=bool(int(data[BMS.CHARGING_INDEX:BMS.CHARGING_INDEX + 2], base=16)),
            minutes_left=int(data[BMS.MINUTES_LEFT_INDEX:BMS.MINUTES_LEFT_INDEX + 4], base=16),
            battery_percentage=int(data[BMS.BATTERY_PERCENTAGE_INDEX:BMS.BATTERY_PERCENTAGE_INDEX + 2], base=16),
            battery_temperature=int(data[BMS.BATTERY_TEMPERATURE_INDEX:BMS.BATTERY_TEMPERATURE_INDEX + 4], base=16),
            battery_current=Driver._binary_to_2_complement(int(data[BMS.CURRENT_INDEX:BMS.CURRENT_INDEX + 4], base=16),
                                                           byte_length=16),
            battery_voltage=int(data[BMS.VOLTAGE_INDEX: BMS.VOLTAGE_INDEX + 4], base=16),
            full_charged_capacity=int(data[BMS.FULL_CHARGED_CAPACITY_INDEX:BMS.FULL_CHARGED_CAPACITY_INDEX + 4],
                                      base=16),
            remaining_capacity=int(data[BMS.REMAINING_CAPACITY_INDEX:BMS.REMAINING_CAPACITY_INDEX + 4], base=16))
        if bms.charging:
            bms.minutes_left = float("inf")
        self.data.BMS.put(bms)

    @staticmethod
    def _crc_check(data: str, source: str) -> bool:
        crc_calculated = crc16.arc(data[:-Driver._CRC_START_INDEX].encode())
        crc_received = int(data[-Driver._CRC_START_INDEX:], base=16)
        if crc_calculated != crc_received:  # Corrupted data
            logging.error(f"CRC value of {source} isn't equal to transmitted. Got {crc_received:04X} "
                          f"instead of {crc_calculated:04X}.")
            return False
        return True

    def _check_package_difference(self) -> bool:
        package_difference = int(self._sample_numbers[1], base=16) - int(self._sample_numbers[0],  base=16)
        if package_difference != 1:
            logging.error(f"Missing {package_difference} packages.")
            return False
        return True

    def _synchronize_with_ref(self, ref_signal: _Samples, ac_coupled: list[_Samples],
                              dc_coupled: list[_Samples]) -> None:
        logging.warning("Trying to synchronise")
        while sum(itertools.islice(ref_signal, 0, self.config.daq.ref_period // 2)):
            ref_signal.popleft()
            for channel in range(Driver._CHANNELS):
                ac_coupled[channel].popleft()
                dc_coupled[channel].popleft()
            dc_coupled[Driver._CHANNELS].popleft()
        if len(ref_signal) < self.config.daq.ref_period // 2:
            return
        self.synchronize = False

    def build_sample_package(self) -> None:
        """
        Creates a package of samples that represents approximately 1 s data. It contains 8000
        samples.
        """
        ref = [self._encoded_buffer.ref_signal.popleft() for _ in range(self.config.daq.number_of_samples)]
        self.data.DAQ.ref_signal.put(ref)
        if sum(itertools.islice(ref, 0, self.config.daq.ref_period // 2)):
            logging.warning("Not synchron with reference signal")
            self._reset()
            return
        dc_package = [[], [], []]
        ac_package = [[], [], []]
        for _ in itertools.repeat(None, self.config.daq.number_of_samples):
            for channel in range(Driver._CHANNELS):
                dc_package[channel].append(self._encoded_buffer.dc_coupled[channel].popleft())
                ac_package[channel].append(self._encoded_buffer.ac_coupled[channel].popleft())
        self.data.DAQ.dc_coupled.put(dc_package)
        self.data.DAQ.ac_coupled.put(ac_package)

    def set_valve(self) -> None:
        if self.bypass:
            self.write(serial_device.SerialStream("SBP0000"))
            self.bypass = False
        else:
            self.write(serial_device.SerialStream("SBP0001"))
            self.bypass = True

    def _process_data(self) -> None:
        self._reset()
        self.data = PackageData(DAQData(queue.Queue(maxsize=Driver._QUEUE_SIZE),
                                        queue.Queue(maxsize=Driver._QUEUE_SIZE),
                                        queue.Queue(maxsize=Driver._QUEUE_SIZE)),
                                queue.Queue(maxsize=Driver._QUEUE_SIZE))
        self._package_buffer = ""
        self._encoded_buffer = DAQData(deque(), [deque(), deque(), deque()], [deque(), deque(), deque()])
        self._sample_numbers = deque(maxlen=2)
        while self.connected.is_set():
            if self.new_run:
                self.reset()
                self.new_run = False
            self._encode_data()
            if self.running.is_set() and len(self._encoded_buffer.ref_signal) >= self.config.daq.number_of_samples:
                self.build_sample_package()
        self.new_run = True

    def automatic_valve_change(self) -> None:
        """
        Periodically bypass a valve. The duty cycle defines how much time for each part (bypassed
        or not) is spent.
        """
        def switch() -> None:
            while self.connected and self.automatic_switch.set():
                if self.bypass:
                    self.set_valve()
                    time.sleep(self.config.valve.period * self.config.valve.duty_cycle / 100)
                else:
                    self.set_valve()
                    time.sleep(self.config.valve.period * (1 - self.config.valve.duty_cycle / 100))

        threading.Thread(target=switch, daemon=True).start()

    def do_shutdown(self) -> None:
        self.write(serial_device.SerialStream("SHD0001"))
