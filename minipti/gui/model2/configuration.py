from dataclasses import dataclass


@dataclass
class Logging:
    console: bool = True
    file: bool = True


@dataclass
class TEC:
    probe_laser: bool = True
    pump_laser: bool = True


@dataclass
class Laser:
    probe_laser: bool = True
    pump_laser: bool = True


@dataclass
class OnRun:
    DAQ: bool = True
    BMS: bool = True
    laser: Laser = Laser()
    tec: TEC = TEC()


@dataclass
class Plots:
    dc_signals: bool = True
    interferometric_phase: bool = False
    pti_signal: bool = True


@dataclass
class Home:
    use: bool = True
    use_utilities: bool = True
    on_run: OnRun = OnRun()
    plots: Plots = Plots()


@dataclass
class SystemSettings:
    interferometric: bool = True
    response_phases: bool = True


@dataclass
class Settings:
    valve: bool = True
    measurement_settings: bool = True
    system_settings: SystemSettings = SystemSettings()


@dataclass
class Devices:
    daq: bool = True
    laser_driver: bool = True
    tec_driber: bool = True


@dataclass
class Utilities:
    calculate: bool = True
    plot: bool = True
    devices: Devices = Devices()


@dataclass
class Laser:
    use: bool = True
    tec_driver: bool = True
    laser_driver: bool = True


@dataclass
class Plot:
    use: bool = True


@dataclass
class Plots:
    dc_signals: Plot = Plot()
    amplitudes: Plot = Plot()
    output_phases: Plot = Plot()
    interferometric_phase: Plot = Plot()
    sensitivity: Plot = Plot()
    pti_signal: Plot = Plot()


@dataclass
class Battery:
    use: bool = True


@dataclass
class GUI:
    logging: Logging = Logging()
    battery: Battery = Battery()
    home: Home = Home()
    settings: Settings = Settings()
    utilities: Utilities = Utilities()
    probe_laser: Laser = Laser()
    pump_laser: Laser = Laser()
    plots: Plots = Plots()
