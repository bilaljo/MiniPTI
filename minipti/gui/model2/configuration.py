import typing
from dataclasses import dataclass


@dataclass(frozen=True)
class Logging:
    console: bool = True
    file: bool = True


@dataclass(frozen=True)
class TEC:
    probe_laser: bool = True
    pump_laser: bool = True


@dataclass(frozen=True)
class Laser:
    use: bool = True
    tec_driver: bool = True
    laser_driver: bool = True


@dataclass(frozen=True)
class OnRun:
    DAQ: bool = True
    BMS: bool = True
    laser: Laser = Laser()
    tec: TEC = TEC()


@dataclass(frozen=True)
class Plots:
    dc_signals: bool = True
    interferometric_phase: bool = False
    pti_signal: bool = True


@dataclass(frozen=True)
class Home:
    use: bool = True
    use_utilities: bool = True
    on_run: OnRun = OnRun()
    plots: Plots = Plots()


@dataclass(frozen=True)
class SystemSettings:
    interferometric: bool = True
    response_phases: bool = True


@dataclass(frozen=True)
class Settings:
    valve: bool = True
    measurement_settings: bool = True
    system_settings: SystemSettings = SystemSettings()


@dataclass(frozen=True)
class Devices:
    daq: bool = True
    laser_driver: bool = True
    tec_driber: bool = True


@dataclass(frozen=True)
class Utilities:
    calculate: bool = True
    plot: bool = True
    devices: Devices = Devices()


@dataclass(frozen=True)
class Plot:
    use: bool = True


@dataclass(frozen=True)
class Plots:
    dc_signals: Plot = Plot()
    amplitudes: Plot = Plot()
    output_phases: Plot = Plot()
    interferometric_phase: Plot = Plot()
    sensitivity: Plot = Plot()
    pti_signal: Plot = Plot()


@dataclass(frozen=True)
class Battery:
    use: bool = True


@dataclass(frozen=True)
class GUI:
    logging: Logging = Logging()
    battery: Battery = Battery()
    home: Home = Home()
    settings: Settings = Settings()
    utilities: Utilities = Utilities()
    probe_laser: Laser = Laser()
    pump_laser: Laser = Laser()
    plots: Plots = Plots()
