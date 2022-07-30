import csv
import multiprocessing
import threading
import time
import tkinter as tk
from collections import deque
from tkinter import filedialog
from tkinter import messagebox

import pandas as pd
from matplotlib import pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk

from gui.settings import Settings
from pti.decimation import Decimation
from pti.inversion import Inversion
from pti.phase_scan import PhaseScan
from pti.pti import PTI


class Action:
    def __init__(self, settings: Settings, dc_frame=None, phase_frame=None, pti_frame=None):
        self.file_path = {"Decimation": "data.bin", "Phase Scan": "Decimation.csv", "Inversion": "Decimation.csv"}
        self.decimation = Decimation()
        self.inversion = Inversion()
        self.phase_scan = PhaseScan()
        self.pti = PTI()
        self.pti_process = None
        self.frames = {"DC Signal": dc_frame, "Interferometric Phase": phase_frame, "PTI Signal": pti_frame}
        self.figs = {"DC Signal": None, "Interferometric Phase": None, "PTI Signal": None}
        self.axes = {"DC Signal": None, "Interferometric Phase": None, "PTI Signal": None}
        self.canvas = {"DC Signal": None, "Interferometric Phase": None, "PTI Signal": None}
        self.settings = settings
        self.live_path = ""
        self.decimation_data = None
        self.pti_data = None
        self.live_plot = None

    @staticmethod
    def on_close(root):
        def close():
            if messagebox.askokcancel("Quit", "Do you want to quit?"):
                root.destroy()

        return close

    def calculate_decimation(self):
        decimate_thread = threading.Thread(target=self.pti.decimate, daemon=True, args=(self.decimation,
                                                                                        self.file_path["Decimation"],
                                                                                        "Offline"))
        decimate_thread.start()

    def calculate_inversion(self):
        inversion_thread = threading.Thread(target=self.pti.invert, args=(self.inversion, self.file_path["Inversion"],
                                                                          self.settings.data, "Offline"), daemon=True)
        inversion_thread.start()

    def calculate_live(self):
        self.pti_process = multiprocessing.Process(target=self.pti.run_live, daemon=True,
                                                   args=(self.decimation, self.inversion,
                                                         self.live_path, self.settings.data))
        self.pti_process.start()

    # TODO: Kill Measurements

    def scan(self):
        pass

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
                messagebox.showwarning("File Path", "You have not specified any file path.")
            else:
                self.file_path[program] = file

        return decimation_path

    def set_live_path(self):
        self.live_path = filedialog.askdirectory(title="Directory for live measurements")

    @staticmethod
    def __plot_path(title):
        default_extension = "*.csv"
        file_types = (("CSV File", "*.csv"), ("Tab Separated File", "*.txt"), ("All Files", "*"))
        file_path = filedialog.askopenfilename(defaultextension=default_extension, filetypes=file_types,
                                               title=title)
        if not file_path:
            messagebox.showerror(title="Path Error", message="No path specified")
            return
        return file_path

    def __draw_plot(self, x_label, y_label, x_data, y_data, tab):
        self.axes[tab].cla()
        self.axes[tab].grid()
        self.axes[tab].set_xlabel(x_label, fontsize=11)
        self.axes[tab].set_ylabel(y_label, fontsize=11)
        if tab == "DC Signal":
            for channel in range(3):
                self.axes[tab].plot(x_data, y_data[f"DC CH{channel + 1}"], label=f"CH{channel + 1}")
                self.axes[tab].legend(fontsize=11)
        else:
            self.axes[tab].plot(x_data, y_data)
        self.canvas[tab].draw()

    def __setup_plots(self, tab):
        self.figs[tab], self.axes[tab] = plt.subplots()
        if tab == "DC Signal":
            self.axes[tab].plot([], [], label="CH1")
            self.axes[tab].plot([], [], label="CH2")
            self.axes[tab].plot([], [], label="CH3")
            self.axes[tab].legend(fontsize=11)
        else:
            self.axes[tab].plot([], [])
        self.canvas[tab] = FigureCanvasTkAgg(self.figs[tab], master=self.frames[tab])
        self.canvas[tab].draw()
        self.canvas[tab].get_tk_widget().pack()
        toolbar = NavigationToolbar2Tk(self.canvas[tab], self.frames[tab])
        toolbar.update()
        self.canvas[tab].get_tk_widget().pack(side=tk.TOP, fill=tk.BOTH, expand=1)

    def plot_dc(self):
        file_path = self.__plot_path("Inversion")
        if file_path is None:
            return
        data = pd.read_csv(file_path)
        self.__setup_plots(tab="DC Signal")
        self.__draw_plot(x_label="Time [s]", y_label="Intensity [V]", x_data=range(len(data)), y_data=data,
                         tab="DC Signal")

    def plot_inversion(self):
        file_path = self.__plot_path("Inversion")
        if file_path is None:
            return
        data = pd.read_csv(file_path)
        self.__setup_plots(tab="Interferometric Phase")
        self.__draw_plot(x_label="Time [s]", y_label=r"$\varphi$ [rad]", x_data=range(len(data)),
                         y_data=data["Interferometric Phase"], tab="Interferometric Phase")
        self.__setup_plots(tab="PTI Signal")
        self.__draw_plot(x_label="Time [s]", y_label=r"$\Delta\varphi$ [rad]", x_data=range(len(data)),
                         y_data=data["PTI Signal"], tab="PTI Signal")

    def plot_live(self):
        # FIXME: If the user switches at beginning to fast in the plottings tabe it will be blocked.
        self.__setup_plots(tab="DC Signal")
        self.__setup_plots(tab="Interferometric Phase")
        self.__setup_plots(tab="PTI Signal")
        dc_csv = None
        pti_csv = None
        try:
            while True:
                try:
                    dc_csv = open("Decimation.csv", "r")
                    decimation_data = csv.DictReader(dc_csv)
                except FileExistsError:
                    time.sleep(1)
                else:
                    break
            pti_csv = open("PTI_Inversion.csv", "r")
            pti_data = csv.DictReader(pti_csv)
            max_time = 1000
            time_live = deque(maxlen=max_time)
            dc_live = {"DC CH1": deque(maxlen=max_time), "DC CH2": deque(maxlen=max_time),
                       "DC CH3": deque(maxlen=max_time)}
            phase_live = deque(maxlen=max_time)
            pti_live = deque(maxlen=max_time)
            current_time = 0
            dc_added_data = 0
            pti_added_data = 0
            while True:
                for data in decimation_data:  # This should stop after one iteration if we are in sync.
                    dc_live["DC CH1"].append(float(data["DC CH1"]))
                    dc_live["DC CH2"].append(float(data["DC CH2"]))
                    dc_live["DC CH3"].append(float(data["DC CH3"]))
                    current_time += 1
                    time_live.append(current_time)
                    dc_added_data += 1
                for data in pti_data:
                    phase_live.append(float(data["Interferometric Phase"]))
                    pti_live.append(float(data["PTI Signal"]))
                    pti_added_data += 1
                while pti_added_data < dc_added_data:
                    try:
                        phase_live.append(float(next(pti_data)["Interferometric Phase"]))
                        pti_live.append(float(next(pti_data)["PTI Signal"]))
                        pti_added_data += 1
                    except StopIteration:
                        continue
                self.__draw_plot(x_label="Time [s]", y_label="Intensity [V]", x_data=time_live, y_data=dc_live,
                                 tab="DC Signal")
                self.__draw_plot(x_label="Time [s]", y_label=r"$\varphi$ [rad]", x_data=time_live, y_data=phase_live,
                                 tab="Interferometric Phase")
                self.__draw_plot(x_label="Time [s]", y_label=r"$\Delta\varphi$ [rad]", x_data=time_live,
                                 y_data=pti_live, tab="PTI Signal")
                time.sleep(1)
        finally:
            if dc_csv:
                dc_csv.close()
            if pti_csv:
                pti_csv.close()

    def live(self):
        self.calculate_live()
        self.live_plot = threading.Thread(target=self.plot_live, daemon=True)
        self.live_plot.start()
