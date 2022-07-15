import os
from tkinter import filedialog
from tkinter import messagebox

import numpy as np
import pandas as pd


class Action:
    def __init__(self, decimation, inversion=None, phase_scan=None):
        self.file_path = {"Decimation": "data.bin", "Phase Scan": "Decimation.csv", "Inversion": "Decimation.csv"}
        self.mode = {"Decimation": "Offline", "Inversion": "Offline"}
        self.programs = {"Decimation": decimation, "Inversion": inversion, "Phase Scan": phase_scan}

    def set_mode(self, mode):
        self.mode = mode

    def decimate(self):
        decimation = self.programs["Decimation"]
        decimation.file = open(self.file_path["Decimation"], "rb")
        if self.mode["Decimation"] == "Offline":
            if os.path.exists("Decimation.csv"):
                os.remove("Decimation.csv")
        while not decimation.eof:
            decimation.read_data()
            decimation.calucalte_dc()
            decimation.common_mode_noise_reduction()
            decimation.lock_in_amplifier()
            ac, response_phase = decimation.get_lock_in_values()
            dc = decimation.dc_down_sampled
            pd.DataFrame({"AC CH1": ac[0], "Response Phase CH1": response_phase[0],
                          "AC CH2": ac[1], "Response Phase CH2": response_phase[1],
                          "AC CH3": ac[2], "Response Phase CH3": response_phase[2],
                          "DC CH1": dc[0], "DC CH2": dc[1], "DC CH3": dc[2]},
                         index=[0]).to_csv("Decimation.csv", mode="a", header=not os.path.exists("Decimation.csv"))
        if self.mode["Decimation"] == "Offline":
            decimation.file.close()

    def invert(self):
        inversion = self.programs["Inversion"]
        data = pd.read_csv(self.file_path["Decimation"])
        dc_signals = np.array([data[f"DC CH{i}"] for i in range(1, 4)])
        ac_signals = np.array([data[f"RMS CH{i}"] for i in range(1, 4)])
        lock_in_phase = np.array([data[f"Response Phase CH{i}"] for i in range(1, 4)])
        inversion.set_signals(dc_signals)
        inversion.scale_data()
        interferometric_phase = inversion.get_interferometric_phase()
        inversion.calculate_pti_signal(ac_signals, lock_in_phase)
        pd.DataFrame({"Interferometric Phase": interferometric_phase,
                      "PTI Signal": inversion.pti}).to_csv("PTI_Inversion.csv")

    def scan(self):
        phase_scan = self.programs["Phase Scan"]
        data = pd.read_csv(self.file_path["Decimation"])
        dc_signals = np.array([data[f"DC CH{i}"] for i in range(1, 4)])
        phase_scan.set_data(dc_signals)
        phase_scan.set_min()
        phase_scan.set_max()
        phase_scan.scale_data()
        phase_scan.calulcate_output_phases()

    def set_file_path(self, program):
        def decimation_path():
            if program == "Decimation":
                default_extension = "*.bin"
                file_types = (("Binary File", "*.bin"), ("All Files", "*"))
            else:
                default_extension = "*.csv"
                file_types = (("CSV File", "*.cvv"), ("Tab Separated File", "*.txt"), ("All Files", "*"))
            file = filedialog.askopenfilename(defaultextension=default_extension, filetypes=file_types,
                                              title=f"{program} File Path")
            if not file:
                messagebox.showwarning("File Path", "You have not specificed any file path.")
            else:
                self.file_path[program] = file
        return decimation_path
