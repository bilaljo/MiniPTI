import enum
import itertools
import logging
import queue
import re
import threading
import time
from collections import deque
from dataclasses import dataclass, asdict
from typing import Sequence, Annotated

from fastcrc import crc16
from commentedconfigparser import CommentedConfigParser

import hardware.serial


@dataclass
class DAQData:
    ref_signal: queue.Queue | deque | Sequence
    ac_coupled: queue.Queue | deque | Sequence
    dc_coupled: queue.Queue | deque | Sequence


@dataclass
class Packages:
    DAQ = re.compile("00[0-9a-fA-F]{4108}", flags=re.MULTILINE)
    BMS = re.compile("01[0-9a-fA-F]{41}", flags=re.MULTILINE)


_Samples = deque[int]


class BMS(enum.IntEnum):
    SHUTDOWN_INDEX = 0
    SHUTDOWN = 0xFF
    VALID_IDENTIFIER_INDEX = 4
    EXTERNAL_DC_POWER_INDEX = 6
    CHARGING_INDEX = 8
    MINUTES_LEFT_INDEX = 10
    BATTERY_PERCENTAGE_INDEX = 14
    BATTERY_TEMPERATURE_INDEX = 16
    CURRENT_INDEX = 20
    VOLTAGE_INDEX = 24
    FULL_CHARGED_CAPACITY_INDEX = 28
    REMAINING_CAPACITY_INDEX = 32


@dataclass
class BMSData:
    external_dc_power: bool
    charging: bool
    minutes_left: int
    battery_percentage: int
    battery_temperature: float  # °C
    battery_current: int  # mA
    battery_voltage: int  # mV
    full_charged_capacity: int  # mAh
    remaining_capacity: int  # mAh


@dataclass
class PackageData:
    _QUEUE_SIZE = 15
    DAQ: DAQData
    BMS: queue.Queue


@dataclass
class Valve:
    automatic_switch: bool
    period: int
    duty_cycle: int


@dataclass
class MotherBoardConfig:
    valve: Valve


class Driver(hardware.serial.Driver):
    """
    This class provides an interface for receiving data from the serial port of a USB connected DAQ system.
    The data is accordingly to a defined protocol encoded and build into a packages of samples.
    """
    _PACKAGE_SIZE_START_INDEX = 2
    _PACKAGE_SIZE_END_INDEX = 10
    _CRC_START_INDEX = 4
    _PACKAGE_SIZE = 4110
    _WORD_SIZE = 32

    ID = b"0001"
    NAME = "Motherboard"

    _CHANNELS = 3
    REF_PERIOD = 100
    NUMBER_OF_SAMPLES = 8000

    def __init__(self):
        hardware.serial.Driver.__init__(self)
        self.connected = threading.Event()
        self._package_data = PackageData(
            DAQData(queue.Queue(maxsize=Driver._QUEUE_SIZE),
                    queue.Queue(maxsize=Driver._QUEUE_SIZE),
                    queue.Queue(maxsize=Driver._QUEUE_SIZE)),
            queue.Queue(maxsize=Driver._QUEUE_SIZE)
        )
        self._encoded_buffer = DAQData(deque(), [deque(), deque(), deque()], [deque(), deque(), deque()])
        self._sample_numbers = deque(maxlen=2)
        self._synchronize = True
        self.config: MotherBoardConfig | None = None
        self.shutdown = threading.Event()
        self.config_path = "hardware/configs/motherboard.conf"
        self.config_parser = CommentedConfigParser()
        self.automatic_switch = threading.Event()
        self.bypass = False
        self.load_config()

    @property
    def device_id(self) -> bytes:
        return Driver.ID

    @property
    def device_name(self) -> str:
        return Driver.NAME

    @property
    def bms(self) -> BMSData:
        return self._package_data.BMS.get(block=True)

    @property
    def ref_signal(self) -> deque:
        return self._package_data.DAQ.ref_signal.get(block=True)

    @property
    def dc_coupled(self) -> deque:
        return self._package_data.DAQ.dc_coupled.get(block=True)

    @property
    def ac_coupled(self) -> deque:
        return self._package_data.DAQ.ac_coupled.get(block=True)

    @staticmethod
    def _binary_to_2_complement(number: int, byte_length: int) -> int:
        if number & (1 << (byte_length - 1)):
            return number - (1 << byte_length)
        return number

    def load_config(self) -> None:
        self.config_parser.read(self.config_path)
        valve_config = Valve(
            automatic_switch=self.config_parser.getboolean("Valve", "automatic_switch"),
            period=self.config_parser.getint("Valve", "period"),
            duty_cycle=self.config_parser.getint("Valve", "duty_cycle"),
        )
        self.config = MotherBoardConfig(valve_config)
        if valve_config.automatic_switch:
            self.automatic_switch.set()

    def save_config(self) -> None:
        self.config_parser["Valve"] = asdict(self.config.valve)
        with open(self.config_path, "w") as savefile:
            self.config_parser.write(savefile)

    @staticmethod
    def _encode(raw_data: Sequence) -> tuple[_Samples, Annotated[list[_Samples], 3], Annotated[list[_Samples], 4]]:
        """
        A block of data has the following structure:
        Ref, DC 1, DC 2, DC 3, DC, 4 AC 1, AC 2, AC 3, AC 4
        These byte words are 4 bytes wide and hex decimal decoded. These big byte word of size 32 repeats periodically.
        It starts with below the first 10 bytes (meta information) and ends before the last 4 bytes (crc checksum).
        """
        raw_data = raw_data[Driver._PACKAGE_SIZE_END_INDEX:Driver._PACKAGE_SIZE - Driver._CRC_START_INDEX]
        ref: _Samples = deque()
        ac: list[_Samples] = [deque(), deque(), deque()]
        dc: list[_Samples] = [deque(), deque(), deque(), deque()]
        for i in range(0, len(raw_data), Driver._WORD_SIZE):
            ref.append(int(raw_data[i:i + 4], 16))
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

    def _reset(self) -> None:
        self._synchronize = True
        self._encoded_buffer.ref_signal = deque()
        self._encoded_buffer.dc_coupled = [deque(), deque(), deque()]
        self._encoded_buffer.ac_coupled = [deque(), deque(), deque()]
        self._sample_numbers = deque(maxlen=2)

    def _encode_data(self) -> None:
        """
        The data is encoded according to the following protocol:
            - The first two bytes describes the send command
            - Byte 2 up to 10 describe the package number of the send package
            - Byte 10 to 32 contain the data as period sequence of blocks in hex decimal
            - The last 4 bytes represent a CRC checksum in hex decimal
        """
        split_data = self.received_data.get(block=True).split("\n")
        for data in split_data:
            if Packages.DAQ.match(data):
                self._encode_daq(data)
            elif Packages.BMS.match(data):
                self._encode_bms(data)

    def _encode_daq(self, data: str) -> None:
        if not Driver._crc_check(data, "DAQ"):
            self._reset()  # The data is not trustful, and it should be waited for new
            return
        self._sample_numbers.append(data[Driver._PACKAGE_SIZE_START_INDEX:Driver._PACKAGE_SIZE_END_INDEX])
        if len(self._sample_numbers) > 1 and not self._check_package_difference():
            self._reset()
        ref_signal, ac_coupled, dc_coupled = Driver._encode(data)
        if self._synchronize:
            self._synchronize_with_ref(ref_signal, ac_coupled, dc_coupled)
        self._encoded_buffer.ref_signal.extend(ref_signal)
        for channel in range(Driver._CHANNELS):
            self._encoded_buffer.dc_coupled[channel].extend(dc_coupled[channel])
            self._encoded_buffer.ac_coupled[channel].extend(ac_coupled[channel])

    def _encode_bms(self, data: str) -> None:
        if int(data[BMS.SHUTDOWN_INDEX:BMS.SHUTDOWN_INDEX + 2], base=16) < BMS.SHUTDOWN:
            self.shutdown.set()
        if not int(data[BMS.VALID_IDENTIFIER_INDEX: BMS.VALID_IDENTIFIER_INDEX + 2], base=16):
            logging.error("Invalid package from BMS")
            return
        if not Driver._crc_check(data, "BMS"):
            return
        bms = BMSData(
            external_dc_power=bool(int(data[BMS.EXTERNAL_DC_POWER_INDEX:BMS.EXTERNAL_DC_POWER_INDEX + 2], base=16)),
            charging=bool(int(data[BMS.CHARGING_INDEX:BMS.CHARGING_INDEX + 2], base=16)),
            minutes_left=int(data[BMS.MINUTES_LEFT_INDEX:BMS.MINUTES_LEFT_INDEX + 4], base=16),
            battery_percentage=int(data[BMS.BATTERY_PERCENTAGE_INDEX:BMS.BATTERY_PERCENTAGE_INDEX + 2], base=16),
            battery_temperature=int(data[BMS.BATTERY_TEMPERATURE_INDEX:BMS.BATTERY_TEMPERATURE_INDEX + 4], base=16),
            battery_current=Driver._binary_to_2_complement(
                int(data[BMS.CURRENT_INDEX:BMS.CURRENT_INDEX + 4], base=16),
                byte_length=16
            ),
            battery_voltage=int(data[BMS.VOLTAGE_INDEX: BMS.VOLTAGE_INDEX + 4], base=16),
            full_charged_capacity=int(
                data[BMS.FULL_CHARGED_CAPACITY_INDEX:BMS.FULL_CHARGED_CAPACITY_INDEX + 4],
                base=16
            ),
            remaining_capacity=int(data[BMS.REMAINING_CAPACITY_INDEX:BMS.REMAINING_CAPACITY_INDEX + 4], base=16)
        )
        self._package_data.BMS.put(bms)

    @staticmethod
    def _crc_check(data: str, source) -> bool:
        crc_calculated = crc16.arc(data[:-Driver._CRC_START_INDEX].encode())
        crc_received = int(data[-Driver._CRC_START_INDEX:], base=16)
        if crc_calculated != crc_received:  # Corrupted data
            logging.error(f"CRC value of {source} isn't equal to transmitted. Got {crc_received} "
                          f"instead of {crc_calculated}.")
            return False
        return True

    def _check_package_difference(self) -> bool:
        package_difference = int(self._sample_numbers[1], base=16) - int(self._sample_numbers[0], base=16)
        if package_difference != 1:
            logging.error(f"Missing {package_difference} packages.")
            return False
        return True

    def _synchronize_with_ref(
            self, ref_signal: _Samples, ac_coupled: list[_Samples], dc_coupled: list[_Samples]
    ) -> None:
        while sum(itertools.islice(ref_signal, 0, Driver.REF_PERIOD // 2)):
            ref_signal.popleft()
            for channel in range(Driver._CHANNELS):
                ac_coupled[channel].popleft()
                dc_coupled[channel].popleft()
            dc_coupled[3].popleft()
        if len(ref_signal) < Driver.REF_PERIOD // 2:
            return
        self._synchronize = False

    def _build_sample_package(self) -> None:
        """
        Creates a package of samples that represents approximately 1 s data. It contains 8000 samples.
        """
        self._package_data.DAQ.ref_signal.put([self._encoded_buffer.ref_signal.popleft()
                                               for _ in range(Driver.NUMBER_OF_SAMPLES)])
        dc_package = [[], [], []]
        ac_package = [[], [], []]
        for _ in itertools.repeat(None, Driver.NUMBER_OF_SAMPLES):
            for channel in range(Driver._CHANNELS):
                dc_package[channel].append(self._encoded_buffer.dc_coupled[channel].popleft())
                ac_package[channel].append(self._encoded_buffer.ac_coupled[channel].popleft())
        self._package_data.DAQ.dc_coupled.put(dc_package)
        self._package_data.DAQ.ac_coupled.put(ac_package)

    def set_valve(self) -> None:
        if self.bypass:
            self.write("SBP0000")
            self.bypass = False
        else:
            self.write("SBP0001")
            self.bypass = True

    def _process_data(self) -> None:
        self._reset()
        while self.connected.is_set():
            self._encode_data()
            if len(self._encoded_buffer.ref_signal) >= Driver.NUMBER_OF_SAMPLES:
                self._build_sample_package()

    def automatic_valve_change(self) -> None:
        """
        Periodically bypass a valve. The duty cycle defines how much time for each part (bypassed or not) is spent.
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
