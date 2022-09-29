import os
import platform
import threading

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
        self.characterisation = InterferometerCharaterisation(step_size=100)
        self.running = False
        self.characterisation_thread = threading.Thread()
        self.characterise_event = threading.Event()
        self.paramter_lock = threading.Lock()

    def __calculate_decimation(self, destination_folder="./"):
        self.decimation.read_data()
        self.decimation.calculate_dc()
        self.decimation.common_mode_noise_reduction()
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

    def init_inversion(self, settings_path):
        settings = pd.read_csv(settings_path, index_col="Setting")
        self.inversion.output_phases = np.deg2rad(settings.loc["Output Phases [deg]"].to_numpy())
        self.inversion.response_phases = np.deg2rad(settings.loc["Response Phases [deg]"].to_numpy())
        self.inversion.amplitude = (settings.loc["Amplitude [V]"]).to_numpy()
        self.inversion.offset = (settings.loc["Offset [V]"].to_numpy())

    def invert(self, file_path, recalulcation=False):
        data = pd.read_csv(file_path)
        dc_signals = data[[f"DC CH{i}" for i in range(1, 4)]].to_numpy()
        ac_signals = data[[f"AC CH{i}" for i in range(1, 4)]].to_numpy().T
        ac_phases = data[[f"AC Phase CH{i}" for i in range(1, 4)]].to_numpy().T
        self.inversion.calculate_offset(dc_signals)
        self.inversion.calculate_amplitude(dc_signals)
        self.inversion.calculate_interferometric_phase(dc_signals)
        self.inversion.calculate_pti_signal(ac_signals, ac_phases)
        pd.DataFrame({"Interferometric Phase": self.inversion.interferometric_phase,
                      "PTI Signal": self.inversion.pti_signal}).to_csv("PTI_Inversion.csv")

    def calculcate_characterisation(self, dc_path, pti_path, settings_path):
        dc_data = pd.read_csv(dc_path)
        dc_signals = dc_data[[f"DC CH{i}" for i in range(1, 4)]].to_numpy()
        pti_data = pd.read_csv(pti_path)
        settings = pd.read_csv(settings_path, index_col="Setting")
        self.characterisation.output_phases = np.deg2rad(settings.loc["Output Phases [deg]"].to_numpy())
        self.characterisation.amplitude = (settings.loc["Amplitude [V]"]).to_numpy()
        self.characterisation.offset = (settings.loc["Offset [V]"].to_numpy())
        output_phases = []
        amplitudes = []
        offsets = []
        last_index = 0
        for i in range(len(pti_data)):
            self.characterisation.phases.append(pti_data["Interferometric Phase"])
            if self.characterisation.check_enough_values():
                self.characterisation.set_signals(dc_signals[last_index:i + 1].T)
                self.characterisation.characterise_interferometer()
                output_phases.append(self.characterisation.output_phases)
                amplitudes.append(self.characterisation.amplitude)
                offsets.append(self.characterisation.offset)
                self.characterisation.phases = []
                last_index = i + 1
        characterised_data = {}
        for channel in range(1, 4):
            characterised_data[f"Output Phase CH{channel} [rad]"] = output_phases[channel]
            characterised_data[f"Amplitude CH{channel} [V]"] = amplitudes[channel]
            characterised_data[f"Offset CH{channel} [V]"] = offsets[channel]
        pd.DataFrame(characterised_data).to_csv("Characterisation.csv")

    def characterise(self):
        while True:
            self.characterise_event.wait()
            self.characterisation.characterise_interferometer()
            self.paramter_lock.acquire()
            self.inversion.amplitude = self.characterisation.amplitude
            self.inversion.offset = self.characterisation.offset
            self.inversion.output_phases = self.characterisation.output_phases
            self.paramter_lock.release()
            characterised_data = {}
            for channel in range(1, 4):
                characterised_data[f"Output Phase CH{channel} [rad]"] = self.characterisation.output_phases[channel]
                characterised_data[f"Amplitude CH{channel} [V]"] = self.characterisation.amplitude[channel]
                characterised_data[f"Offset CH{channel} [V]"] = self.characterisation.offset[channel]
            pd.DataFrame(characterised_data, index=[0]).to_csv("Characterisation.csv", mode="a",
                                                               header=not os.path.exists("Characterisation.csv"))
            self.characterise_event.clear()

    def pti(self, file_path_decimation, settings_path, destination_directory):
        if self.decimation_first_call:
            if os.path.exists("Decimation.csv"):
                os.remove("Decimation.csv")
            if os.path.exists("PTI_Inversion.csv"):
                os.remove("PTI_Inversion.csv")
            self.decimation.file = open(file_path_decimation, "rb")
            self.characterisation_thread = threading.Thread(target=self.characterise)
            self.characterisation_thread.start()
        if platform.system() == "Windows":
            destination_directory += ".\\"
        else:
            destination_directory += "./"
        self.decimation_first_call = False
        ac_signal, phase, dc_signal = self.__calculate_decimation(destination_directory)
        self.init_inversion(settings_path)
        self.inversion.calculate_interferometric_phase(dc_signal)
        self.paramter_lock.acquire()  # During PTI calculation the actual paramters shouldn't change.
        self.inversion.calculate_pti_signal(ac_signal, phase)
        self.paramter_lock.release()
        self.characterisation.phases.append(self.inversion.interferometric_phase)
        if self.characterisation.check_enough_values():
            self.characterise_event.set()
        pd.DataFrame({"Interferometric Phase": self.inversion.interferometric_phase,
                      "PTI Signal": self.inversion.pti_signal},
                     index=[0]).to_csv(destination_directory + "PTI_Inversion.csv", mode="a",
                                       header=not os.path.exists(destination_directory + "PTI_Inversion.csv"))
