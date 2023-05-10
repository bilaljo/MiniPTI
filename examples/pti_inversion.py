"""
Example file for the usage of the inversion algorithm of the MiniPTI.
"""
import os

import pandas as pd

from minipti.algorithm import interferometry, pti


if __name__ == "__main__":
    interferometer = interferometry.Interferometer(settings_path="sample_configs/settings.csv")
    interferometer.load_settings()
    interferometer.decimation_filepath = "sample_data/Decimation_Comercial.csv"
    inversion = pti.Inversion(interferometer=interferometer, settings_path="sample_configs/settings.csv")
    inversion.load_response_phase()

    # Using the wrapper for pti inversion
    inversion.invert()
    print(inversion)

    # Using the API
    data = pd.read_csv("sample_data/Decimation_Comercial.csv")
    dc_signals = data[[f"DC CH{i}" for i in range(1, 4)]].to_numpy()
    inversion.lock_in.amplitude = data[[f"Lock In Amplitude CH{i}" for i in range(1, 4)]].to_numpy().T
    inversion.lock_in.phase = data[[f"Lock In Phase CH{i}" for i in range(1, 4)]].to_numpy().T

    interferometer.calculate_phase(dc_signals)
    inversion.calculate_sensitivity()
    inversion.calculate_pti_signal()
    print(inversion)
    os.remove("PTI_Inversion.csv")
