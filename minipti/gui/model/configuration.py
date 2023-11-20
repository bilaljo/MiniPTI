import dataclasses
import json
import logging
import os
import pathlib
from dataclasses import dataclass
from typing import Final

import dacite


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
    pump: bool = True


@dataclass(frozen=True)
class _DestinationFolder:
    use: bool = True
    default_path: str = "."


@dataclass(frozen=True)
class _SystemSettings:
    interferometric: bool = True
    response_phases: bool = True


@dataclass(frozen=True)
class _Valve:
    use: bool = True
    bypass_button: bool = True
    automatic_switch: bool = True


@dataclass(frozen=True)
class _Settings:
    use: bool = True
    measurement_settings: bool = True
    pump: bool = True
    system_settings: _SystemSettings = _SystemSettings()


@dataclass(frozen=True)
class _Save:
    daq: bool = True
    laser: bool = True
    tec: bool = True
    valve: bool = True
    pump: bool = True
    bms: bool = True


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
    interferometry: _Plot = _Plot()
    characterisation: _Plot = _Plot()
    measurement: _Plot = _Plot()


@dataclass(frozen=True)
class _Battery:
    use: bool = True


@dataclass(frozen=True)
class Connect:
    use: bool = True
    motherboard: bool = True
    tec_driver: bool = True
    laser_driver: bool = True


@dataclass(frozen=True)
class _GUI:
    window_title: str = "MiniPTI"
    logging: _Logging = _Logging()
    battery: _Battery = _Battery()
    destination_folder: _DestinationFolder = _DestinationFolder()
    settings: _Settings = _Settings()
    utilities: _Utilities = _Utilities()
    valve: _Valve = _Valve()
    save: _Save = _Save()
    use_shutdown: bool = True
    connect: Connect = Connect()
    probe_laser: _LaserWindow = _LaserWindow()
    pump_laser: _LaserWindow = _LaserWindow()
    plots: _Plots = _Plots()
    on_run: _OnRun = _OnRun()


def _parse_configuration() -> _GUI:
    module_path = f"{pathlib.Path(__file__).parent.parent}/configs"
    for file in os.listdir(module_path):
        if not pathlib.Path(file).suffix == ".json":
            continue
        with open(f"{module_path}/{file}") as config:
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
                    KeyError) as e:
                logging.debug(e)
                continue
    return _GUI()  # Default constructed object


def _generate_config_file() -> None:
    gui = _GUI()
    module_path = f"{pathlib.Path(__file__).parent.parent}/configs"
    with open(f"{module_path}/sandbox.json", "w") as config:
        gui_dict = {"use": True, "GUI": dataclasses.asdict(gui)}
        json.dump(gui_dict, config, indent=4)


if __name__ == "__main__":
    _generate_config_file()

GUI: Final = _parse_configuration()
