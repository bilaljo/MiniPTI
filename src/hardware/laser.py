import copy
import json
import logging
from dataclasses import dataclass
from typing import Annotated
import dacite

import hardware.serial


@dataclass
class _DAC:
    bit_value: int
    continuous_wave: Annotated[list[bool], 3]
    pulsed_mode: Annotated[list[bool], 3]


@dataclass
class PumpLaser:
    _RESISTOR = 2.2e4
    _DIGITAL_POT = 1e4
    NUMBER_OF_STEPS = 1 << 7
    _PRE_RESISTOR = 1.6e3

    max_current_mA: float
    bit_value: int
    DAC_1: _DAC
    DAC_2: _DAC

    @staticmethod
    def bit_to_voltage(bits):
        # 0.8 is an interpolation constant without any practical meaning.
        return 0.8 * PumpLaser._RESISTOR / (bits * PumpLaser._DIGITAL_POT / PumpLaser.NUMBER_OF_STEPS
                                            + PumpLaser._PRE_RESISTOR) + 0.8


@dataclass
class ProbeLaser:
    max_current_mA: float
    current_bits: int
    constant_current: bool
    constant_light: bool
    photo_diode_gain: int

    @staticmethod
    def bit_to_current(bits):
        # Values and formula is given by hardware
        return (bits - 260.4) / (-5.335)

    @staticmethod
    def current_to_bit(bits):
        return int(-5.335 * bits + 260.4)


@dataclass
class LaserData(hardware.serial.Data):
    pump_laser_current: float
    pump_laser_voltage: float
    probe_laser_current: float


class Driver(hardware.serial.Driver):
    HARDWARE_ID = "0002"
    NAME = "Laser"
    DELIMITER = "\t"
    DATA_START = "L"
    _START_MEASURED_DATA = 1
    _END_MEASURED_DATA = 4

    CHANNELS = 3

    # Pump Laser
    _DAC_1_REGISTER = [1 << 8, 1 << 9, 1 << 10, 1 << 11, 1 << 12, 1 << 13]
    _DAC_2_REGISTER = [1 << 14, 1 << 15, 1 << 0, 1 << 1, 1 << 2, 1 << 3]

    CURRENT_BITS = (1 << 8) - 1

    def __init__(self):
        hardware.serial.Driver.__init__(self)
        self.pump_laser = None  # type: None | PumpLaser
        self.probe_laser = None  # type: None | ProbeLaser
        self.config_path = "hardware/configs/laser.json"
        self.probe_laser_initialized = False
        self.pump_laser_initialized = False
        self.load_configs()

    def open(self) -> bool:
        if super().open():
            self.init_pump_laser()
            self.init_probe_laser()
            # If laser was configured as enabled we disable it for safety
            self.disable_pump_laser()
            self.disable_probe_laser()
            return True
        return False

    def load_configs(self) -> None:
        with open(self.config_path) as config:
            loaded_config = json.load(config)
            self.pump_laser = dacite.from_dict(PumpLaser, loaded_config["Pump Laser"])
            self.probe_laser = dacite.from_dict(ProbeLaser, loaded_config["Probe Laser"])

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
                        logging.error(f"Received message {received} message, expected {last_written}")
                    else:
                        logging.debug(f"Command {received} successfully applied")
                    self.ready_write.set()
                case "L":
                    data_frame = received.split("\t")[Driver._START_DATA_FRAME:self.end_data_frame]
                    extracted_data = LaserData(pump_laser_current=float(data_frame[0]),
                                               pump_laser_voltage=float(data_frame[1]),
                                               probe_laser_current=float(data_frame[2]))
                    self.data.put(copy.deepcopy(extracted_data))
                case _:  # Broken data frame without header char
                    logging.error("Received invalid package without header")
                    self.ready_write.set()
                    continue

    def _process_data(self) -> None:
        while self.connected.is_set():
            self._encode_data()

    @property
    def device_id(self) -> str:
        return Driver.HARDWARE_ID

    @property
    def device_name(self) -> str:
        return Driver.NAME

    @property
    def end_data_frame(self) -> int:
        return 4

    def set_driver_voltage(self) -> None:
        voltage_hex = f"{self.pump_laser.bit_value:0{hardware.serial.Driver._NUMBER_OF_HEX_BYTES}X}"
        self.write("SHV" + voltage_hex)

    def set_dac_1(self) -> None:
        dac_1_hex = f"{self.pump_laser.DAC_1.bit_value:0{hardware.serial.Driver._NUMBER_OF_HEX_BYTES}X}"
        self.write("SC3" + dac_1_hex)

    def set_dac_2(self) -> None:
        dac_2_hex = f"{self.pump_laser.DAC_2.bit_value:0{hardware.serial.Driver._NUMBER_OF_HEX_BYTES}X}"
        self.write("SC4" + dac_2_hex)

    def set_dac_matrix(self) -> None:
        matrix = 0
        for i in range(Driver.CHANNELS):
            if self.pump_laser.DAC_1.continuous_wave[i]:
                matrix |= Driver._DAC_1_REGISTER[2 * i]
            elif self.pump_laser.DAC_1.pulsed_mode[i]:
                matrix |= Driver._DAC_1_REGISTER[2 * i + 1]
            if self.pump_laser.DAC_2.continuous_wave[i]:
                matrix |= Driver._DAC_2_REGISTER[2 * i]
            elif self.pump_laser.DAC_2.pulsed_mode[i]:
                matrix |= Driver._DAC_2_REGISTER[2 * i + 1]
        matrix_hex = f"{matrix:0{hardware.serial.Driver._NUMBER_OF_HEX_BYTES}X}"
        self.write("SC1" + matrix_hex)

    def enable_channels(self) -> None:
        self.write("SHE0001")

    def set_probe_laser_current(self) -> None:
        current_mA = ProbeLaser.bit_to_current(self.probe_laser.current_bits)
        if current_mA > self.probe_laser.max_current_mA:
            logging.error(f"Current exceeds maximum current of {self.probe_laser.max_current_mA} mA")
            logging.info(f"Setting it to maximum value of {self.probe_laser.max_current_mA} mA")
            current = ProbeLaser.current_to_bit(self.probe_laser.max_current_mA)
        else:
            current = self.probe_laser.current_bits
        current_hex = f"{current:0{hardware.serial.Driver._NUMBER_OF_HEX_BYTES}X}"
        self.write("SLS" + current_hex)

    def set_probe_laser_mode(self) -> None:
        # WARNING: The firmware of the laser driver has a bug. This command does nothing
        if self.probe_laser.constant_light:
            self.write("SLM0002")
        else:
            self.write("SLM0001")

    def init_pump_laser(self) -> None:
        self.write("CHI0001")
        self.pump_laser_initialized = True

    def init_probe_laser(self) -> None:
        self.write("CLI0001")
        self.probe_laser_initialized = True

    def enable_pump_laser(self) -> None:
        if self.pump_laser_initialized:
            self.write("SHE0001")
        else:
            self.init_pump_laser()
            self.pump_laser_initialized = True
            self.write("SHE0001")

    def enable_probe_laser(self):
        if self.probe_laser_initialized:
            self.write("SLE0001")
        else:
            self.init_probe_laser()
            self.probe_laser_initialized = True
            self.write("SLE0001")

    def disable_pump_laser(self) -> None:
        self.write("SHE0000")

    def disable_probe_laser(self) -> None:
        self.write("SLE0000")

    def set_photo_gain(self) -> None:
        phot_gain_hex = f"{self.probe_laser.photo_diode_gain:0{hardware.serial.Driver._NUMBER_OF_HEX_BYTES}X}"
        self.write("SLS" + phot_gain_hex)

    def apply_configuration(self) -> None:
        # Probe Driver
        self.set_probe_laser_current()
        self.set_probe_laser_mode()
        # Pump Driver
        self.set_driver_voltage()
        self.set_dac_1()
        self.set_dac_2()
        self.set_dac_matrix()
        self.enable_channels()
