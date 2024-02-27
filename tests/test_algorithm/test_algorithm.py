"""
Unit tests for Characterisation algorithm of an interferometer.
"""
import os
import pytest

import numpy as np
import pandas as pd

import minipti


class TestInterferometer:
    """
    Tests with sample data if the characteristic values of the interferometer fit the measured
    intensities well (according to a tolerance) enough.
    """
    MAX_ERROR_PHASE = 1e-9 * 2 * np.pi
    MAX_ERROR_PARAMETERS = 1e-6

    @pytest.fixture
    def setup(self):
        self.base_dir = f"{os.path.dirname(__file__)}/sample_data"
        settings = f"{self.base_dir}/settings.csv"
        self.interferometer = minipti.algorithm.interferometry.Interferometer(settings_path=settings)
        self.interferometer.load_settings()
        self.characterisation = minipti.algorithm.interferometry.Characterization(interferometer=self.interferometer)
        self.interferometer.decimation_filepath = f"{self.base_dir}/Decimation_Comercial.csv"
        data = pd.read_csv(self.interferometer.decimation_filepath)
        self.dc_data = data[[f"DC CH{i}" for i in range(1, 4)]].to_numpy().T
        self.characterisation.destination_folder = os.path.dirname(__file__)
        yield
        self.clean_up()

    def clean_up(self) -> None:
        data_path: str = f"{os.path.dirname(__file__)}"
        if os.path.exists(f"{data_path}/Characterisation.csv"):
            os.remove(f"{data_path}/Characterisation.csv")

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

    def test_interferometer_parameters(self, setup):
        """
        Tests for given fixed interferometric phase if the reconstruction is approximately
        equal to the measured intensities.
        """
        self.characterisation.process(self.dc_data)
        settings = pd.read_csv(f"{self.base_dir}/settings.csv", index_col="Setting")
        np.testing.assert_allclose(
            settings.loc["Output Phases [deg]"],
            np.rad2deg(self.interferometer.output_phases),
            TestInterferometer.MAX_ERROR_PARAMETERS
        )
        np.testing.assert_allclose(
            settings.loc["Output Phases [deg]"],
            np.rad2deg(self.interferometer.output_phases),
            TestInterferometer.MAX_ERROR_PARAMETERS
        )
        np.testing.assert_allclose(
            settings.loc["Amplitude [V]"],
            self.interferometer.amplitudes,
            TestInterferometer.MAX_ERROR_PARAMETERS
        )
        np.testing.assert_allclose(
            settings.loc["Amplitude [V]"],
            self.interferometer.amplitudes,
            TestInterferometer.MAX_ERROR_PARAMETERS
        )
        np.testing.assert_allclose(
            settings.loc["Offset [V]"],
            self.interferometer.offsets,
            TestInterferometer.MAX_ERROR_PARAMETERS
        )

    def test_interferometer_phase(self, setup):
        """
        Tests whereby given fixed characteristic parameters the interferometric phase can be
        correctly calculated, i.e. the signal reconstructed.
        """
        self.interferometer.intensities = self.dc_data.T
        self.interferometer.calculate_phase()
        reconstructed_signal = self._reconstruct_signal(self.interferometer.phase)
        np.testing.assert_array_almost_equal(
            np.mean((reconstructed_signal - self.dc_data) ** 2),
            0,
            3)


class TestCharacterisation:
    """
    Tests with sample data if the characteristic values of the interferometer fit the measured
    intensities well (according to a tolerance) enough.
    """
    @pytest.fixture
    def setup(self):
        self.base_dir = f"{os.path.dirname(__file__)}/sample_data/algorithm"
        self.interferometer = minipti.algorithm.interferometry.Interferometer()
        self.characterization = minipti.algorithm.interferometry.Characterization(interferometer=self.interferometer)
        self.phases = np.linspace(0, 2 * np.pi, 100)
        yield

    def test_parameters_non_ideal(self, setup) -> None:
        output_phases = np.array([0, 0.4, 0.7]) * 2 * np.pi
        self.intensities = np.array([np.cos(self.phases - output_phases[i]) + 1 for i in range(3)]).T
        for _ in self.characterization.process(self.intensities):
            pass
        ideal_amplitudes = np.array([1, 1, 1])
        ideal_offsets = np.array([1, 1, 1])
        try:
            np.testing.assert_allclose(self.interferometer.output_phases, output_phases, 1e-3)
        except AssertionError:
            self.interferometer.output_phases[1:] = 2 * np.pi - np.array(self.interferometer.output_phases[1:])
        np.testing.assert_allclose(self.interferometer.output_phases, output_phases, 1e-3)
        np.testing.assert_allclose(self.interferometer.amplitudes, ideal_amplitudes, 1e-3)
        np.testing.assert_allclose(self.interferometer.offsets, ideal_offsets, 1e-3)
