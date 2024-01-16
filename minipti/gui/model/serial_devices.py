import enum
import logging
import os
import platform
import subprocess
import threading
import time
import typing
from abc import abstractmethod, ABC
from collections import deque
from dataclasses import asdict, dataclass
from datetime import datetime

import pandas as pd
from notifypy import Notify
from overrides import override

import minipti
from minipti import hardware
from minipti.gui.model import buffer, configuration
from minipti.gui.model import signals

LaserData = hardware.laser.Data

TecData = hardware.tec.Data


class Serial(ABC):
    """
    This class is a base class for subclasses of the driver objects from driver/serial.
    """

    def __init__(self, driver: hardware.serial_device.Driver):
        self.driver = driver
        self._destination_folder = os.getcwd()
        self._init_headers = True
        self._running = False
        signals.GENERAL_PURPORSE.destination_folder_changed.connect(self._update_destination_folder)

    def _update_destination_folder(self, destination_folder: str) -> None:
        self._destination_folder = destination_folder
        self._init_headers = True

    def find_port(self) -> None:
        self.driver.find_port()

    def open(self) -> None:
        """
        Connects to a serial device and listens to incoming data.
        """
        self.driver.open()

    def run(self) -> None:
        self.driver.run()

    def close(self) -> None:
        """
        Disconnects to a serial device and stops listening to data
        """
        self.driver.close()

    def save_configuration(self) -> None:
        ...

    def fire_configuration_change(self) -> None:
        """
        By initiation of a Serial Object (on which the laser model relies) the configuration is
        already set and do not fire events to update the GUI. This function is hence only called
        once to manually activate the firing.
        """

    def load_configuration(self) -> None:
        self.fire_configuration_change()

    def _incoming_data(self) -> None:
        """
        Listens to incoming data and emits them as _signals to the view as long a serial connection
        is established.
        """

    def process_measured_data(self) -> threading.Thread:
        processing_thread = threading.Thread(target=self._incoming_data, name="Incoming Data", daemon=True)
        processing_thread.start()
        return processing_thread


class DAQ(Serial):
    def __init__(self, driver: hardware.motherboard.Driver):
        Serial.__init__(self, driver)
        self.driver = driver

    @property
    def ref_signal(self) -> deque:
        return self.driver.daq.ref_signal

    @property
    def dc_coupled(self) -> deque:
        return self.driver.daq.dc_coupled

    @property
    def ac_coupled(self) -> deque:
        return self.driver.daq.ac_coupled

    def save_configuration(self) -> None:
        self.driver.daq.save_configuration()

    def load_configuration(self) -> None:
        self.driver.daq.load_configuration()
        self.fire_configuration_change()

    @property
    def running(self) -> bool:
        return self.driver.daq.running.is_set()

    @running.setter
    def running(self, running: bool):
        if running:
            # Before we start a new run, we clear all old data
            self.driver.reset()
            signals.DAQ.clear.emit()
            self.driver.daq.running.set()
            signals.DAQ.running.emit(True)
        else:
            self.driver.daq.running.clear()
            signals.DAQ.running.emit(False)

    def fire_configuration_change(self) -> None:
        signals.DAQ.samples_changed.emit(self.driver.daq.configuration.number_of_samples)

    @property
    def number_of_samples(self) -> int:
        return self.driver.daq.number_of_samples
    
    @number_of_samples.setter
    def number_of_samples(self, number_of_sampes: int) -> None:
        self.driver.daq.number_of_samples = number_of_sampes
        self.fire_configuration_change()


class BMS(Serial):
    MINIUM_PERCENTAGE = 15
    CRITICAL_PERCENTAGE = 5
    DATA = hardware.motherboard.BMSData

    def __init__(self, driver: hardware.motherboard.Driver):
        Serial.__init__(self, driver)
        self._destination_folder = "."
        self.driver = driver
        self.driver.bms.configuration.use_battery = configuration.GUI.battery.use

    def shutdown_procedure(self) -> None:
        self.shutdown()
        time.sleep(0.5)  # Give the calculations threads time to finish their write operation
        if platform.system() == "Windows":
            subprocess.run(r"shutdown /s /t 1", shell=True)
        else:
            subprocess.run("sleep 0.5s && poweroff", shell=True)
        exit(0)

    def shutdown(self) -> None:
        self.driver.bms.do_shutdown()

    @staticmethod
    def centi_kelvin_to_celsius(temperature: float) -> float:
        return round((temperature - 273.15) / 100, 2)

    @override
    def _incoming_data(self) -> None:
        init_headers = True
        now = datetime.now()
        date = str(now.strftime("%Y-%m-%d"))
        while self.driver.connected.is_set():
            shutdown, bms_data = self.driver.bms.data  # type: bool, hardware.motherboard.BMSData
            if shutdown:
                logging.critical("BMS has started a shutdown")
                logging.critical("The system will make an emergency shutdown now")
                self.shutdown_procedure()
                return
            elif BMS.CRITICAL_PERCENTAGE < bms_data.battery_percentage < BMS.MINIUM_PERCENTAGE:
                logging.warning(f"Battery below {BMS.MINIUM_PERCENTAGE}.")
                logging.warning("An automatic shutdown will occur soon")
            elif bms_data.battery_percentage < BMS.CRITICAL_PERCENTAGE:
                logging.critical("Battery too low")
                logging.warning("The system will make an emergency shutdown now")
                self.shutdown_procedure()
                return
            bms_data.battery_temperature = BMS.centi_kelvin_to_celsius(bms_data.battery_temperature)
            signals.BMS.battery_data.emit(bms_data.battery_current, bms_data.battery_voltage,
                                          bms_data.battery_temperature, bms_data.minutes_left,
                                          bms_data.battery_percentage, bms_data.remaining_capacity)
            signals.BMS.battery_state.emit(bms_data.charging, bms_data.battery_percentage)
            if self.driver.sampling and configuration.GUI.save.bms:
                if init_headers:
                    units = {"Time": "H:M:S", "External DC Power": "bool",
                             "Charging Battery": "bool", "Minutes Left": "min", "Charging Level": "%",
                             "Temperature": "°C", "Current": "mA",
                             "Voltage": "mV", "Full Charge Capacity": "mAh", "Remaining Charge Capacity": "mAh"}
                    pd.DataFrame(units, index=["Y:M:D"]).to_csv(self._destination_folder + f"/{date}_BMS.csv",
                                                                index_label="Date")
                    init_headers = False
                now = datetime.now()
                output_data = {"Time": str(now.strftime("%H:%M:%S"))}
                for key, value in asdict(bms_data).items():
                    output_data[key.replace("_", " ").title()] = value
                bms_data_frame = pd.DataFrame(output_data, index=[str(now.strftime("%Y-%m-%d"))])
                bms_data_frame.to_csv(self._destination_folder + f"/{date}_BMS.csv", header=False, mode="a")


class Valve(Serial):
    def __init__(self, driver: hardware.motherboard.Driver):
        Serial.__init__(self, driver)
        self.driver = driver
        self.driver.valve.observers.append(lambda x: signals.VALVE.bypass.emit(x))

    @property
    def period(self) -> int:
        return self.driver.valve.configuration.period

    @period.setter
    def period(self, period: int) -> None:
        if period < 0:
            raise ValueError("Invalid value for period")
        self.driver.valve.configuration.period = period

    @property
    def duty_cycle(self) -> int:
        return self.driver.valve.configuration.duty_cycle

    @duty_cycle.setter
    def duty_cycle(self, duty_cycle: int) -> None:
        if not 0 < self.driver.valve.configuration.duty_cycle < 100:
            raise ValueError("Invalid value for duty cycle")
        self.driver.valve.configuration.duty_cycle = duty_cycle

    @property
    def automatic_switch(self) -> bool:
        return self.driver.valve.automatic_switch

    @automatic_switch.setter
    def automatic_switch(self, automatic_switch: bool) -> None:
        self.driver.valve.automatic_switch = automatic_switch

    @property
    def bypass(self) -> bool:
        return self.driver.valve.bypass

    @bypass.setter
    def bypass(self, bypass: bool) -> None:
        self.driver.valve.bypass = bypass
        signals.VALVE.bypass.emit(self.driver.valve.bypass)

    @override
    def save_configuration(self) -> None:
        self.driver.valve.save_configuration()

    def automatic_valve_change(self) -> None:
        self.driver.valve.automatic_valve_change()

    @override
    def load_configuration(self) -> None:
        self.driver.valve.load_configuration()
        self.fire_configuration_change()

    def fire_configuration_change(self) -> None:
        signals.VALVE.duty_cycle.emit(self.driver.valve.configuration.duty_cycle)
        signals.VALVE.period.emit(self.driver.valve.configuration.period)
        signals.VALVE.automatic_switch.emit(self.driver.valve.configuration.automatic_switch)

    @override
    def _incoming_data(self) -> None:
        init_headers = True
        now = datetime.now()
        date = str(now.strftime("%Y-%m-%d"))
        while self.driver.connected.is_set():
            self.driver.wait()
            if configuration.GUI.save.valve:
                if init_headers:
                    units = {"Time": "H:M:S", "Bypass": "bool"}
                    pd.DataFrame(units, index=["Y:M:D"]).to_csv(self._destination_folder + f"/{date}_gas.csv",
                                                                index_label="Date")
                    init_headers = False
                now = datetime.now()
                output_data = {"Time": str(now.strftime("%H:%M:%S")), "Bypass": self.bypass}
                output_data_data_frame = pd.DataFrame(output_data, index=[str(now.strftime("%Y-%m-%d"))])
                output_data_data_frame.to_csv(self._destination_folder + "/{date}_gas.csv", header=False, mode="a")
                time.sleep(1)


class Pump(Serial):
    def __init__(self, driver: hardware.motherboard.Driver):
        Serial.__init__(self, driver)
        self.driver = driver
        self.running = False
        self._enabled = False
        self.enable_on_run = True

    @property
    def flow_rate(self) -> float:
        return self.driver.pump.configuration.duty_cycle / hardware.motherboard.Pump.MAX_DUTY_CYCLE * 100

    @flow_rate.setter
    def flow_rate(self, flow_rate: float) -> None:
        if not 0 <= flow_rate <= 100:
            raise ValueError("Invalid value for duty cycle")
        self.driver.pump.configuration.duty_cycle = int(flow_rate / 100 * hardware.motherboard.Pump.MAX_DUTY_CYCLE)
        self.driver.pump.set_duty_cycle()

    def set_duty_cycle(self) -> None:
        if not self.enable_on_run:
            return
        self.driver.pump.enabled = not self.running
        self.enabled = not self.running
        self.running = not self.running

    @property
    def enabled(self) -> bool:
        return self._enabled

    @enabled.setter
    def enabled(self, enabled: bool) -> None:
        self._enabled = enabled
        signals.PUMP.enabled.emit(enabled)
        if enabled:
            self.driver.pump.enabled = True
            self.enable_pump()
        else:
            self.driver.pump.enabled = False
            self.disable_pump()

    def enable_pump(self) -> None:
        self.driver.pump.set_duty_cycle()

    def disable_pump(self) -> None:
        self.driver.pump.disable_pump()

    @override
    def save_configuration(self) -> None:
        self.driver.pump.save_configuration()

    @override
    def load_configuration(self) -> None:
        self.driver.pump.load_configuration()
        self.fire_configuration_change()

    @override
    def fire_configuration_change(self) -> None:
        signals.PUMP.flow_Rate.emit(self.flow_rate)


class Laser(Serial):
    buffer = buffer.Laser()

    def __init__(self, driver: hardware.laser.Driver):
        Serial.__init__(self, driver)
        self.driver = driver
        self._config_path = f"{minipti.module_path}/hardware/configs/laser.json"
        self.on_notification = Notify(default_notification_title="Laser",
                                      default_notification_icon=f"{minipti.module_path}/gui/images/hardware/laser.svg",
                                      default_notification_application_name="Laser Driver")
        self.off_notification = Notify(default_notification_title="Laser",
                                       default_notification_icon=f"{minipti.module_path}"
                                                                 f"/gui/images/hardware/laser/off.svg",
                                       default_notification_application_name="Laser Driver")

    @property
    @abstractmethod
    def config_path(self) -> str:
        ...

    @config_path.setter
    @abstractmethod
    def config_path(self, config_path: str) -> None:
        ...

    @property
    @abstractmethod
    def enabled(self) -> bool:
        ...

    @enabled.setter
    @abstractmethod
    def enabled(self, enabled: bool) -> None:
        ...

    @abstractmethod
    def load_configuration(self) -> None:
        ...

    @abstractmethod
    def save_configuration(self) -> None:
        ...

    @abstractmethod
    def apply_configuration(self) -> None:
        ...

    def _incoming_data(self):
        now = datetime.now()
        date = str(now.strftime("%Y-%m-%d"))
        while self.driver.connected.is_set():
            received_data: hardware.laser.Data = self.driver.data.get(block=True)
            Laser.buffer.append(received_data)
            signals.LASER.data.emit(Laser.buffer)
            signals.LASER.data_display.emit(received_data)
            if self.driver.sampling and configuration.GUI.save.laser:
                if self._init_headers:
                    units = {"Time": "H:M:S",
                             "Pump Laser Enabled": "bool",
                             "Pump Laser Voltage": "V",
                             "Probe Laser Enabled": "bool",
                             "Pump Laser Current": "mA",
                             "Probe Laser Current": "mA"}
                    pd.DataFrame(units, index=["Y:M:D"]).to_csv(self._destination_folder + f"/{date}_laser.csv",
                                                                index_label="Date")
                    self._init_headers = False
                now = datetime.now()
                output_data = {"Time": str(now.strftime("%H:%M:%S")),
                               "Pump Laser Enabled": received_data.high_power_laser_enabled,
                               "Pump Laser Voltage": received_data.high_power_laser_voltage,
                               "Probe Laser Enabled": received_data.low_power_laser_enabled,
                               "Pump Laser Current": received_data.high_power_laser_current,
                               "Probe Laser Current": received_data.low_power_laser_current}
                laser_data_frame = pd.DataFrame(output_data, index=[str(now.strftime("%Y-%m-%d"))])
                pd.DataFrame(laser_data_frame).to_csv(f"{self._destination_folder}/{date}_laser.csv", mode="a", header=False)

    def fire_configuration_change(self) -> None:
        ...


class Mode(enum.IntEnum):
    DISABLED = 0
    CONTINUOUS_WAVE = 1
    PULSED = 2


class PumpLaser(Laser):
    def __init__(self, driver: hardware.laser.Driver):
        Laser.__init__(self, driver)
        self.pump_laser = self.driver.high_power_laser
        self.on_notification.message = "Pump Laser is on"
        self.off_notification.message = "Pump Laser is off"

    def start_up(self) -> None:
        self.pump_laser.initialize()
        self.pump_laser.apply_configuration()

    @property
    def connected(self) -> bool:
        return self.driver.connected.is_set()

    @property
    def driver_bits(self) -> int:
        return self.pump_laser.configuration.bit_value

    @driver_bits.setter
    def driver_bits(self, bits: int) -> None:
        # With increasing the slider decreases its value but the voltage should increase, hence we subtract the bits.
        self.pump_laser.configuration.bit_value = hardware.laser.HighPowerLaser.NUMBER_OF_STEPS - bits
        self.fire_driver_bits_signal()
        self.pump_laser.set_voltage()

    @property
    @override
    def config_path(self) -> str:
        return self.pump_laser.config_path

    @config_path.setter
    @override
    def config_path(self, config_path: str) -> None:
        self.pump_laser.config_path = config_path

    @override
    def save_configuration(self) -> None:
        self.pump_laser.save_configuration()

    @override
    def load_configuration(self) -> None:
        self.pump_laser.load_configuration()

    @override
    def apply_configuration(self) -> None:
        self.pump_laser.apply_configuration()

    def fire_driver_bits_signal(self) -> None:
        bits: int = self.pump_laser.configuration.bit_value
        voltage: float = hardware.laser.HighPowerLaser.bit_to_voltage(bits)
        bits = hardware.laser.HighPowerLaser.NUMBER_OF_STEPS - bits
        signals.LASER.laser_voltage.emit(bits, voltage)

    @property
    @override
    def enabled(self) -> bool:
        return self.pump_laser.enabled

    @enabled.setter
    @override
    def enabled(self, enable: bool):
        if enable:
            self.on_notification.send(block=False)
        else:
            self.off_notification.send(block=False)
        self.pump_laser.enabled = enable
        signals.LASER.pump_laser_enabled.emit(enable)

    @property
    def current_bits_dac_1(self) -> int:
        return self.pump_laser.configuration.dac[0].bit_value

    @current_bits_dac_1.setter
    def current_bits_dac_1(self, bits: int) -> None:
        self.pump_laser.configuration.dac[0].bit_value = bits
        self.fire_current_bits_dac_1()
        self.pump_laser.set_dac(0)

    def fire_current_bits_dac_1(self) -> None:
        signals.LASER.current_dac.emit(0, self.pump_laser.configuration.dac[0].bit_value)

    @property
    def current_bits_dac_2(self) -> int:
        return self.pump_laser.configuration.dac[1].bit_value

    @current_bits_dac_2.setter
    def current_bits_dac_2(self, bits: int) -> None:
        self.pump_laser.configuration.dac[1].bit_value = bits
        self.fire_current_bits_dac2()
        self.pump_laser.set_dac(1)

    def fire_current_bits_dac2(self) -> None:
        signals.LASER.current_dac.emit(1, self.pump_laser.configuration.dac[1].bit_value)

    @property
    def dac_1_matrix(self) -> hardware.laser.DAC:
        return self.pump_laser.configuration.dac[0]

    @property
    def dac_2_matrix(self) -> hardware.laser.DAC:
        return self.pump_laser.configuration.dac[1]

    @staticmethod
    def _set_indices(dac_number: int, dac: hardware.laser.DAC) -> None:
        indices: typing.Annotated[list[int], 3] = []
        for i in range(3):
            if dac.continuous_wave[i]:
                indices.append(Mode.CONTINUOUS_WAVE)
            elif dac.pulsed_mode[i]:
                indices.append(Mode.PULSED)
            else:
                indices.append(Mode.DISABLED)
        signals.LASER.matrix_dac.emit(dac_number, indices)

    @dac_1_matrix.setter
    def dac_1_matrix(self, dac: hardware.laser.DAC) -> None:
        self.pump_laser.configuration.dac[0] = dac
        self.fire_dac_matrix_1()

    def fire_dac_matrix_1(self) -> None:
        PumpLaser._set_indices(dac_number=0, dac=self.dac_1_matrix)

    @dac_2_matrix.setter
    def dac_2_matrix(self, dac: hardware.laser.DAC) -> None:
        self.pump_laser.configuration.dac[1] = dac
        self.fire_dac_matrix_2()

    def fire_dac_matrix_2(self) -> None:
        PumpLaser._set_indices(dac_number=1, dac=self.dac_2_matrix)

    def update_dac_mode(self, dac: hardware.laser.DAC, channel: int, mode: int) -> None:
        if mode == Mode.CONTINUOUS_WAVE:
            dac.continuous_wave[channel] = True
            dac.pulsed_mode[channel] = False
        elif mode == Mode.PULSED:
            dac.continuous_wave[channel] = False
            dac.pulsed_mode[channel] = True
        elif mode == Mode.DISABLED:
            dac.continuous_wave[channel] = False
            dac.pulsed_mode[channel] = False
        self.pump_laser.set_dac_matrix()

    @override
    def fire_configuration_change(self) -> None:
        self.fire_driver_bits_signal()
        self.fire_current_bits_dac_1()
        self.fire_current_bits_dac2()
        self.fire_dac_matrix_1()
        self.fire_dac_matrix_2()


class ProbeLaserMode(enum.IntEnum):
    CONSTANT_LIGHT = 0
    CONSTANT_CURRENT = 1


class ProbeLaser(Laser):
    CURRENT_BITS = hardware.laser.LowPowerLaser.CURRENT_BITS

    def __init__(self, driver: hardware.laser.Driver):
        Laser.__init__(self, driver)
        self.probe_laser = self.driver.low_power_laser
        self.on_notification.message = "Probe Laser is on"
        self.off_notification.message = "Probe Laser is off"

    def start_up(self) -> None:
        self.probe_laser.initialize()
        self.probe_laser.apply_configuration()

    @property
    def connected(self) -> bool:
        return self.driver.connected.is_set()

    @property
    def current_bits_probe_laser(self) -> int:
        return self.probe_laser.configuration.current.bits

    @current_bits_probe_laser.setter
    def current_bits_probe_laser(self, bits: int) -> None:
        self.probe_laser.configuration.current.bits = bits
        self.probe_laser.set_current()
        bit, current = self.fire_current_bits_signal()
        signals.LASER.current_probe_laser.emit(hardware.laser.LowPowerLaser.CURRENT_BITS - bits, current)

    @property
    @override
    def config_path(self) -> str:
        return self.probe_laser.config_path

    @config_path.setter
    @override
    def config_path(self, config_path: str) -> None:
        self.probe_laser.config_path = config_path

    @override
    def save_configuration(self) -> None:
        self.probe_laser.save_configuration()

    @override
    def load_configuration(self) -> None:
        self.probe_laser.load_configuration()

    def fire_current_bits_signal(self) -> tuple[int, float]:
        bits: int = self.probe_laser.configuration.current.bits
        current: float = hardware.laser.LowPowerLaserConfig.bit_to_current(bits)
        signals.LASER.current_probe_laser.emit(hardware.laser.LowPowerLaser.CURRENT_BITS - bits, current)
        return bits, current

    @property
    @override
    def enabled(self) -> bool:
        return self.probe_laser.enabled

    @enabled.setter
    @override
    def enabled(self, enable: bool) -> None:
        if enable:
            self.on_notification.send(block=False)
        else:
            self.off_notification.send(block=False)
        self.probe_laser.enabled = enable
        signals.LASER.probe_laser_enabled.emit(enable)

    @property
    def photo_diode_gain(self) -> int:
        return self.probe_laser.configuration.photo_diode_gain

    @photo_diode_gain.setter
    def photo_diode_gain(self, photo_diode_gain: int) -> None:
        self.probe_laser.configuration.photo_diode_gain = photo_diode_gain
        self.fire_photo_diode_gain_signal()
        self.probe_laser.set_photo_diode_gain()

    def fire_photo_diode_gain_signal(self) -> None:
        signals.LASER.photo_gain.emit(self.probe_laser.configuration.photo_diode_gain - 1)

    @property
    def probe_laser_max_current(self) -> float:
        return self.probe_laser.configuration.current.max_mA

    @probe_laser_max_current.setter
    def probe_laser_max_current(self, current: float) -> None:
        if self.probe_laser.configuration.current.max_mA != current:
            self.probe_laser.configuration.current.max_mA = current
            self.fire_max_current_signal()

    def fire_max_current_signal(self) -> None:
        signals.LASER.max_current_probe_laser.emit(self.probe_laser.configuration.current.max_mA)

    @property
    def probe_laser_mode(self) -> ProbeLaserMode:
        if self.probe_laser.configuration.mode.constant_light:
            return ProbeLaserMode.CONSTANT_LIGHT
        else:
            return ProbeLaserMode.CONSTANT_CURRENT

    @probe_laser_mode.setter
    def probe_laser_mode(self, mode: ProbeLaserMode) -> None:
        if mode == ProbeLaserMode.CONSTANT_CURRENT:
            self.driver.low_power_laser.configuration.mode.constant_current = True
            self.driver.low_power_laser.configuration.mode.constant_light = False
        elif mode == ProbeLaserMode.CONSTANT_LIGHT:
            self.driver.low_power_laser.configuration.mode.constant_current = False
            self.driver.low_power_laser.configuration.mode.constant_light = True
        self.probe_laser.set_mode()
        self.fire_laser_mode_signal()

    def fire_laser_mode_signal(self) -> None:
        if self.probe_laser.configuration.mode.constant_light:
            signals.LASER.probe_laser_mode.emit(ProbeLaserMode.CONSTANT_LIGHT)
        else:
            signals.LASER.probe_laser_mode.emit(ProbeLaserMode.CONSTANT_CURRENT)

    @override
    def fire_configuration_change(self) -> None:
        self.fire_current_bits_signal()
        self.fire_laser_mode_signal()
        self.fire_photo_diode_gain_signal()
        self.fire_max_current_signal()

    @override
    def apply_configuration(self) -> None:
        self.probe_laser.apply_configuration()


class Tec(Serial):
    PUMP_LASER = 0
    PROBE_LASER = 1

    ROOM_TEMPERATURE = hardware.tec.ROOM_TEMPERATURE_CELSIUS

    _buffer = buffer.Tec()

    def __init__(self, driver: hardware.tec.Driver, channel=1):
        Serial.__init__(self, driver)
        self.driver = driver
        self.tec = self.driver.tec[channel]
        self.tec_signals = signals.TEC[channel]

    @property
    def connected(self) -> bool:
        return self.driver.connected.is_set()

    @property
    def enabled(self) -> bool:
        return self.tec.enabled

    @enabled.setter
    def enabled(self, enable) -> None:
        self.tec.enabled = enable
        self.tec_signals.enabled.emit(enable)

    @property
    def config_path(self) -> str:
        return self.tec.config_path

    @config_path.setter
    def config_path(self, config_path: str) -> None:
        self.tec.config_path = config_path

    @override
    def save_configuration(self) -> None:
        self.tec.save_configuration()

    @override
    def load_configuration(self) -> None:
        self.tec.load_configuration()
        self.fire_configuration_change()

    def apply_configuration(self) -> None:
        self.tec.apply_configuration()

    @property
    def p_value(self) -> float:
        return self.tec.configuration.pid.proportional_value

    @p_value.setter
    def p_value(self, p_value: float) -> None:
        self.tec.configuration.pid.proportional_value = p_value
        self.tec.set_pid_p_gain()

    @property
    def i_gain(self) -> float:
        return self.tec.configuration.pid.integral_value

    @i_gain.setter
    def i_gain(self, i_value: int) -> None:
        self.tec.configuration.pid.integral_value = i_value
        self.tec.set_pid_i_gain()

    @property
    def d_gain(self) -> int:
        return self.tec.configuration.pid.derivative_value

    @d_gain.setter
    def d_gain(self, d_value: int) -> None:
        self.tec.configuration.pid.derivative_value = d_value
        self.tec.set_pid_d_gain()

    @property
    def setpoint_temperature(self) -> float:
        return self.tec.configuration.system_parameter.setpoint_temperature

    @setpoint_temperature.setter
    def setpoint_temperature(self, new_setpoint_temperature: float) -> None:
        self.tec.configuration.system_parameter.setpoint_temperature = new_setpoint_temperature
        self.tec.set_setpoint_temperature_value()

    @property
    def loop_time(self) -> int:
        return self.tec.configuration.system_parameter.loop_time

    @loop_time.setter
    def loop_time(self, loop_time: int) -> None:
        self.tec.configuration.system_parameter.loop_time = loop_time
        self.tec.set_loop_time_ms()

    @property
    def max_power(self) -> float:
        return self.tec.configuration.system_parameter.max_power * 100  # percent

    @max_power.setter
    def max_power(self, max_power: float) -> None:
        max_power /= 100
        self.tec.configuration.system_parameter.max_power = max_power
        self.tec.set_max_power()

    @override
    def fire_configuration_change(self) -> None:
        self.tec_signals.d_gain.emit(self.d_gain)
        self.tec_signals.p_gain.emit(self.p_value)
        self.tec_signals.i_gain.emit(self.i_gain)
        self.tec_signals.setpoint_temperature.emit(self.setpoint_temperature)
        self.tec_signals.loop_time.emit(self.loop_time)
        self.tec_signals.max_power.emit(self.max_power)

    @override
    def _incoming_data(self) -> None:
        now = datetime.now()
        date = str(now.strftime("%Y-%m-%d"))
        while self.driver.connected.is_set():
            received_data: hardware.tec.Data = self.driver.data.get(block=True)
            self._buffer.append(received_data)
            signals.GENERAL_PURPORSE.tec_data.emit(self._buffer)
            signals.GENERAL_PURPORSE.tec_data_display.emit(received_data)
            if self.driver.sampling and configuration.GUI.save.tec:
                if self._init_headers:
                    units = {"Time": "H:M:S",
                             "PWM Duty Cycle Pump Laser": "%",
                             "PWM Duty Cycle Probe Laser": "%",
                             "TEC Pump Laser Enabled": "bool",
                             "TEC Probe Laser Enabled": "bool",
                             "Measured Temperature Pump Laser": "°C",
                             "Set Point Temperature Pump Laser": "°C",
                             "Measured Temperature Probe Laser": "°C",
                             "Set Point Temperature Probe Laser": "°C"}
                    pd.DataFrame(units, index=["Y:M:D"]).to_csv(f"{self._destination_folder}/{date}_tec.csv",
                                                                index_label="Date")
                    self._init_headers = False
                now = datetime.now()
                tec_data = {"Time": str(now.strftime("%H:%M:%S")),
                            "PWM Duty Cycle Pump Laser": received_data.pwm_duty_cycle[Tec.PUMP_LASER],
                            "PWM Duty Cycle Probe Laser": received_data.pwm_duty_cycle[Tec.PROBE_LASER],
                            "TEC Pump Laser Enabled": self.driver.tec[Tec.PUMP_LASER].enabled,
                            "TEC Probe Laser Enabled": self.driver.tec[Tec.PROBE_LASER].enabled,
                            "Measured Temperature Pump Laser": received_data.actual_temperature[Tec.PUMP_LASER],
                            "Set Point Temperature Pump Laser": received_data.set_point[Tec.PUMP_LASER],
                            "Measured Temperature Probe Laser": received_data.actual_temperature[Tec.PROBE_LASER],
                            "Set Point Temperature Probe Laser": received_data.set_point[Tec.PROBE_LASER]}
                tec_data_frame = pd.DataFrame(tec_data, index=[str(now.strftime("%Y-%m-%d"))])
                pd.DataFrame(tec_data_frame).to_csv(f"{self._destination_folder}/{date}_tec.csv",
                                                    header=False, mode="a")


@dataclass
class Driver:
    motherboard: hardware.motherboard.Driver = hardware.motherboard.Driver()
    laser: hardware.laser.Driver = hardware.laser.Driver()
    tec: hardware.tec.Driver = hardware.tec.Driver()


DRIVER: typing.Final = Driver()


@dataclass
class Tools:
    daq: DAQ = DAQ(DRIVER.motherboard)
    bms: BMS = BMS(DRIVER.motherboard)
    pump: Pump = Pump(DRIVER.motherboard)
    valve: Valve = Valve(DRIVER.motherboard)
    pump_laser: PumpLaser = PumpLaser(DRIVER.laser)
    probe_laser: ProbeLaser = ProbeLaser(DRIVER.laser)
    tec = [Tec(DRIVER.tec, Tec.PUMP_LASER), Tec(DRIVER.tec, Tec.PROBE_LASER)]


TOOLS: typing.Final = Tools()
