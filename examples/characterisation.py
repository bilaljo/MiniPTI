"""
Example file for usage of the characterisation API of the MiniPTI.
"""
import os

import pandas as pd

from minipti.algorithm import interferometry


def default_settings_save_to_csv() -> None:
    interferometer = interferometry.Interferometer(settings_path="sample_configs/settings.csv")
    interferometer.decimation_filepath = "sample_data/Decimation_Comercial.csv"
    interferometer.load_settings()
    characterization = interferometry.Characterization(interferometer=interferometer)
    characterization.characterise()
    print(characterization)


def without_default_settings_save_to_csv() -> None:
    interferometer = interferometry.Interferometer(settings_path="sample_configs/settings.csv")
    interferometer.decimation_filepath = "sample_data/Decimation_Comercial.csv"
    characterization = interferometry.Characterization(interferometer=interferometer)
    characterization.use_settings = False
    characterization.characterise()
    print(characterization)


def default_settings_without_save_to_csv() -> None:
    interferometer = interferometry.Interferometer(settings_path="sample_configs/settings.csv")
    interferometer.load_settings()
    characterization = interferometry.Characterization(interferometer=interferometer)
    characterization.use_settings = False
    dc_signals = pd.read_csv("sample_data/Decimation_Comercial.csv")[[f"DC CH{i}" for i in range(1, 4)]].to_numpy()
    for _ in characterization.process_characterisation(dc_signals):
        print(characterization.interferometer)


def wihtout_default_settings_without_save_to_csv() -> None:
    interferometer = interferometry.Interferometer()
    characterization = interferometry.Characterization(interferometer=interferometer)
    characterization.use_settings = False
    dc_signals = pd.read_csv("sample_data/Decimation_Comercial.csv")[[f"DC CH{i}" for i in range(1, 4)]].to_numpy()
    for _ in characterization.process_characterisation(dc_signals):
        print(characterization.interferometer)


if __name__ == "__main__":
    default_settings_save_to_csv()
    without_default_settings_save_to_csv()
    default_settings_without_save_to_csv()
    wihtout_default_settings_without_save_to_csv()
    os.remove("Characterisation.csv")
