import pandas as pd

import minipti

if __name__ == "__main__":
    interferometer = minipti.interferometry.Interferometer(settings_path="sample_configs/settings.csv",
                                                           decimation_filepath="sample_data/Decimation_Comercial.csv")
    interferometer.init_settings()

    data = pd.read_csv("sample_data/Decimation_Comercial.csv")

    dc_signals = data[[f"DC CH{i}" for i in range(1, 4)]].to_numpy()

    interferometer.calculate_offsets(dc_signals)  # Estimate offsets
    interferometer.calculate_amplitudes(dc_signals)  # Estimate amplitudes
    interferometer.calculate_phase(dc_signals)
    print(interferometer.phase)
