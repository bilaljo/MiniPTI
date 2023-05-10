"""
Unit tests for Characterisation algorithm of an interferometer.
"""

import os
import unittest

import numpy as np
import pandas as pd

import minipti


class TestInterferometer(unittest.TestCase):
    """
    Tests with sample data if the characteristic values of the interferometer fit the the measured
    intensities well (according to a tolerance) enough.
    """
    MAX_ERROR_PHASE = 1e-6  # Corresponds to µV range
    MAX_ERROR_PARAMETERS = 1e-3

    def setUp(self):
        unittest.TestCase.__init__(self)
        self.base_dir = f"{os.path.dirname(__file__)}/sample_data/algorithm"
        settings = f"{self.base_dir}/settings.csv"
        self.interferometry = minipti.algorithm.interferometry.Interferometer(
            settings_path=settings)
        self.interferometry.load_settings()
        self.characterisation = minipti.algorithm.interferometry.Characterization(
            interferometer=self.interferometry)
        self.interferometry.decimation_filepath = f"{self.base_dir}/Decimation_Comercial.csv"
        data = pd.read_csv(self.interferometry.decimation_filepath)
        self.dc_data = data[[f"DC CH{i}" for i in range(1, 4)]].to_numpy().T
        self.characterisation.destination_folder = os.path.dirname(__file__)

    def _reconstruct_signal(self, phases):
        """
        Reconstructs the signal of given phases and characteristic parameters. The signal has
        always the form
        I(φ) = A * cos(φ - α) + B
        with amplitude A, phase φ, output phase α, Offset B and intensity I(φ). Given the
        characteric parameters (A, B, α) and interferometric phase the intensity can be reonstructed
        according to this formula.
        """
        signals = []
        amplitudes = self.characterisation.interferometer.amplitudes
        output_phases = self.characterisation.interferometer.output_phases
        offsets = self.characterisation.interferometer.offsets
        for i in range(3):
            signals.append(amplitudes[i] * np.cos(phases - output_phases[i]) + offsets[i])
        return np.array(signals)

    def test_interferometer_parameters(self):
        """
        Tests for given fixed interferometric phase if the reconstruction is approximatly
        equal to the measured intensities.
        """
        self.characterisation.use_settings = False
        self.characterisation._signals = self.dc_data
        self.characterisation(live=False)
        self.interferometry.calculate_phase(self.dc_data.T)
        settings = pd.read_csv(f"{self.base_dir}/settings.csv", index_col="Setting")
        self.assertTrue((np.abs(settings.loc["Output Phases [deg]"]
                                - self.interferometry.output_phases)
                         < np.deg2rad(TestInterferometer.MAX_ERROR_PARAMETERS)).any())
        self.assertTrue((np.abs(settings.loc["Amplitude [V]"]
                                - self.interferometry.amplitudes)
                         < TestInterferometer.MAX_ERROR_PARAMETERS).any())
        self.assertTrue((np.abs(settings.loc["Offset [V]"]
                                - self.interferometry.offsets)
                         < TestInterferometer.MAX_ERROR_PARAMETERS).any())

    def test_interferometer_phase(self):
        """
        Tests whethere by given fixed characteristic parameters the interferometric phase can be
        correctly calculaed, i.e. the signal reconstructed.
        """
        self.interferometry.calculate_phase(self.dc_data.T)
        reconstructed_signal = self._reconstruct_signal(self.interferometry.phase)
        self.assertTrue((np.abs(
            reconstructed_signal - self.dc_data) < TestInterferometer.MAX_ERROR_PHASE).any())

    def tearDown(self) -> None:
        data_path: str = f"{os.path.dirname(__file__)}"
        if os.path.exists(f"{data_path}/Characterisation.csv"):
            os.remove(f"{data_path}/Characterisation.csv")


if __name__ == "__main__":
    unittest.main()
