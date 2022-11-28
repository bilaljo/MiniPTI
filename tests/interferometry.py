import minipti
import pandas as pd
import numpy as np


class InterferometerTest:
    interferometry = minipti.interferometry.Interferometer(settings_path="../examples/sample_configs/settings.csv")
    interferometry.init_settings()
    characterisation = minipti.interferometry.Characterization(interferometry=interferometry)
    interferometry.decimation_filepath = "../examples/sample_data/Decimation_Comercial.csv"
    data = pd.read_csv("../examples/sample_data/Decimation_Comercial.csv")
    dc_data = data[[f"DC CH{i}" for i in range(1, 4)]].to_numpy().T

    @staticmethod
    def interferometer_parameters():
        InterferometerTest.characterisation.characterise_interferometer()
        InterferometerTest.interferometry.calculate_phase(InterferometerTest.dc_data)
        amplitudes = InterferometerTest.interferometry.amplitudes
        output_phases = InterferometerTest.interferometry.output_phases
        offsets = InterferometerTest.interferometry.offsets
        calculated_dc = amplitudes * np.cos(InterferometerTest.interferometry.phase - output_phases) + offsets
        np.testing.assert_allclose(calculated_dc, InterferometerTest.dc_data, rtol=1e-6, atol=0)


def interferometer_phase():
    InterferometerTest.interferometry.calculate_phase(InterferometerTest.dc_data)
    amplitudes = InterferometerTest.interferometry.amplitudes
    output_phases = InterferometerTest.interferometry.output_phases
    offsets = InterferometerTest.interferometry.offsets
    calculated_dc = amplitudes * np.cos(InterferometerTest.interferometry.phase - output_phases) + offsets
    np.testing.assert_allclose(calculated_dc, InterferometerTest.dc_data, rtol=1e-6, atol=0)
