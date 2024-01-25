import os
import sys

import pandas as pd
import numpy as np
import copy

sys.path.append(".")

import minipti


class TestSettingsTable:
    settings_table = minipti.gui.model.processing.SettingsTable()
    calculation = minipti.gui.model.processing.OfflineCalculation()
    BASE_DIR = f"{os.path.dirname(__file__)}/sample_data"

    def test_lock_in_phase_update(self) -> None:
        old_settings = copy.deepcopy(
            TestSettingsTable.settings_table.table_data
        )
        decimation_path = TestSettingsTable.BASE_DIR + "/Decimation_Comercial.csv"
        old_response_phases = copy.deepcopy(
            TestSettingsTable.calculation.pti.inversion.response_phases
        )
        TestSettingsTable.calculation.calculate_response_phases(decimation_path)
        new_response_phases = copy.deepcopy(
            TestSettingsTable.calculation.pti.inversion.response_phases
        )
        assert np.any(np.not_equal(old_response_phases, new_response_phases))
        new_settings = copy.deepcopy(
            TestSettingsTable.settings_table.table_data
        )
        response_phases = TestSettingsTable.calculation.pti.inversion.response_phases
        np.testing.assert_array_equal(
            new_settings.loc["Response Phases [rad]"].to_numpy(),
            response_phases
        )
        pd.testing.assert_frame_equal(old_settings.drop(["Response Phases [rad]"]),
                                      new_settings.drop(["Response Phases [rad]"]))
