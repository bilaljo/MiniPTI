import itertools

import numpy as np
import pytest

import minipti

N = 10
phase_space = itertools.product([2 * np.pi / N * k for k in range(N)],
                                [2 * np.pi / N * k for k in range(N)])


@pytest.mark.parametrize("alpha", phase_space)
def test_calculate_output_phases(alpha) -> None:
    interferometer = minipti.algorithm.interferometry.Interferometer()
    characterization = minipti.algorithm.interferometry.Characterization(interferometer=interferometer,
                                                                         use_parameters=False,
                                                                         use_configuration=False)
    phases = np.linspace(0, 2 * np.pi, 100)
    output_phases = [0, alpha[0], alpha[1]]
    intensities = np.array([np.cos(phases - output_phases[i]) + 1 for i in range(3)]).T
    for _ in characterization.process(intensities):
        pass
    ideal_amplitudes = np.array([1, 1, 1])
    ideal_offsets = np.array([1, 1, 1])
    try:
        np.testing.assert_allclose(interferometer.output_phases, output_phases, 1e-4)
    except AssertionError:
        interferometer.output_phases[1:] = 2 * np.pi - np.array(interferometer.output_phases[1:])
        np.testing.assert_allclose(interferometer.output_phases, output_phases, 1e-4)
    np.testing.assert_allclose(interferometer.amplitudes, ideal_amplitudes, 1e-1)
    np.testing.assert_allclose(interferometer.offsets, ideal_offsets, 1e-1)
