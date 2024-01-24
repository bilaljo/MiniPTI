"""
Example file for the usage of the inversion algorithm of the MiniPTI.
"""
import os
import sys

import pandas as pd

sys.path.extend(".")
from minipti.algorithm import interferometry, pti


if __name__ == "__main__":
    base_path = f"{os.path.dirname(__file__)}"
    interferometer = interferometry.Interferometer(settings_path=f"{base_path}/sample_configs/settings.csv")
    interferometer.load_settings()
    interferometer.decimation_filepath = f"{base_path}/sample_data/Decimation_Comercial.csv"
    inversion = pti.Inversion(
        interferometer=interferometer,
        settings_path=f"{base_path}/sample_configs/settings.csv"
    )
    inversion.load_response_phase()

    # Using the wrapper for pti inversion
    inversion.run(file_path=f"{base_path}/sample_data/Decimation_Comercial.csv")
    print(inversion)

    # Using the API
    data = pd.read_csv(f"{base_path}/sample_data/Decimation_Comercial.csv")
    interferometer.intensities = data[[f"DC CH{i}" for i in range(1, 4)]].to_numpy()
    inversion.decimation.lock_in.amplitude = data[[f"Lock In Amplitude CH{i}" for i in range(1, 4)]].to_numpy().T
    inversion.decimation.lock_in.phase = data[[f"Lock In Phase CH{i}" for i in range(1, 4)]].to_numpy().T
    inversion.run(live=False)
    print(inversion)
    os.remove("Offline_PTI_Inversion.csv")
    os.remove("Offline_Interferometer.csv")
