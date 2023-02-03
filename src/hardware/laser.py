import copy
import json
import logging
import queue
import threading
from dataclasses import dataclass
from typing import Annotated

import dacite
from statemachine import StateMachine, State

import hardware.driver


@dataclass
class DAC:
    bit_value: int
    continuous_wave: Annotated[list[bool], 3]
    pulsed_mode: Annotated[list[bool], 3]


@dataclass
class PumpLaser:
    bit_value: int
    DAC_1: DAC
    DAC_2: DAC


@dataclass
class ProbeLaser:
    current_bits: int
    constant_current: bool
    constant_light: bool
    photo_diode_gain: int


@dataclass
class Data:
    pump_laser_current = 0
    pump_laser_voltage = 0
    probe_laser_current = 0


class DriverStateMachine(StateMachine):
    disconnected = State("Disconnected", initial=True)
    connected = State("Connected")
    disabled = State("Disabled")
    initialized = State("Init")
    enabled = State("Enabled")

    connect = disconnected.to(connected)
    initialize = connected.to(initialized)
    enable = initialized.to(enabled) | disabled.to(enabled)
    disable = enabled.to(disabled)


class Driver(hardware.driver.Serial):
    HARDWARE_ID = b"0002"
    NAME = "Laser"
    DELIMITER = "\t"
    DATA_START = "L"
    START_MEASURED_DATA = 1
    END_MEASURED_DATA = 4

    # Pump Laser
    RESISTOR = 2.2e4
    DIGITAL_POT = 1e4
    NUMBER_OF_STEPS = 1 << 7
    PRE_RESISTOR = 1.6e3
    ContinuesWaveRegister = [1 << 8, 1 << 10, 1 << 12, 1 << 14, 1 << 0, 1 << 2]
    ModulatedModeRegister = [1 << 9, 1 << 11, 1 << 13, 1 << 15, 1 << 1, 1 << 3]

    # Probe Laser
    CURRENT_BITS = (1 << 8) - 1

    def __init__(self):
        hardware.driver.Serial.__init__(self)
        self.pump_laser = None  # type: None | PumpLaser
        self.probe_laser = None  # type: None | ProbeLaser
        self.config_path = "hardware/configs/laser.json"
        self.laser_data = queue.Queue(maxsize=Driver.QUEUE_SIZE)
        self.laser_machine = DriverStateMachine()
        self.laser_machine.connect()
        self.load_configs()

    def load_configs(self):
        with open(self.config_path) as config:
            loaded_config = json.load(config)
            self.pump_laser = dacite.from_dict(PumpLaser, loaded_config["pump_laser"])
            self.probe_laser = dacite.from_dict(ProbeLaser, loaded_config["probe_laser"])

    def open(self):
        super().open()
        self.laser_machine.connect()

    @property
    def device_id(self):
        return Driver.HARDWARE_ID

    @property
    def device_name(self):
        return Driver.NAME

    @staticmethod
    def bit_to_voltage(bits):
        # Values and formula is given by hardware
        return 0.8 * Driver.RESISTOR / (bits * Driver.DIGITAL_POT / Driver.NUMBER_OF_STEPS + Driver.PRE_RESISTOR) + 0.8

    @staticmethod
    def bit_to_current(bits):
        # Values and formula is given by hardware
        return (bits - 260.4) / (-5.335)

    def set_static_current(self, current):
        self.write(b"SC3" + bytes(current))

    def set_modulated_current(self, current):
        self.write(b"SC4" + bytes(current))

    def set_driver_voltage(self):
        voltage_hex = f"{self.pump_laser.bit_value:0{hardware.driver.Serial.NUMBER_OF_HEX_BYTES}x}".encode()
        self.write(b"SHV" + voltage_hex)

    def set_dac_1(self):
        dac_1_hex = f"{self.pump_laser.DAC_1.bit_value:0{hardware.driver.Serial.NUMBER_OF_HEX_BYTES}x}".encode()
        self.write(b"SC3" + dac_1_hex)

    def set_dac_2(self):
        dac_2_hex = f"{self.pump_laser.DAC_2.bit_value:0{hardware.driver.Serial.NUMBER_OF_HEX_BYTES}x}".encode()
        self.write(b"SC4" + dac_2_hex)

    def set_dac_matrix(self):
        matrix = 0
        for i in range(len(self.pump_laser.DAC_1.continuous_wave)):
            if self.pump_laser.DAC_1.continuous_wave[i]:
                matrix |= Driver.ContinuesWaveRegister[i]
            elif self.pump_laser.DAC_1.pulsed_mode[i]:
                matrix |= Driver.ModulatedModeRegister[i]
            if self.pump_laser.DAC_2.continuous_wave[i]:
                matrix |= Driver.ContinuesWaveRegister[i]
            elif self.pump_laser.DAC_2.pulsed_mode[i]:
                matrix |= Driver.ModulatedModeRegister[i]
        matrix_hex = f"{matrix:0{hardware.driver.Serial.NUMBER_OF_HEX_BYTES}x}".encode()
        self.write(b"SC1" + matrix_hex)

    def enable_channels(self):
        self.write(b"SHE0001")

    def disable_channels(self):
        self.write(b"SHE0000")

    def set_probe_laser_current(self):
        power_current = f"{self.probe_laser.current_bits:0{hardware.driver.Serial.NUMBER_OF_HEX_BYTES}x}".encode()
        self.write(b"SLS" + power_current)

    def set_probe_laser_mode(self):
        if self.probe_laser.constant_light:
            self.write(b"SLM0001")
        else:
            self.write(b"SLM0002")

    def init_laser(self):
        self.write(b"CHI0000")
        self.write(b"CLI0000")
        self.laser_machine.initialize()

    def enable_lasers(self):
        self.write(b"SHE0001")
        self.write(b"SLE0001")
        self.laser_machine.enable()

    def disable_laser(self):
        self.write(b"SHE0000")
        self.write(b"SLE0000")
        self.laser_machine.disable()

    def set_photo_gain(self):
        phot_gain_hex = f"{self.probe_laser.photo_diode_gain:0{hardware.driver.Serial.NUMBER_OF_HEX_BYTES}x}".encode()
        self.write(b"SLS" + phot_gain_hex)

    def _encode_data(self, received_data):
        for received in received_data.split(Driver.TERMINATION_SYMBOL):
            if not received:
                continue
            encoded_data = received.decode()
            match encoded_data[0]:
                case "N":
                    logging.error(f"Invalid command {encoded_data}")
                case "S" | "C":
                    logging.info(f"Command {encoded_data} successfully applied")
                case "L":
                    measured_data = encoded_data.split(Driver.DELIMITER)[Driver.START_MEASURED_DATA:
                                                                         Driver.END_MEASURED_DATA]
                    laser_data = Data()
                    laser_data.pump_laser_voltage = float(measured_data[0])
                    laser_data.pump_laser_current = float(measured_data[1])
                    laser_data.probe_laser_current = float(measured_data[2])
                    self.laser_data.put(copy.deepcopy(laser_data))
                case _:  # Broken data frame without header char
                    continue

    def apply_configuration(self):
        # Probe Driver
        self.set_probe_laser_current()
        self.set_probe_laser_mode()
        # Pump Driver
        self.set_driver_voltage()
        self.set_dac_1()
        self.set_dac_2()
        self.set_dac_matrix()
        self.enable_lasers()
