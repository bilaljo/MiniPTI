import dataclasses
import enum
import itertools
import json
import logging
import queue
import threading
import time
from collections import deque
from dataclasses import dataclass
from typing import Final, Union, Any, Callable

import dacite
import numpy as np
from fastcrc import crc16
from overrides import override

import minipti
from . import protocolls
from . import serial_device, _json_parser


class MotherBoardTools:
    _QUEUE_SIZE = 50

    def __init__(self, tool: str, driver: "Driver", config_type: Any):
        self.tool = tool
        self.driver = driver
        self.config_path = f"{minipti.module_path}/hardware/configs/motherboard/{tool.casefold()}.json"
        self.configuration: Union[config_type, None] = None
        self._config_type = config_type

    def load_configuration(self) -> None:
        with open(self.config_path) as config:
            loaded_config = json.load(config)
            self.configuration = dacite.from_dict(self._config_type, loaded_config[self.tool])

    def save_configuration(self) -> None:
        with open(self.config_path, "w") as configuration:
            valve = {self.tool: dataclasses.asdict(self.configuration)}
            configuration.write(_json_parser.to_json(valve) + "\n")
            logging.info("Saved %s configuration in %s", self.tool.casefold(), self.config_path)


@dataclass
class ValveConfiguration:
    automatic_switch: bool
    period: int
    duty_cycle: int


class Valve(MotherBoardTools):
    def __init__(self, driver: "Driver"):
        MotherBoardTools.__init__(self, "Valve", driver, ValveConfiguration)
        self._bypass = protocolls.ASCIIHex("SBP0000")
        self._automatic_switch = threading.Event()
        self.configuration: Union[ValveConfiguration, None] = None
        self.observers: list[Callable[[bool], None]] = []
        self.load_configuration()

    def automatic_valve_change(self) -> None:
        """
        Periodically bypass a valve. The duty cycle defines how much time for each part (bypassed
        or not) is spent.
        """
        def switch() -> None:
            while self.driver.connected.is_set():
                self._automatic_switch.wait()
                self.bypass = not self.bypass
                if self.bypass:
                    time.sleep(self.configuration.period * self.configuration.duty_cycle / 100)
                else:
                    time.sleep(self.configuration.period * (1 - self.configuration.duty_cycle / 100))

        threading.Thread(target=switch, daemon=True).start()

    @property
    def automatic_switch(self):
        return self._automatic_switch.is_set()

    @automatic_switch.setter
    def automatic_switch(self, automatic_switch: bool) -> None:
        self.configuration.automatic_switch = automatic_switch
        if automatic_switch:
            self._automatic_switch.set()
        else:
            self._automatic_switch.clear()

    @override
    def load_configuration(self) -> None:
        super().load_configuration()
        if self.configuration.automatic_switch:
            self._automatic_switch.set()
        self.bypass = False

    @property
    def bypass(self) -> bool:
        return bool(self._bypass.value)

    @bypass.setter
    def bypass(self, new_value) -> None:
        self._bypass.value = new_value
        self.driver.write(self._bypass)
        for observer in self.observers:
            observer(self.bypass)


class BMSIndex(enum.IntEnum):
    SHUTDOWN = 0
    VALID_IDENTIFIER = 2
    EXTERNAL_DC_POWER = 4
    CHARGING = 6
    MINUTES_LEFT = 8
    BATTERY_PERCENTAGE = 12
    BATTERY_TEMPERATURE = 14
    CURRENT = 18
    VOLTAGE = 22
    FULL_CHARGED_CAPACITY = 26
    REMAINING_CAPACITY = 30


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


class BMS(MotherBoardTools):
    PACKAGE_SIZE: Final = 38
    SHUTDOWN = 0xFF

    def __init__(self, driver: "Driver"):
        MotherBoardTools.__init__(self, "BMS", driver, BMSConfiguration)
        self._do_shutdown = protocolls.ASCIIHex("SHD0001")
        self.running = threading.Event()
        self.encoded_data: Union[tuple[bool, BMSData], None] = None
        self._data = queue.Queue(maxsize=MotherBoardTools._QUEUE_SIZE)
        self.configuration: Union[BMSConfiguration, None] = None
        self.load_configuration()

    @property
    def data(self) -> tuple[bool, BMSData]:
        return self._data.get(block=True)

    def encode(self, data: str) -> None:
        shutdown = int(data[BMSIndex.SHUTDOWN:BMSIndex.SHUTDOWN + 2], base=16) < BMS.SHUTDOWN
        """
        The BMS data is encoded according to the following scheme:
        Every byte is an ASCII symbol. The bytes have the following meanings:
        1 - 2:
        Represent the package identifier
        3 - 4:
        - The next two bytes are the countdown of a shutdown. Attention: if this value is below 255 (0xFF),
        the motherboard will shut down itself soon.
        - The next 
        """
        if not int(data[BMSIndex.VALID_IDENTIFIER:BMSIndex.VALID_IDENTIFIER + 2], base=16):
            logging.error("Invalid package from BMS")
            return
        self.encoded_data = BMSData(
            external_dc_power=bool(int(data[BMSIndex.EXTERNAL_DC_POWER:BMSIndex.EXTERNAL_DC_POWER + 2], base=16)),
            charging=bool(int(data[BMSIndex.CHARGING:BMSIndex.CHARGING + 2], base=16)),
            minutes_left=int(data[BMSIndex.MINUTES_LEFT:BMSIndex.MINUTES_LEFT + 4], base=16),
            battery_percentage=int(data[BMSIndex.BATTERY_PERCENTAGE:BMSIndex.BATTERY_PERCENTAGE + 2], base=16),
            battery_temperature=int(data[BMSIndex.BATTERY_TEMPERATURE:BMSIndex.BATTERY_TEMPERATURE + 4], base=16),
            battery_current=Driver.binary_to_2_complement(int(data[BMSIndex.CURRENT:BMSIndex.CURRENT + 4], base=16)),
            battery_voltage=int(data[BMSIndex.VOLTAGE: BMSIndex.VOLTAGE + 4], base=16),
            full_charged_capacity=int(data[BMSIndex.FULL_CHARGED_CAPACITY:BMSIndex.FULL_CHARGED_CAPACITY + 4], base=16),
            remaining_capacity=int(data[BMSIndex.REMAINING_CAPACITY:BMSIndex.REMAINING_CAPACITY + 4], base=16))
        if self.encoded_data.charging:
            self.encoded_data.minutes_left = float("inf")
        self._data.put((shutdown, self.encoded_data))

    @property
    def empty(self) -> bool:
        return self._data.empty()

    def do_shutdown(self) -> None:
        self.driver.write(self._do_shutdown)

    def load_configuration(self) -> None:
        super().load_configuration()
        if self.configuration.use_battery:
            self.running.set()
        else:
            self.running.clear()


@dataclass
class PumpConfiguration:
    duty_cycle: int


class Pump(MotherBoardTools):
    MAX_DUTY_CYCLE: Final = 0xFFFF

    def __init__(self, driver: "Driver"):
        MotherBoardTools.__init__(self, "Pump", driver, PumpConfiguration)
        self._duty_cycle_command = protocolls.ASCIIHex("SDP0000")
        self.configuration: Union[PumpConfiguration, None] = None
        self.load_configuration()

    def set_duty_cycle(self) -> None:
        self._duty_cycle_command.value = self.configuration.duty_cycle
        self.driver.write(self._duty_cycle_command)

    def disable_pump(self) -> None:
        self._duty_cycle_command.value = 0
        self.driver.write(self._duty_cycle_command)


@dataclass
class DAQConfiguration:
    number_of_samples: int
    ref_period: int


@dataclass
class DAQData:
    ref_signal: Union[list, deque]
    ac_coupled: Union[list, list[deque]]
    dc_coupled: Union[list, list[deque]]


class DAQ(MotherBoardTools):
    PACKAGE_SIZE: Final = 4104
    _SEQUENCE_SIZE: Final = 8
    RAW_DATA_SIZE: Final = PACKAGE_SIZE - _SEQUENCE_SIZE
    _WORD_SIZE: Final = 32
    ENCODED_DATA_SIZE = RAW_DATA_SIZE // _WORD_SIZE
    _AC_CHANNELS: Final = 3
    _DC_CHANNELS: Final = 4

    def __init__(self, driver: "Driver"):
        MotherBoardTools.__init__(self, "DAQ", driver, DAQConfiguration)
        self._sample_numbers = deque(maxlen=2)
        self.synchronize = False
        self.encoded_buffer = DAQData(deque(maxlen=DAQ.ENCODED_DATA_SIZE),
                                      [deque(maxlen=DAQ.ENCODED_DATA_SIZE) for _ in range(3)],
                                      [deque(maxlen=DAQ.ENCODED_DATA_SIZE) for _ in range(4)])
        self.samples_buffer = DAQData([], [[], [], []], [[], [], [], []])
        self.running = threading.Event()
        self.data = [queue.Queue(maxsize=DAQ._QUEUE_SIZE) for _ in range(3)]
        self.configuration: Union[DAQConfiguration, None] = None
        self.load_configuration()

    @property
    def ref_signal(self) -> deque:
        return self.data[PackageIndex.REF].get(block=True)

    @property
    def dc_coupled(self) -> deque:
        return self.data[PackageIndex.DC].get(block=True)

    @property
    def ac_coupled(self) -> deque:
        return self.data[PackageIndex.AC].get(block=True)

    @property
    def samples_buffer_size(self) -> int:
        return len(self.samples_buffer.ref_signal)

    @property
    def number_of_samples(self) -> int:
        return self.configuration.number_of_samples

    @number_of_samples.setter
    def number_of_samples(self, number_of_samples: int) -> None:
        self.configuration.number_of_samples = number_of_samples
        self.update_buffer_size()

    def update_buffer_size(self) -> None:
        was_running = self.running.is_set()
        if self.running.is_set():
            logging.warning("Encoding is running. Need to pause is to update the buffer size and reset samples")
            self.running.clear()
        self.samples_buffer = DAQData([], [[], [], []], [[], [], [], []])
        self.reset()
        if was_running:
            self.running.set()

    def build_sample_package(self) -> None:
        """
        Creates a package of samples that represents approximately 1 s data. It contains 8000
        samples.
        """
        if self.samples_buffer.ref_signal[0]:
            logging.warning("Not synchron with reference signal")
            self.reset()
            return
        ref = []
        dc_package = [[], [], []]
        ac_package = [[], [], []]
        for _ in itertools.repeat(None, self.number_of_samples):
            ref.append(self.samples_buffer.ref_signal.pop(0))
            for channel in range(3):
                dc_package[channel].append(self.samples_buffer.dc_coupled[channel].pop(0))
                ac_package[channel].append(self.samples_buffer.ac_coupled[channel].pop(0))
        self.data[PackageIndex.REF].put(np.array(ref), block=False)
        self.data[PackageIndex.DC].put(np.array(dc_package), block=False)
        self.data[PackageIndex.AC].put(np.array(ac_package), block=False)

    def _encode_binary(self, raw_data: str) -> None:
        """
        A block of data has the following structure:
        Ref, DC 1, DC 2, DC 3, DC, 4 AC 1, AC 2, AC 3, AC 4
        These byte words are 4 bytes wide and hex decimal decoded. These big byte word of size 32
        repeats periodically. It starts with below the first 10 bytes (meta information) and ends
        before the last 4 bytes (crc checksum).
        """
        for i in range(0, len(raw_data), DAQ._WORD_SIZE):
            self.encoded_buffer.ref_signal.append(int(raw_data[i:i + 4], base=16))
            # AC signed
            ac_value = Driver.binary_to_2_complement(int(raw_data[i + 4:i + 8], base=16), 16)
            self.encoded_buffer.ac_coupled[0].append(ac_value)
            ac_value = Driver.binary_to_2_complement(int(raw_data[i + 8:i + 12], base=16), 16)
            self.encoded_buffer.ac_coupled[1].append(ac_value)
            ac_value = Driver.binary_to_2_complement(int(raw_data[i + 12:i + 16], base=16), 16)
            self.encoded_buffer.ac_coupled[2].append(ac_value)
            # DC unsigned
            self.encoded_buffer.dc_coupled[0].append(int(raw_data[i + 16:i + 20], base=16))
            self.encoded_buffer.dc_coupled[1].append(int(raw_data[i + 20:i + 24], base=16))
            self.encoded_buffer.dc_coupled[2].append(int(raw_data[i + 24:i + 28], base=16))
            self.encoded_buffer.dc_coupled[3].append(int(raw_data[i + 28:i + 32], base=16))

    def encode(self, data: str) -> None:
        """
        The data is encoded according to the following protocol:
            - The first two bytes describes the send command
            - Byte 2 up to 10 describe the package number of the send package
            - Byte 10 to 32 contain the data as period sequence of blocks in hex decimal
            - The last 4 bytes represent a CRC checksum in hex decimal
        """
        self._sample_numbers.append(data[:DAQ._SEQUENCE_SIZE])
        if len(self._sample_numbers) > 1 and not self._check_package_difference():
            self.reset()
            self.synchronize = True
        self._encode_binary(data[DAQ._SEQUENCE_SIZE:])
        if self.synchronize:
            self.synchronize_with_ref()
        self.samples_buffer.ref_signal.extend(self.encoded_buffer.ref_signal)
        for i in range(3):
            self.samples_buffer.dc_coupled[i].extend(self.encoded_buffer.dc_coupled[i])
            self.samples_buffer.ac_coupled[i].extend(self.encoded_buffer.ac_coupled[i])
        self.samples_buffer.dc_coupled[3].extend(self.encoded_buffer.dc_coupled[3])
        if len(self.samples_buffer.ref_signal) >= self.number_of_samples:
            self.build_sample_package()

    def synchronize_with_ref(self) -> None:
        logging.warning("Trying to synchronise")
        while sum(itertools.islice(self.encoded_buffer.ref_signal, 0, self.configuration.ref_period // 2)):
            self.encoded_buffer.ref_signal.popleft()
            for channel in range(3):
                self.encoded_buffer.ac_coupled[channel].popleft()
                self.encoded_buffer.dc_coupled[channel].popleft()
            self.encoded_buffer.dc_coupled[3].popleft()
        if len(self.encoded_buffer.ref_signal) < self.configuration.ref_period // 2:
            return
        self.synchronize = False

    def reset(self) -> None:
        self._sample_numbers = deque(maxlen=2)
        self.synchronize = True
        self.encoded_buffer = DAQData(deque(maxlen=DAQ.ENCODED_DATA_SIZE),
                                      [deque(maxlen=DAQ.ENCODED_DATA_SIZE) for _ in range(3)],
                                      [deque(maxlen=DAQ.ENCODED_DATA_SIZE) for _ in range(4)])
        self.samples_buffer = DAQData([], [[], [], []], [[], [], [], []])

    def _check_package_difference(self) -> bool:
        package_difference = int(self._sample_numbers[1], base=16) - int(self._sample_numbers[0], base=16)
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
            config = {"DAQ": dataclasses.asdict(self.configuration)}
            configuration.write(_json_parser.to_json(config) + "\n")
            logging.info("Saved DAQ configuration in %s", self.config_path)


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
    CRC_SIZE: Final = 4

    HARDWARE_ID: Final = b"0001"
    NAME: Final = "Motherboard"

    _CHANNELS: Final = 3

    def __init__(self):
        serial_device.Driver.__init__(self)
        self.daq = DAQ(self)
        self.bms = BMS(self)
        self.valve = Valve(self)
        self.pump = Pump(self)
        self.new_run = True

    @property
    def device_id(self) -> bytes:
        return Driver.HARDWARE_ID

    @property
    def device_name(self) -> str:
        return Driver.NAME

    @property
    def buffer_size(self) -> int:
        return len(self._package_buffer)
    
    @override
    def clear(self) -> None:
        self.pump.disable_pump()
        self.valve.bypass = False
        super().clear()

    def clear_buffer(self) -> None:
        self._package_buffer = ""
        self.daq.data = [queue.Queue(maxsize=Driver._QUEUE_SIZE) for _ in range(3)]

    @staticmethod
    def binary_to_2_complement(number: int, byte_length: int = 16) -> int:
        if number & (1 << (byte_length - 1)):
            return number - (1 << byte_length)
        return number

    def reset(self) -> None:
        self.clear_buffer()

    @override
    def _encode(self, data: str) -> None:
        if self.daq.running.is_set() and data[0] == "D" and len(data) == DAQ.PACKAGE_SIZE + Driver.CRC_SIZE + 1:
            if not self._crc_check(data, "DAQ"):
                return
            self.daq.encode(data[1:-Driver._CRC_START])
        elif self.bms.running.is_set() and data[0] == "B" and len(data) == BMS.PACKAGE_SIZE + 1:
            if not self._crc_check(data, "BMS"):
                return
            self.bms.encode(data[1:-Driver.CRC_SIZE])
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

    def _process_data(self) -> None:
        self.daq.reset()
        self._package_buffer = ""
        while self.connected.is_set():
            if self.new_run:
                self.reset()
                self.new_run = False
            self.encode_data()
        self.new_run = True
