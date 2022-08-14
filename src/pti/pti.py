import os

import numpy as np
import pandas as pd

from pti.decimation import Decimation
from pti.inversion import Inversion


class PTI:
    def __init__(self):
        self.decimation_first_call = True
        self.decimation = Decimation()
        self.inversion = Inversion()

    def __calculate_decimation(self):
        self.decimation.read_data()
        self.decimation.calculate_dc()
        self.decimation.common_mode_noise_reduction()
        self.decimation.lock_in_amplifier()
        ac, phase = self.decimation.get_lock_in_values()
        dc = self.decimation.dc_down_sampled
        pd.DataFrame({"AC CH1": ac[0], "AC Phase CH1": phase[0],
                      "AC CH2": ac[1], "AC Phase CH2": phase[1],
                      "AC CH3": ac[2], "AC Phase Phase CH3": phase[2],
                      "DC CH1": dc[0], "DC CH2": dc[1], "DC CH3": dc[2]},
                     index=[0]).to_csv("Decimation.csv", mode="a", header=not os.path.exists("Decimation.csv"))
        return ac, phase, dc

    def decimate(self, file_path):
        if os.path.exists("Decimation.csv"):
            os.remove("Decimation.csv")
        self.decimation.file = open(file_path, "rb")
        while not self.decimation.eof:
            self.__calculate_decimation()
        self.decimation.file.close()

    def phase_scan(self, decimation_path, inversion_path):
        pass

    def init_inversion(self, settings_path):
        settings = pd.read_csv(settings_path)
        self.inversion.output_phases = np.deg2rad(settings.loc["Output Phases"].to_numpy())
        self.inversion.response_phases = np.deg2rad(settings.loc["Response Phases"].to_numpy())
        self.inversion.min_intensities = settings.loc["Min Intensities"].to_numpy()
        self.inversion.max_intensities = settings.loc["Max Intensities"].to_numpy()

    def invert(self, file_path):
        data = pd.read_csv(file_path)
        dc_signals = np.array([data[f"DC CH{i}"] for i in range(1, 4)])
        ac_signals = np.array([data[f"AC CH{i}"] for i in range(1, 4)])
        lock_in_phase = np.array([data[f"Response Phase CH{i}"] for i in range(1, 4)])
        self.inversion.calculate_interferometric_phase(dc_signals.T)
        self.inversion.calculate_pti_signal(ac_signals, lock_in_phase)
        pd.DataFrame({"Interferometric Phase": self.inversion.interferometric_phase,
                      "PTI Signal": self.inversion.pti_signal}).to_csv("PTI_Inversion.csv")

    def pti(self, file_path_decimation, settings_path):
        if self.decimation_first_call:
            if os.path.exists("Decimation.csv"):
                os.remove("Decimation.csv")
            if os.path.exists("PTI_Inversion.csv"):
                os.remove("PTI_Inversion.csv")
            self.decimation.file = open(file_path_decimation, "rb")
        ac_signal, phase, dc_signal = self.__calculate_decimation()
        self.init_inversion(settings_path)
        self.inversion.calculate_interferometric_phase(dc_signal)
        self.inversion.calculate_pti_signal(ac_signal, phase)
        pd.DataFrame({"Interferometric Phase": self.inversion.interferometric_phase, "PTI Signal": self.inversion.pti},
                     index=[0]).to_csv("PTI_Inversion.csv", mode="a", header=not os.path.exists("PTI_Inversion.csv"))
