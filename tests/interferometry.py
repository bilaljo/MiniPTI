import minipti
import pandas as pd
import unittest
import numpy as np


class TestInterferometer(unittest.TestCase):
    MAX_ERROR_PHASE = 1e-6  # Corresponds to µV range
    MAX_ERROR_PARAMTERS = 1e-3

    def setUp(self):
        unittest.TestCase.__init__(self)
        self.characterisation = minipti.interferometry.Characterization()
        self.dc_data = None
        self.interferometry = minipti.interferometry.Interferometer()
        settings = "../examples/sample_configs/settings.csv"
        self.interferometry = minipti.interferometry.Interferometer(settings_path=settings)
        self.interferometry.init_settings()
        self.characterisation = minipti.interferometry.Characterization(interferometry=self.interferometry)
        self.interferometry.decimation_filepath = "../examples/sample_data/Decimation_Comercial.csv"
        data = pd.read_csv("../examples/sample_data/Decimation_Comercial.csv")
        self.dc_data = data[[f"DC CH{i}" for i in range(1, 4)]].to_numpy().T

    def reconstruct_signal(self, phases):
        signals = []
        amplitudes = self.characterisation.interferometry.amplitudes
        output_phases = self.characterisation.interferometry.output_phases
        offsets = self.characterisation.interferometry.offsets
        for i in range(3):
            signals.append(amplitudes[i] * np.cos(phases - output_phases[i]) + offsets[i])
        return signals

    def test_interferometer_parameters(self):
        self.characterisation.use_settings = False
        self.characterisation.iterate_characterization(self.dc_data)
        self.interferometry.calculate_phase(self.dc_data.T)
        settings = pd.read_csv("../examples/sample_configs/settings.csv", index_col="Setting")
        self.assertTrue((np.abs(settings.loc["Output Phases [deg]"]
                                - self.interferometry.output_phases) <
                         np.deg2rad(TestInterferometer.MAX_ERROR_PARAMTERS)).any())
        self.assertTrue((np.abs(settings.loc["Amplitude [V]"]
                                - self.interferometry.amplitudes) < TestInterferometer.MAX_ERROR_PARAMTERS).any())
        self.assertTrue((np.abs(settings.loc["Offset [V]"]
                                - self.interferometry.offsets) < TestInterferometer.MAX_ERROR_PARAMTERS).any())

    def test_interferometer_phase(self):
        self.interferometry.calculate_phase(self.dc_data.T)
        reconstructed_signal = self.reconstruct_signal(self.interferometry.phase)
        self.assertTrue((np.abs(reconstructed_signal - self.dc_data) < TestInterferometer.MAX_ERROR_PHASE).any())


if __name__ == "__main__":
    unittest.main()
