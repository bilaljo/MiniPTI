import os
import platform

import numpy as np
import pandas as pd

from pti.decimation import Decimation
from pti.interferometer_charaterisation import InterferometerCharaterisation
from pti.inversion import Inversion


class PTI:
    def __init__(self):
        self.decimation_first_call = True
        self.decimation = Decimation()
        self.inversion = Inversion()
        self.interferometer_characterisation = InterferometerCharaterisation(step_size=100)

    def __calculate_decimation(self, destination_folder="./"):
        self.decimation.read_data()
        self.decimation.calculate_dc()
        #self.decimation.common_mode_noise_reduction()
        self.decimation.lock_in_amplifier()
        ac, phase = self.decimation.get_lock_in_values()
        dc = self.decimation.dc_down_sampled
        pd.DataFrame({"AC CH1": ac[0], "AC Phase CH1": phase[0],
                      "AC CH2": ac[1], "AC Phase CH2": phase[1],
                      "AC CH3": ac[2], "AC Phase CH3": phase[2],
                      "DC CH1": dc[0], "DC CH2": dc[1], "DC CH3": dc[2]},
                     index=[0]).to_csv(destination_folder + "Decimation.csv", mode="a",
                                       header=not os.path.exists(destination_folder + "Decimation.csv"))
        return ac, phase, dc

    def decimate(self, file_path, destination_folder="./"):
        if os.path.exists("Decimation.csv"):
            os.remove("Decimation.csv")
        self.decimation.file = open(file_path, "rb")
        while not self.decimation.eof:
            self.__calculate_decimation(destination_folder)
        self.decimation.file.close()

    def characterise(self, dc_signals_path):
        data = pd.read_csv(dc_signals_path)
        dc_signals = np.array([data[f"DC CH{i}"] for i in range(1, 4)])
        self.interferometer_characterisation.set_signals(dc_signals)
        self.interferometer_characterisation.set_amplitude()
        self.interferometer_characterisation.set_offset()
        self.inversion.set_amplitude(dc_signals)
        self.inversion.set_offset(dc_signals)
        self.inversion.calculate_interferometric_phase(dc_signals)
        self.interferometer_characterisation.set_phases(self.inversion.interferometric_phase)
        self.interferometer_characterisation.characterise_interferometer()

    def init_inversion(self, settings_path):
        settings = pd.read_csv(settings_path, index_col="Setting")
        self.inversion.output_phases = np.deg2rad(settings.loc["Output Phases [deg]"].to_numpy())
        self.inversion.response_phases = np.deg2rad(settings.loc["Response Phases [deg]"].to_numpy())
        self.inversion.amplitude = (settings.loc["Amplitude [V]"]).to_numpy()
        self.inversion.offset = (settings.loc["Offset [V]"].to_numpy())

    def invert(self, file_path):
        data = pd.read_csv(file_path)
        dc_signals = np.array([data[f"DC CH{i}"] for i in range(1, 4)])
        ac_signals = np.array([data[f"AC CH{i}"] for i in range(1, 4)])
        lock_in_phase = np.array([data[f"AC Phase CH{i}"] for i in range(1, 4)])
        self.inversion.calculate_interferometric_phase(dc_signals)
        self.inversion.calculate_pti_signal(ac_signals, lock_in_phase)
        pd.DataFrame({"Interferometric Phase": self.inversion.interferometric_phase,
                      "PTI Signal": self.inversion.pti_signal}).to_csv("PTI_Inversion.csv")

    def pti(self, file_path_decimation, settings_path, destination_directory):
        if self.decimation_first_call:
            if os.path.exists("Decimation.csv"):
                os.remove("Decimation.csv")
            if os.path.exists("PTI_Inversion.csv"):
                os.remove("PTI_Inversion.csv")
            self.decimation.file = open(file_path_decimation, "rb")
        if platform.system() == "Windows":
            destination_directory += "\\"
        else:
            destination_directory += "/"
        self.decimation_first_call = False
        ac_signal, phase, dc_signal = self.__calculate_decimation(destination_directory)
        self.init_inversion(settings_path)
        self.inversion.calculate_interferometric_phase(dc_signal)
        self.inversion.calculate_pti_signal(ac_signal, phase)
        pd.DataFrame({"Interferometric Phase": self.inversion.interferometric_phase,
                      "PTI Signal": self.inversion.pti_signal},
                     index=[0]).to_csv(destination_directory + "PTI_Inversion.csv", mode="a",
                                       header=not os.path.exists(destination_directory + "PTI_Inversion.csv"))
