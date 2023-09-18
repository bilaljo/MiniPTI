"""
Unit tests for Characterisation algorithm of an interferometer.
"""

import os
import unittest
import sys

import numpy as np
import pandas as pd

sys.path.extend(".")

import minipti


class TestInterferometer(unittest.TestCase):
    """
    Tests with sample data if the characteristic values of the interferometer fit the measured
    intensities well (according to a tolerance) enough.
    """
    MAX_ERROR_PHASE = 1e-6  # Corresponds to µV range
    MAX_ERROR_PARAMETERS = 1e-3

    def setUp(self):
        unittest.TestCase.__init__(self)
        self.base_dir = f"{os.path.dirname(__file__)}/sample_data/algorithm"
        settings = f"{self.base_dir}/settings.csv"
        self.interferometer = minipti.algorithm.interferometry.Interferometer(settings_path=settings)
        self.interferometer.load_settings()
        self.characterisation = minipti.algorithm.interferometry.Characterization(interferometer=self.interferometer)
        self.interferometer.decimation_filepath = f"{self.base_dir}/Decimation_Comercial.csv"
        data = pd.read_csv(self.interferometer.decimation_filepath)
        self.dc_data = data[[f"DC CH{i}" for i in range(1, 4)]].to_numpy().T
        self.characterisation.destination_folder = os.path.dirname(__file__)

    def _reconstruct_signal(self, phases):
        """
        Reconstructs the signal of given phases and characteristic parameters. The signal has
        always the form
        I(φ) = A * cos(φ - α) + B
        with amplitude A, phase φ, output phase α, Offset B and intensity I(φ). Given the
        characteristic parameters (A, B, α) and interferometric phase the intensity can be reconstructed
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
        Tests for given fixed interferometric phase if the reconstruction is approximately
        equal to the measured intensities.
        """
        self.characterisation.process(self.dc_data)
        settings = pd.read_csv(f"{self.base_dir}/settings.csv", index_col="Setting")
        self.assertTrue((np.abs(settings.loc["Output Phases [deg]"] - self.interferometer.output_phases)
                         < np.deg2rad(TestInterferometer.MAX_ERROR_PARAMETERS)).any())
        self.assertTrue((np.abs(settings.loc["Amplitude [V]"] - self.interferometer.amplitudes)
                         < TestInterferometer.MAX_ERROR_PARAMETERS).any())
        self.assertTrue((np.abs(settings.loc["Offset [V]"] - self.interferometer.offsets)
                         < TestInterferometer.MAX_ERROR_PARAMETERS).any())

    def test_interferometer_phase(self):
        """
        Tests whereby given fixed characteristic parameters the interferometric phase can be
        correctly calculated, i.e. the signal reconstructed.
        """
        self.interferometer.intensities = self.dc_data.T
        self.interferometer.calculate_phase()
        reconstructed_signal = self._reconstruct_signal(self.interferometer.phase)
        self.assertTrue((np.abs(reconstructed_signal - self.dc_data) < TestInterferometer.MAX_ERROR_PHASE).any())

    def tearDown(self) -> None:
        data_path: str = f"{os.path.dirname(__file__)}"
        if os.path.exists(f"{data_path}/Characterisation.csv"):
            os.remove(f"{data_path}/Characterisation.csv")


class TestCharacterisation(unittest.TestCase):
    """
    Tests with sample data if the characteristic values of the interferometer fit the measured
    intensities well (according to a tolerance) enough.
    """
    MAX_ERROR_PARAMETERS = 1e-3

    def setUp(self):
        unittest.TestCase.__init__(self)
        self.base_dir = f"{os.path.dirname(__file__)}/sample_data/algorithm"
        self.interferometer = minipti.algorithm.interferometry.Interferometer()
        self.characterization = minipti.algorithm.interferometry.Characterization(interferometer=self.interferometer,
                                                                                  use_parameters=False,
                                                                                  use_configuration=False)
        phases = np.linspace(0, 2 * np.pi, 1000)
        self.intensities = np.array([np.cos(phases - i * 2 * np.pi / 3) for i in range(3)]).T

    def test_parameters(self) -> None:
        for _ in self.characterization.process(self.intensities):
            pass
        self.assertTrue((np.abs(self.interferometer.output_phases - np.array([0, 2 * np.pi / 3, 4 * np.pi / 3]))
                         < TestInterferometer.MAX_ERROR_PHASE).any())


if __name__ == "__main__":
    unittest.main()
