"""
Example file for usage of the characterisation API of the MiniPTI.
"""
import os
import sys

import pandas as pd

sys.path.extend(".")
from minipti.algorithm import interferometry


def default_settings_save_to_csv() -> None:
    interferometer = interferometry.Interferometer(settings_path="examples/sample_configs/algorithm_settings.csv")
    interferometer.decimation_filepath = "examples/sample_data/Decimation_Comercial.csv"
    interferometer.load_settings()
    characterization = interferometry.Characterization(interferometer=interferometer)
    characterization.characterise()
    print(characterization)


def without_default_settings_save_to_csv() -> None:
    interferometer = interferometry.Interferometer(settings_path="examples/sample_configs/algorithm_settings.csv")
    interferometer.decimation_filepath = "examples/sample_data/Decimation_Comercial.csv"
    characterization = interferometry.Characterization(interferometer=interferometer, use_configuration=False)
    characterization.characterise()
    print(characterization)


def default_settings_without_save_to_csv() -> None:
    interferometer = interferometry.Interferometer(settings_path="examples/sample_configs/algorithm_settings.csv")
    interferometer.load_settings()
    characterization = interferometry.Characterization(interferometer=interferometer)
    characterization.use_configuration = False
    data = pd.read_csv("examples/sample_data/Decimation_Comercial.csv")
    dc_signals = data[[f"DC CH{i}" for i in range(1, 4)]].to_numpy()
    for _ in characterization.process_characterisation(dc_signals):
        print(characterization.interferometer)


def wihtout_default_settings_without_save_to_csv() -> None:
    interferometer = interferometry.Interferometer()
    characterization = interferometry.Characterization(interferometer=interferometer, use_configuration=False)
    data = pd.read_csv("examples/sample_data/Decimation_Comercial.csv")
    dc_signals = data[[f"DC CH{i}" for i in range(1, 4)]].to_numpy()
    for _ in characterization.process_characterisation(dc_signals):
        print(characterization.interferometer)


if __name__ == "__main__":
    default_settings_save_to_csv()
    without_default_settings_save_to_csv()
    default_settings_without_save_to_csv()
    wihtout_default_settings_without_save_to_csv()
    os.remove("Characterisation.csv")
