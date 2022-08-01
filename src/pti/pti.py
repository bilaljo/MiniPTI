import os
import queue
import threading
import time

import numpy as np
import pandas as pd
from pti.decimation import Decimation
from pti.inversion import Inversion
from pti.phase_scan import PhaseScan


class PTI:
    def __init__(self):
        self.data = queue.Queue()
        self.decimation_thread = None
        self.pti_thread = None
        self.running = False
        self.settings_lock = threading.Lock()

    def decimate(self, file_path, mode):
        file_path = "280422.bin"
        decimation = Decimation()

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
                if not self.running:
                    break
                ac_signal, dc_signal, lock_in_phase = calculate_decimation()
                save_decimation(ac_signal, dc_signal, lock_in_phase)
                self.data.put((ac_signal, dc_signal, lock_in_phase))
                time.sleep(1)
                print(self.running)

    def phase_scan(self, decimation_path, inversion_path):
        phase_scan = PhaseScan(step_size=150)
        decimation_data = pd.read_csv(decimation_path)
        inversion_data = pd.read_csv(inversion_path)
        dc_signals = np.array([decimation_data[f"DC CH{i}"] for i in range(1, 4)])
        phases = inversion_data["Interferometric Phase"]
        phase_scan.create_graph()
        for i in range(len(phases)):
            phase_scan.add_phase(phases[i], i)
        while True:
            phase_scan.color_nodes()
            if not phase_scan.enough_values:
                break
            phase_scan.set_signals(np.take(dc_signals, phase_scan.colored_nodes, axis=1))
            phase_scan.set_phases(np.take(phases, phase_scan.colored_nodes, axis=1))
            phase_scan.set_min()
            phase_scan.set_max()
            phase_scan.scale_data()
            phase_scan.calulcate_output_phases()
            print(phase_scan.output_phases)
            pd.DataFrame({"Detector 2": phase_scan.output_phases[1],
                          "Detector 3": phase_scan.output_phases[2]},
                         index=[0]).to_csv("Output_Phases.csv", mode="a",
                                           header=not os.path.exists("Output_Phases.csv"))
            phase_scan.colored_nodes = []

    def invert(self, file_path, settings, mode):
        inversion = Inversion()
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
                if not self.running:
                    break
                ac_signal, dc_signal, lock_in_phase = self.data.get(block=True)
                inversion.calculate_interferometric_phase(dc_signal)
                inversion.calculate_pti_signal(ac_signal, lock_in_phase)
                pd.DataFrame({"Interferometric Phase": inversion.interferometric_phase,
                              "PTI Signal": inversion.pti},
                             index=[0]).to_csv("PTI_Inversion.csv", mode="a",
                                               header=not os.path.exists("PTI_Inversion.csv"))

    def run_live(self, file_path, settings):
        self.running = True
        self.decimation_thread = threading.Thread(target=self.decimate, args=[file_path, "Online"])
        self.pti_thread = threading.Thread(target=self.invert, args=["", settings, "Online"])
        self.decimation_thread.start()
        self.pti_thread.start()
