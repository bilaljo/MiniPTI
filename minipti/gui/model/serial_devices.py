import enum
import logging
import os
import platform
import subprocess
import threading
import time
import typing
from abc import abstractmethod
from dataclasses import asdict, dataclass
from datetime import datetime

import pandas as pd
from notifypy import Notify
from overrides import override

import minipti
from minipti import hardware
from minipti.gui.model import buffer
from minipti.gui.model import signals


LaserData = hardware.laser.Data

TecData = hardware.tec.Data


class Serial:
    """
    This class is a base class for subclasses of the driver objects from driver/serial.
    """
    def __init__(self):
        signals.GENERAL_PURPORSE.destination_folder_changed.connect(self._update_destination_folder)
        self._destination_folder = os.getcwd()
        self._init_headers = True
        self._running = False

    @property
    def is_found(self) -> bool:
        return self.driver.is_found

    @property
    @abstractmethod
    def driver(self) -> hardware.serial_device.Driver:
        ...

    def _daq_running_changed(self, running) -> None:
        self._running = running

    # @QtCore.pyqtSlot(str)
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

    @classmethod
    @abstractmethod
    def save_configuration(cls) -> None:
        ...

    @abstractmethod
    def fire_configuration_change(self) -> None:
        """
        By initiation of a Serial Object (on which the laser model relies) the configuration is
        already set and do not fire events to update the GUI. This function is hence only called
        once to manually activate the firing.
        """

    @abstractmethod
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


@dataclass
class Battery:
    percentage: int
    minutes_left: int


class Motherboard(Serial):
    _driver = hardware.motherboard.Driver()
    running_event: threading.Event = threading.Event()
    MINIUM_PERCENTAGE = 15
    CRITICAL_PERCENTAGE = 5

    def __init__(self):
        Serial.__init__(self)
        self.bms_data: tuple[float, float] = (0, 0)
        self.initialized: bool = False
        signals.DAQ.running.connect(self._daq_running_changed)

    def shutdown_procedure(self) -> None:
        self.driver.bms.do_shutdown()
        time.sleep(0.5)  # Give the calculations threads time to finish their write operation
        if platform.system() == "Windows":
            subprocess.run(r"shutdown /s /t 1", shell=True)
        else:
            subprocess.run("sleep 0.5s && poweroff", shell=True)

    @property
    @override
    def driver(self) -> hardware.motherboard.Driver:
        return Motherboard._driver

    @property
    def connected(self) -> bool:
        return self.driver.connected.is_set()

    @staticmethod
    def centi_kelvin_to_celsius(temperature: float) -> float:
        return round((temperature - 273.15) / 100, 2)

    def _incoming_data(self) -> None:
        while self.driver.connected.is_set():
            shudtown, bms_data = self.driver.bms_data
            if shudtown:
                logging.critical("BMS has started a shutdown cause of almost battery")
                logging.warning("The system will make an emergency shutdown now")
                self.shutdown_procedure()
                return
            elif Motherboard.CRITICAL_PERCENTAGE < bms_data.battery_percentage\
                    < Motherboard.MINIUM_PERCENTAGE:
                logging.warning(f"Battery below {Motherboard.MINIUM_PERCENTAGE}.")
                logging.warning("An automatic shutdown will occur soon")
            elif bms_data.battery_percentage < Motherboard.CRITICAL_PERCENTAGE:
                logging.critical("Battery too low")
                logging.warning("The system will make an emergency shutdown now")
                self.shutdown_procedure()
                return
            bms_data.battery_temperature = Motherboard.centi_kelvin_to_celsius(bms_data.battery_temperature)
            signals.GENERAL_PURPORSE.battery_state.emit(Battery(bms_data.battery_percentage, bms_data.minutes_left))
            if self.running:
                if self._init_headers:
                    units = {"Time": "H:M:S", "External DC Power": "bool",
                             "Charging Battery": "bool",
                             "Minutes Left": "min", "Charging Level": "%", "Temperature": "°C", "Current": "mA",
                             "Voltage": "V", "Full Charge Capacity": "mAh", "Remaining Charge Capacity": "mAh"}
                    pd.DataFrame(units, index=["Y:M:D"]).to_csv(self._destination_folder + "/BMS.csv",
                                                                index_label="Date")
                    self.init_header = False
                now = datetime.now()
                output_data = {"Time": str(now.strftime("%H:%M:%S"))}
                for key, value in asdict(bms_data).items():
                    output_data[key.replace("_", " ").title()] = value
                bms_data_frame = pd.DataFrame(output_data, index=[str(now.strftime("%Y-%m-%d"))])
                bms_data_frame.to_csv(self._destination_folder + "/BMS.csv", header=False, mode="a")

    @property
    def running(self) -> bool:
        return Motherboard.running_event.is_set()

    @running.setter
    def running(self, running):
        self._running = running
        if running:
            # Before we start a new run, we clear all old data
            self.driver.reset()
            signals.DAQ.clear.emit()
            self.driver.daq.running.set()
            signals.DAQ.running.emit(True)
            self.running_event.set()
        else:
            self.driver.daq.running.clear()
            signals.DAQ.running.emit(False)
            self.running_event.clear()

    def shutdown(self) -> None:
        self.driver.bms.do_shutdown()

    @abstractmethod
    def load_configuration(self) -> None:
        ...

    @abstractmethod
    def save_configuration(self) -> None:
        ...

    @abstractmethod
    def fire_configuration_change(self) -> None:
        ...


class DAQ(Motherboard):
    def __init__(self):
        Motherboard.__init__(self)
        self.daq = DAQ._driver.daq

    @property
    def number_of_samples(self) -> int:
        return self.daq.configuration.number_of_samples

    @number_of_samples.setter
    def number_of_samples(self, samples: int) -> None:
        self.daq.number_of_samples = samples

    def save_configuration(self) -> None:
        self.daq.save_configuration()

    def load_configuration(self) -> None:
        self.daq.load_configuration()
        self.fire_configuration_change()

    @override
    def fire_configuration_change(self) -> None:
        signals.DAQ.samples_changed.emit(self.daq.configuration.number_of_samples)


class Valve(Motherboard):
    def __init__(self):
        Motherboard.__init__(self)
        self.valve = Valve._driver.valve

    @property
    def period(self) -> int:
        return self.valve.configuration.period

    @period.setter
    def period(self, period: int) -> None:
        if period < 0:
            raise ValueError("Invalid value for period")
        self.valve.configuration.period = period

    @property
    def duty_cycle(self) -> int:
        return self.valve.configuration.duty_cycle

    @duty_cycle.setter
    def duty_cycle(self, duty_cycle: int) -> None:
        if not 0 < self.valve.configuration.duty_cycle < 100:
            raise ValueError("Invalid value for duty cycle")
        self.valve.configuration.duty_cycle = duty_cycle

    @property
    def automatic_switch(self) -> bool:
        return self.valve.automatic_switch.is_set()

    @automatic_switch.setter
    def automatic_switch(self, automatic_switch: bool) -> None:
        self.valve.configuration.automatic_switch = automatic_switch
        if automatic_switch:
            self.valve.automatic_switch.set()
            self.valve.automatic_valve_change()
        else:
            self.valve.automatic_switch.clear()

    @property
    def enable(self) -> bool:
        return self.valve.bypass

    @enable.setter
    def enable(self, state: bool) -> None:
        self.valve.bypass = state
        signals.VALVE.bypass.emit(state)

    @override
    def save_configuration(self) -> None:
        self.valve.save_configuration()

    @override
    def load_configuration(self) -> None:
        self.valve.load_configuration()
        self.fire_configuration_change()

    def fire_configuration_change(self) -> None:
        signals.VALVE.duty_cycle.emit(self.valve.configuration.duty_cycle)
        signals.VALVE.period.emit(self.valve.configuration.period)
        signals.VALVE.automatic_switch.emit(self.valve.configuration.automatic_switch)


class Laser(Serial):
    buffer = buffer.Laser()
    _driver = hardware.laser.Driver()

    def __init__(self):
        Serial.__init__(self)
        self._config_path = f"{minipti.module_path}/hardware/configs/laser.json"
        self.on_notification = Notify(default_notification_title="Laser",
                                      default_notification_icon=f"{minipti.module_path}/gui/images/hardware/laser.svg",
                                      default_notification_application_name="Laser Driver")
        self.off_notification = Notify(default_notification_title="Laser",
                                       default_notification_icon=f"{minipti.module_path}"
                                                                 f"/gui/images/hardware/laser/off.svg",
                                       default_notification_application_name="Laser Driver")

    @property
    @override
    def driver(self) -> hardware.laser.Driver:
        return Laser._driver

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
        while self.driver.connected:
            received_data: hardware.laser.Data = self.driver.data.get(block=True)
            Laser.buffer.append(received_data)
            signals.LASER.data.emit(Laser.buffer)
            signals.LASER.data_display.emit(received_data)
            if Motherboard.running_event.is_set():
                if self._init_headers:
                    units = {"Time": "H:M:S",
                             "Pump Laser Enabled": "bool",
                             "Pump Laser Voltage": "V",
                             "Probe Laser Enabled": "bool",
                             "Pump Laser Current": "mA",
                             "Probe Laser Current": "mA"}
                    pd.DataFrame(units, index=["Y:M:D"]).to_csv(self._destination_folder + "/laser.csv",
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
                pd.DataFrame(laser_data_frame).to_csv(f"{self._destination_folder}/laser.csv", mode="a", header=False)

    def fire_configuration_change(self) -> None:
        ...


class Mode(enum.IntEnum):
    DISABLED = 0
    CONTINUOUS_WAVE = 1
    PULSED = 2


class PumpLaser(Laser):
    def __init__(self):
        Laser.__init__(self)
        self.pump_laser = self.driver.high_power_laser
        self.on_notification.message = "Pump Laser is on"
        self.off_notification.message = "Pump Laser is off"

    @property
    def connected(self) -> bool:
        return self.driver.connected.is_set()

    @property
    def driver_bits(self) -> int:
        return self.pump_laser.configuration.bit_value

    @driver_bits.setter
    def driver_bits(self, bits: int) -> None:
        # With increasing the slider decreases its value but the voltage should increase, hence we subtract the bits.
        self.pump_laser.configuration.bit_value = hardware.laser.HighPowerLaserConfig.NUMBER_OF_STEPS - bits
        self.fire_driver_bits_signal()
        self.pump_laser.set_voltage()

    @property
    def config_path(self) -> str:
        return self.pump_laser.config_path

    @config_path.setter
    @abstractmethod
    def config_path(self, config_path: str) -> None:
        self.pump_laser.config_path = config_path

    def save_configuration(self) -> None:
        self.pump_laser.save_configuration()

    def load_configuration(self) -> None:
        self.pump_laser.load_configuration()

    def apply_configuration(self) -> None:
        self.pump_laser.apply_configuration()

    def fire_driver_bits_signal(self) -> None:
        bits: int = self.pump_laser.configuration.bit_value
        voltage: float = hardware.laser.HighPowerLaserConfig.bit_to_voltage(bits)
        bits = hardware.laser.HighPowerLaserConfig.NUMBER_OF_STEPS - bits
        signals.LASER.laser_voltage.emit(bits, voltage)

    @property
    def enabled(self) -> bool:
        return self.pump_laser.enabled

    @enabled.setter
    def enabled(self, enable: bool):
        if enable:
            self.on_notification.send(block=False)
        else:
            self.off_notification.send(block=False)
        self.pump_laser.enabled = enable
        signals.LASER.pump_laser_enabled.emit(enable)

    @property
    def current_bits_dac_1(self) -> int:
        return self.pump_laser.configuration.DAC[0].bit_value

    @current_bits_dac_1.setter
    def current_bits_dac_1(self, bits: int) -> None:
        self.pump_laser.configuration.DAC[0].bit_value = bits
        self.fire_current_bits_dac_1()
        self.pump_laser.set_dac(0)

    def fire_current_bits_dac_1(self) -> None:
        signals.LASER.current_dac.emit(0, self.pump_laser.configuration.DAC[0].bit_value)

    @property
    def current_bits_dac_2(self) -> int:
        return self.pump_laser.configuration.DAC[1].bit_value

    @current_bits_dac_2.setter
    def current_bits_dac_2(self, bits: int) -> None:
        self.pump_laser.configuration.DAC[1].bit_value = bits
        self.fire_current_bits_dac2()
        self.pump_laser.set_dac(1)

    def fire_current_bits_dac2(self) -> None:
        signals.LASER.current_dac.emit(1, self.pump_laser.configuration.DAC[1].bit_value)

    @property
    def dac_1_matrix(self) -> hardware.laser.DAC:
        return self.pump_laser.configuration.DAC[0]

    @property
    def dac_2_matrix(self) -> hardware.laser.DAC:
        return self.pump_laser.configuration.DAC[1]

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
        self.pump_laser.configuration.DAC[0] = dac
        self.fire_dac_matrix_1()

    def fire_dac_matrix_1(self) -> None:
        PumpLaser._set_indices(dac_number=0, dac=self.dac_1_matrix)

    @dac_2_matrix.setter
    def dac_2_matrix(self, dac: hardware.laser.DAC) -> None:
        self.pump_laser.configuration.DAC[1] = dac
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

    def __init__(self):
        Laser.__init__(self)
        self.probe_laser = self.driver.low_power_laser
        self.on_notification.message = "Probe Laser is on"
        self.off_notification.message = "Probe Laser is off"

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
    def config_path(self) -> str:
        return self.probe_laser.config_path

    @config_path.setter
    @abstractmethod
    def config_path(self, config_path: str) -> None:
        self.probe_laser.config_path = config_path

    def save_configuration(self) -> None:
        self.probe_laser.save_configuration()

    def load_configuration(self) -> None:
        self.probe_laser.load_configuration()

    def fire_current_bits_signal(self) -> tuple[int, float]:
        bits: int = self.probe_laser.configuration.current.bits
        current: float = hardware.laser.LowPowerLaserConfig.bit_to_current(bits)
        signals.LASER.current_probe_laser.emit(hardware.laser.LowPowerLaser.CURRENT_BITS - bits, current)
        return bits, current

    @property
    def enabled(self) -> bool:
        return self.probe_laser.enabled

    @enabled.setter
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

    def fire_configuration_change(self) -> None:
        self.fire_current_bits_signal()
        self.fire_laser_mode_signal()
        self.fire_photo_diode_gain_signal()
        self.fire_max_current_signal()

    def apply_configuration(self) -> None:
        self.probe_laser.apply_configuration()


class Tec(Serial):
    PUMP_LASER = 0
    PROBE_LASER = 1

    ROOM_TEMPERATURE = hardware.tec.ROOM_TEMPERATURE_CELSIUS

    driver = hardware.tec.Driver()
    _buffer = buffer.Tec()

    def __init__(self, channel: int = 1):
        Serial.__init__(self)
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
        while self.driver.connected.is_set():
            received_data: hardware.tec.Data = self.driver.data.get(block=True)
            self._buffer.append(received_data)
            signals.GENERAL_PURPORSE.tec_data.emit(self._buffer)
            signals.GENERAL_PURPORSE.tec_data_display.emit(received_data)
            if Motherboard.running_event.is_set():
                if self._init_headers:
                    units = {"Time": "H:M:S",
                             "TEC Pump Laser Enabled": "bool",
                             "TEC Probe Laser Enabled": "bool",
                             "Measured Temperature Pump Laser": "°C",
                             "Set Point Temperature Pump Laser": "°C",
                             "Measured Temperature Probe Laser": "°C",
                             "Set Point Temperature Probe Laser": "°C"}
                    pd.DataFrame(units, index=["Y:M:D"]).to_csv(f"{self._destination_folder}/tec.csv",
                                                                index_label="Date")
                    self._init_headers = False
                now = datetime.now()
                tec_data = {"Time": str(now.strftime("%H:%M:%S")),
                            "TEC Pump Laser Enabled": self.driver.tec[Tec.PUMP_LASER].enabled,
                            "TEC Probe Laser Enabled": self.driver.tec[Tec.PROBE_LASER].enabled,
                            "Measured Temperature Pump Laser": received_data.actual_temperature[Tec.PUMP_LASER],
                            "Set Point Temperature Pump Laser": received_data.set_point[Tec.PUMP_LASER],
                            "Measured Temperature Probe Laser": received_data.actual_temperature[Tec.PROBE_LASER],
                            "Set Point Temperature Probe Laser": received_data.set_point[Tec.PROBE_LASER]}
                tec_data_frame = pd.DataFrame(tec_data, index=[str(now.strftime("%Y-%m-%d"))])
                pd.DataFrame(tec_data_frame).to_csv(f"{self._destination_folder}/tec.csv",
                                                    header=False, mode="a")
