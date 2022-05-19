import tkinter.messagebox
from tkinter import filedialog
from Plotting import Plotting
from tkinter import simpledialog
import pti
import numpy as np
import pandas as pd


class SubMenu:
    def __init__(self, window, menu_name, program, parameters=""):
        self.window = window
        self.menu_name = menu_name
        self.file = ""
        self.program = program
        self.parameters = parameters
        self.response_phases = {"Detector 1": 0.0, "Detector 2": 0.0, "Detector 3": 0.0}
        self.plotting = Plotting(main_window=self.window.root)

    response_phases = dict()

    def add_menu_options(self, menu_name, label, command):
        self.window.menus[menu_name].add_command(label=label, command=command)

    def file_dialog(self):
        filetypes = (('csv files', '*.csv'), ('binary files', '*.bin'), ('text files (tab separated)', '*.txt'),
                     ('All files', '*.*'))
        file_name = filedialog.askopenfilenames(filetypes=filetypes)
        if file_name:
            self.file = file_name[0]

    def set_response_phases_1(self):
        SubMenu.response_phases["Detector 1"] = simpledialog.askfloat(f"Response Phases", "Detector 1",
                                                                   parent=self.window.root)

    def set_response_phases_2(self):
        if pti.PhaseScan.swapp_channels:
            SubMenu.response_phases["Detector 2"] = simpledialog.askfloat("Response Phases", "Detector 3",
                                                                       parent=self.window.root)
        else:
            SubMenu.response_phases["Detector 2"] = simpledialog.askfloat("Response Phases", "Detector 2",
                                                                       parent=self.window.root)

    def set_response_phases_3(self):
        if pti.PhaseScan.swapp_channels:
            SubMenu.response_phases["Detector 3"] = simpledialog.askfloat("Response Phases", "Detector 2",
                                                                          parent=self.window.root)
        else:
            SubMenu.response_phases["Detector 3"] = simpledialog.askfloat("Response Phases", "Detector 3",
                                                                          parent=self.window.root)

    @staticmethod
    def display_output_phases():
        if pti.PhaseScan.swapp_channels:
            tkinter.messagebox.showinfo(title="Output Phases", message=f"Detector 1: {round(pti.PhaseScan.output_phases[0] / np.pi * 180, 5)}°\n \
                                                                         Detector 2: {round(pti.PhaseScan.output_phases[2] / np.pi * 180, 5)}°\n \
                                                                         Detector 3: {round(pti.PhaseScan.output_phases[1] / np.pi * 180, 5)}°")
        else:
            tkinter.messagebox.showinfo(title="Output Phases", message=f"Detector 1: {round(pti.PhaseScan.output_phases[0] / np.pi * 180, 5)}°\n \
                                                                        Detector 2: {round(pti.PhaseScan.output_phases[1] / np.pi * 180, 5)}°\n \
                                                                        Detector 3: {round(pti.PhaseScan.output_phases[2] / np.pi * 180, 5)}°\n")

    @staticmethod
    def display_contrasts():
        contrasts = []
        for channel in range(3):
            contrasts.append((pti.PhaseScan.max_intensities[channel] - pti.PhaseScan.min_intensities[channel]) /
                             (pti.PhaseScan.max_intensities[channel] + pti.PhaseScan.min_intensities[channel]) * 100)
        if pti.PhaseScan.swapp_channels:
            tkinter.messagebox.showinfo(title="Constrasts", message=f"Detector 1: {round(contrasts[0], 5)} %\n \
                                                                     Detector 2: {round(contrasts[2], 5)} %\n \
                                                                     Detector 3: {round(contrasts[1], 5)} %\n")
        else:
            tkinter.messagebox.showinfo(title="Contrasts", message=f"Detector 1: {round(contrasts[0], 2)} %\n \
                                                                    Detector 2: {round(contrasts[1], 2)} %\n \
                                                                    Detector 3: {round(contrasts[2], 2)} %\n")

    def execute(self):
        if self.program == "Decimation":
            try:
                next(pti.decimate(file=self.file, outputfile="Decimation.csv"))
            except StopIteration:
                pass
        elif self.program == "PTI_Inversion":
            pti.invert(file="Decimation.csv", outputfile="PTI_Inversion.csv", response_phases=SubMenu.response_phases)
        elif self.program == "Phase_Scan":
            signals = pd.read_csv(self.file)
            phase_scan = pti.PhaseScan(signals=np.array([signals["DC CH1"], signals["DC CH2"], signals["DC CH3"]]))
            phase_scan.set_min()
            phase_scan.set_max()
            phase_scan.scale_data()
            phase_scan.set_channel_order()
            phase_scan.calulcate_output_phases()
        self.plotting.draw_plots(program=self.program)
