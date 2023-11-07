import json
import os
import pathlib
from dataclasses import dataclass
from typing import Final

import dacite

import minipti


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
    tec_driver: bool = True
    laser_driver: bool = True


@dataclass(frozen=True)
class LaserWindow(Laser):
    use: bool = True


@dataclass(frozen=True)
class OnRun:
    DAQ: bool = True
    BMS: bool = True
    pump_laser: Laser = Laser(False, False)
    probe_laser: Laser = Laser(False, False)


@dataclass(frozen=True)
class Plots:
    dc_signals: bool = True
    interferometric_phase: bool = False
    pti_signal: bool = True


@dataclass(frozen=True)
class Devices(Laser):
    motherboard: bool = True


@dataclass(frozen=True)
class Connect:
    use: bool = True
    devices: Devices = Devices()


@dataclass(frozen=True)
class DestinationFolder:
    use: bool = True


@dataclass(frozen=True)
class Home:
    use: bool = True
    use_settings: bool = True
    use_utilities: bool = True
    use_valve: bool = True
    on_run: OnRun = OnRun()
    connect: Connect = Connect()
    destination_folder: DestinationFolder = DestinationFolder()
    use_shutdown: bool = False
    plots: Plots = Plots()


@dataclass(frozen=True)
class SystemSettings:
    interferometric: bool = True
    response_phases: bool = True


@dataclass(frozen=True)
class Settings:
    use: bool = True
    valve: bool = True
    measurement_settings: bool = True
    system_settings: SystemSettings = SystemSettings()


@dataclass(frozen=True)
class Calculation:
    use: bool = True
    decimation: bool = True
    interferometry: bool = True
    inversion: bool = True
    characterisation: bool = True


@dataclass(frozen=True)
class OfflinePlots:
    dc: bool = True
    interferometry: bool = True
    inversion: bool = True


@dataclass(frozen=True)
class Utilities:
    use: bool = True
    calculate: Calculation = Calculation()
    plot: OfflinePlots = OfflinePlots()


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
    use: bool = False


@dataclass(frozen=True)
class GUI:
    window_title: str = "MiniPTI"
    logging: Logging = Logging()
    battery: Battery = Battery()
    home: Home = Home()
    settings: Settings = Settings()
    utilities: Utilities = Utilities()
    probe_laser: LaserWindow = LaserWindow()
    pump_laser: LaserWindow = LaserWindow()
    plots: Plots = Plots()


def _parse_configuration() -> GUI:
    for file in os.listdir(f"{minipti.module_path}/gui/configs"):
        if not pathlib.Path(file).suffix == ".json":
            continue
        with open(f"{minipti.module_path}/gui/configs/{file}") as config:
            try:
                loaded_configuration = json.load(config)
                if loaded_configuration["use"]:
                    return dacite.from_dict(GUI, loaded_configuration["GUI"])
            except (json.decoder.JSONDecodeError, dacite.WrongTypeError, dacite.exceptions.MissingValueError):
                continue
    return GUI()  # Default constructed object


GUI: Final = _parse_configuration()
