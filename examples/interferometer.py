"""
Example file for the usage of the interferometry API of the MiniPTI.
"""

import pandas as pd

import sys
sys.path.extend(".")
from minipti.algorithm import interferometry


if __name__ == "__main__":
    interferometer = interferometry.Interferometer(settings_path="examples/sample_configs/algorithm_settings.csv",
                                                   decimation_filepath="examples/sample_data/Decimation_Comercial.csv")
    interferometer.load_settings()

    data = pd.read_csv("examples/sample_data/Decimation_Comercial.csv")

    dc_signals = data[[f"DC CH{i}" for i in range(1, 4)]].to_numpy()

    interferometer.calculate_phase(dc_signals)
    print(interferometer.phase)
