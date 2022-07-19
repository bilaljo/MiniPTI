import collections
import os
import tkinter as tk
from tkinter import filedialog
from tkinter import messagebox

import matplotlib.animation as animation
import numpy as np
import pandas as pd
from matplotlib import pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk

from settings import Settings


class Action:
    def __init__(self, decimation, inversion=None, phase_scan=None, dc_frame=None, phase_frame=None, pti_frame=None):
        self.file_path = {"Decimation": "data.bin", "Phase Scan": "Decimation.csv", "Inversion": "Decimation.csv"}
        self.mode = {"Decimation": "Offline", "Inversion": "Offline"}
        self.programs = {"Decimation": decimation, "Inversion": inversion, "Phase Scan": phase_scan}
        self.frames = {"DC Signal": dc_frame, "Interferometric Phase": phase_frame, "PTI Signal": pti_frame}
        self.pti_live_data = collections.deque(maxlen=1000)
        self.pti_live_time = collections.deque(maxlen=1000)

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
        data = pd.read_csv(self.file_path["Inversion"])
        dc_signals = np.array([data[f"DC CH{i}"] for i in range(1, 4)])
        ac_signals = np.array([data[f"RMS CH{i}"] for i in range(1, 4)])
        lock_in_phase = np.array([data[f"Response Phase CH{i}"] for i in range(1, 4)])
        inversion.output_phases = np.deg2rad(Settings.data.loc["Output Phases"].to_numpy())
        inversion.response_phases = np.deg2rad(Settings.data.loc["Response Phases"].to_numpy())
        inversion.min_intensities = Settings.data.loc["Min Intensities"].to_numpy()
        inversion.max_intensities = Settings.data.loc["Max Intensities"].to_numpy()
        inversion.calculate_interferometric_phase(dc_signals.T)
        inversion.calculate_pti_signal(ac_signals, lock_in_phase)
        pd.DataFrame({"Interferometric Phase": inversion.interferometric_phase,
                      "PTI Signal": inversion.pti}).to_csv("PTI_Inversion.csv")
        return inversion.pti, inversion.interferometric_phase

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
                file_types = (("CSV File", "*.csv"), ("Tab Separated File", "*.txt"), ("All Files", "*"))
            file = filedialog.askopenfilename(defaultextension=default_extension, filetypes=file_types,
                                              title=f"{program} File Path")
            if not file:
                messagebox.showwarning("File Path", "You have not specificed any file path.")
            else:
                self.file_path[program] = file

        return decimation_path

    def plot_decimation(self):
        default_extension = "*.csv"
        file_types = (("CSV File", "*.csv"), ("Tab Separated File", "*.txt"), ("All Files", "*"))
        file_dc = filedialog.askopenfilename(defaultextension=default_extension, filetypes=file_types,
                                             title=f"DC File Path")
        if not file_dc:
            messagebox.showerror(title="Path Error", message="No path specicifed")
            return

        def plot_dc():
            fig = plt.figure()
            data = pd.read_csv(file_dc)
            time = range(len(data["DC CH1"]))
            plt.plot(time, data["DC CH1"], label="CH1")
            plt.plot(time, data["DC CH2"], label="CH2")
            plt.plot(time, data["DC CH3"], label="CH3")
            plt.xlabel("Time in [s]", fontsize=11)
            plt.ylabel("Intensity [V]", fontsize=11)
            plt.grid()
            plt.legend(fontsize=11)

            canvas_dc = FigureCanvasTkAgg(fig, master=self.frames["DC Signal"])
            canvas_dc.draw()
            canvas_dc.get_tk_widget().pack()
            toolbar = NavigationToolbar2Tk(canvas_dc, self.frames["DC Signal"])
            toolbar.update()
            canvas_dc.get_tk_widget().pack(side=tk.TOP, fill=tk.BOTH, expand=1)

        plot_dc()

    def plot_inversion(self):
        default_extension = "*.csv"
        file_types = (("CSV File", "*.csv"), ("Tab Separated File", "*.txt"), ("All Files", "*"))
        file_pti = filedialog.askopenfilename(defaultextension=default_extension, filetypes=file_types,
                                              title=f"PTI File Path")
        if not file_pti:
            messagebox.showerror(title="Path Error", message="No path specicifed")
            return

        def plot_phase():
            fig_phase = plt.figure()
            data = pd.read_csv(file_pti)
            time = range(len(data["Interferometric Phase"]))
            plt.scatter(time, data["Interferometric Phase"], s=2)
            plt.xlabel("Time in [s]", fontsize=11)
            plt.ylabel(r"$\varphi$ [rad]", fontsize=12)
            plt.grid()

            canvas = FigureCanvasTkAgg(fig_phase, master=self.frames["Interferometric Phase"])
            canvas.draw()
            canvas.get_tk_widget().pack()
            toolbar = NavigationToolbar2Tk(canvas, self.frames["Interferometric Phase"])
            toolbar.update()
            canvas.get_tk_widget().pack(side=tk.TOP, fill=tk.BOTH, expand=1)

        def plot_pti():
            fig_pti = plt.figure()
            data = pd.read_csv(file_pti)
            time = range(len(data["PTI Signal"]))
            plt.scatter(time, data["PTI Signal"] * 1e6, s=2)
            plt.xlabel("Time in [s]", fontsize=11)
            plt.ylabel(r"$\Delta \varphi$ [$10^{-6}$ rad]", fontsize=11)
            plt.grid()

            canvas = FigureCanvasTkAgg(fig_pti, master=self.frames["PTI Signal"])
            canvas.draw()
            canvas.get_tk_widget().pack()
            toolbar = NavigationToolbar2Tk(canvas, self.frames["PTI Signal"])
            toolbar.update()
            canvas.get_tk_widget().pack(side=tk.TOP, fill=tk.BOTH, expand=1)

        plot_phase()
        plot_pti()

    def live_plotting(self, line):
        self.pti_live_data.append(self.invert()[self.time])
        self.time += 1
        self.pti_live_time.append(self.time)

        def update(i):
            line.set_xdata(self.pti_live_time)
            line.set_ydata(self.pti_live_data)
            return line,

        return update

    def live(self):
        fig, ax = plt.subplots()
        line, = ax.plot(self.pti_live_time, self.pti_live_data)
        ani = animation.FuncAnimation(fig, self.live_plotting(line), interval=500, blit=True)

        canvas = FigureCanvasTkAgg(fig, master=self.frames["PTI Signal"])
        canvas.draw()
        canvas.get_tk_widget().pack()
        toolbar = NavigationToolbar2Tk(canvas, self.frames["PTI Signal"])
        toolbar.update()
        canvas.get_tk_widget().pack(side=tk.TOP, fill=tk.BOTH, expand=1)
