"""
Example file for usage of the characterisation API of the MiniPTI.
"""

import pandas as pd

import minipti


if __name__ == "__main__":
    interferometer = minipti.algorithm.interferometry.Interferometer(
        settings_path="sample_configs/settings.csv")
    interferometer.decimation_filepath = "sample_data/Decimation_Comercial.csv"
    interferometer.load_settings()

    # Using the default settings values
    characterization = minipti.algorithm.interferometry.Characterization(
        interferometer=interferometer)
    characterization()
    print(characterization)

    # Without default values
    characterization = minipti.algorithm.interferometry.Characterization(
        interferometer=interferometer
    )
    characterization.use_settings = False
    characterization()
    print(characterization)

    dc_signals = pd.read_csv("sample_data/Decimation_Comercial.csv")
    characterization.signals = dc_signals[[f"DC CH{i}" for i in range(1, 4)]].to_numpy()

    # Without knowing any parameter
    characterization.use_settings = False
    characterization()
    print(characterization)

    # With knowing the parameters and already calculated phases
    phases = pd.read_csv("sample_data/PTI_Inversion_Comercial.csv")
    characterization.phases = phases["Interferometric Phase"]
    characterization.characterise_interferometer()
    print(characterization)
