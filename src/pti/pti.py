import os
import queue
import threading
import time

import numpy as np
import pandas as pd


class PTI:
    def __init__(self):
        self.data = queue.Queue()
        self.decimation_thread = None
        self.pti_thread = None

    def decimate(self, decimation, file_path, mode):
        file_path = "280422.bin"

        def calculate_decimation():
            decimation.read_data()
            decimation.calculate_dc()
            decimation.common_mode_noise_reduction()
            decimation.lock_in_amplifier()
            ac, response_phase = decimation.get_lock_in_values()
            dc = decimation.dc_down_sampled
            return ac, dc, response_phase

        def save_decimation(ac, dc, response_phase):
            pd.DataFrame({"AC CH1": ac[0], "Response Phase CH1": response_phase[0],
                          "AC CH2": ac[1], "Response Phase CH2": response_phase[1],
                          "AC CH3": ac[2], "Response Phase CH3": response_phase[2],
                          "DC CH1": dc[0], "DC CH2": dc[1], "DC CH3": dc[2]},
                         index=[0]).to_csv("Decimation.csv", mode="a", header=not os.path.exists("Decimation.csv"))

        if os.path.exists("Decimation.csv"):
            os.remove("Decimation.csv")
        if mode == "Offline":
            decimation.file = open(file_path, "rb")
            while not decimation.eof:
                ac_signal, dc_signal, lock_in_phase = calculate_decimation()
                save_decimation(ac_signal, dc_signal, lock_in_phase)
            decimation.file.close()
        else:
            decimation.file = open(file_path, "rb")
            if os.path.exists("Decimation.csv"):
                os.remove("Decimation.csv")
            while True:
                ac_signal, dc_signal, lock_in_phase = calculate_decimation()
                save_decimation(ac_signal, dc_signal, lock_in_phase)
                self.data.put((ac_signal, dc_signal, lock_in_phase))
                time.sleep(1)

    def invert(self, inversion, file_path, settings, mode):
        inversion.output_phases = np.deg2rad(settings.loc["Output Phases"].to_numpy())
        inversion.response_phases = np.deg2rad(settings.loc["Response Phases"].to_numpy())
        inversion.min_intensities = settings.loc["Min Intensities"].to_numpy()
        inversion.max_intensities = settings.loc["Max Intensities"].to_numpy()
        if os.path.exists("PTI_Inversion.csv"):
            os.remove("PTI_Inversion.csv")
        if mode == "Offline":
            data = pd.read_csv(file_path)
            dc_signals = np.array([data[f"DC CH{i}"] for i in range(1, 4)])
            ac_signals = np.array([data[f"AC CH{i}"] for i in range(1, 4)])
            lock_in_phase = np.array([data[f"Response Phase CH{i}"] for i in range(1, 4)])
            inversion.calculate_interferometric_phase(dc_signals.T)
            inversion.calculate_pti_signal(ac_signals, lock_in_phase)
            pd.DataFrame({"Interferometric Phase": inversion.interferometric_phase,
                          "PTI Signal": inversion.pti}).to_csv("PTI_Inversion.csv")
        else:
            while True:
                ac_signal, dc_signal, lock_in_phase = self.data.get(block=True)
                inversion.calculate_interferometric_phase(dc_signal)
                inversion.calculate_pti_signal(ac_signal, lock_in_phase)
                pd.DataFrame({"Interferometric Phase": inversion.interferometric_phase,
                              "PTI Signal": inversion.pti},
                             index=[0]).to_csv("PTI_Inversion.csv", mode="a",
                                               header=not os.path.exists("PTI_Inversion.csv"))

    def run_live(self, decimation, inversion, file_path, settings):
        self.decimation_thread = threading.Thread(target=self.decimate, args=[decimation, file_path, "Online"])
        self.pti_thread = threading.Thread(target=self.invert, args=[inversion, None, settings, "Online"])
        self.decimation_thread.start()
        self.pti_thread.start()
