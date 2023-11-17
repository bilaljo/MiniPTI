import json
import os
import pathlib
from dataclasses import dataclass
from typing import Final

import dacite

import minipti


@dataclass(frozen=True)
class _Logging:
    console: bool = True
    file: bool = True


@dataclass(frozen=True)
class _TEC:
    probe_laser: bool = True
    pump_laser: bool = True


@dataclass(frozen=True)
class _Laser:
    tec_driver: bool = True
    laser_driver: bool = True


@dataclass(frozen=True)
class _LaserWindow(_Laser):
    use: bool = True


@dataclass(frozen=True)
class _OnRun:
    DAQ: bool = True
    BMS: bool = True
    pump_laser: _Laser = _Laser(False, False)
    probe_laser: _Laser = _Laser(False, False)


@dataclass(frozen=True)
class _HomePlots:
    dc_signals: bool = True
    interferometric_phase: bool = False
    pti_signal: bool = True


@dataclass(frozen=True)
class _Devices(_Laser):
    motherboard: bool = True


@dataclass(frozen=True)
class _Connect:
    use: bool = True
    devices: _Devices = _Devices()


@dataclass(frozen=True)
class _DestinationFolder:
    use: bool = True
    default_path: str = "."


@dataclass(frozen=True)
class _Home:
    use: bool = True
    use_settings: bool = True
    use_utilities: bool = True
    use_valve: bool = True
    on_run: _OnRun = _OnRun()
    connect: _Connect = _Connect()
    use_shutdown: bool = True
    plots: _HomePlots = _HomePlots()


@dataclass(frozen=True)
class _SystemSettings:
    interferometric: bool = True
    response_phases: bool = True


@dataclass(frozen=True)
class _Settings:
    use: bool = True
    valve: bool = True
    measurement_settings: bool = True
    system_settings: _SystemSettings = _SystemSettings()


@dataclass(frozen=True)
class _Calculation:
    use: bool = True
    decimation: bool = True
    interferometry: bool = True
    inversion: bool = True
    characterisation: bool = True


@dataclass(frozen=True)
class _OfflinePlots:
    dc: bool = True
    interferometry: bool = True
    inversion: bool = True


@dataclass(frozen=True)
class _Utilities:
    use: bool = True
    calculate: _Calculation = _Calculation()
    plot: _OfflinePlots = _OfflinePlots()


@dataclass(frozen=True)
class _Plot:
    use: bool = True


@dataclass(frozen=True)
class _Plots:
    dc_signals: _Plot = _Plot()
    amplitudes: _Plot = _Plot()
    output_phases: _Plot = _Plot()
    interferometric_phase: _Plot = _Plot()
    sensitivity: _Plot = _Plot()
    pti_signal: _Plot = _Plot()


@dataclass(frozen=True)
class _Battery:
    use: bool = False


@dataclass(frozen=True)
class _GUI:
    window_title: str = "MiniPTI"
    logging: _Logging = _Logging()
    battery: _Battery = _Battery()
    home: _Home = _Home()
    destination_folder: _DestinationFolder = _DestinationFolder()
    settings: _Settings = _Settings()
    utilities: _Utilities = _Utilities()
    probe_laser: _LaserWindow = _LaserWindow()
    pump_laser: _LaserWindow = _LaserWindow()
    plots: _Plots = _Plots()


def _parse_configuration() -> _GUI:
    for file in os.listdir(f"{minipti.module_path}/gui/configs"):
        if not pathlib.Path(file).suffix == ".json":
            continue
        with open(f"{minipti.module_path}/gui/configs/{file}") as config:
            try:
                loaded_configuration = json.load(config)
                if loaded_configuration["use"]:
                    path: str = loaded_configuration["GUI"]["destination_folder"]["default_path"]
                    path_components = path.split("\\")
                    if path_components[0] == "Desktop":
                        desktop = f"{pathlib.Path.home()}/Desktop"
                        loaded_configuration["GUI"]["destination_folder"]["default_path"] = desktop
                    return dacite.from_dict(_GUI, loaded_configuration["GUI"])
            except (json.decoder.JSONDecodeError, dacite.WrongTypeError, dacite.exceptions.MissingValueError,
                    KeyError):
                continue
    return _GUI()  # Default constructed object


GUI: Final = _parse_configuration()
