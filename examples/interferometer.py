"""
Example file for the usage of the interferometry API of the MiniPTI.
"""

import pandas as pd

from minipti.algorithm import interferometry


if __name__ == "__main__":
    interferometer = interferometry.Interferometer(settings_path="sample_configs/settings.csv",
                                                   decimation_filepath="sample_data/Decimation_Comercial.csv")
    interferometer.load_settings()

    data = pd.read_csv("sample_data/Decimation_Comercial.csv")

    dc_signals = data[[f"DC CH{i}" for i in range(1, 4)]].to_numpy()

    interferometer.calculate_phase(dc_signals)
    print(interferometer.phase)
