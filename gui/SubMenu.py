from tkinter import filedialog
import tkinter
import os
import configparser
import platform
import csv
import pandas as pd
import matplotlib.pyplot as plt
from math import sqrt, ceil
from matplotlib.backends.backend_tkagg import (
    FigureCanvasTkAgg, NavigationToolbar2Tk)
from tkinter import simpledialog


class SubMenu:
    def __init__(self, window, menu_name, program, parameters=""):
        self.window = window
        self.menu_name = menu_name
        self.file = None
        self.program = program
        self.parameters = parameters
        self.config = configparser.ConfigParser()

    def add_menu_options(self, menu_name, label, command):
        self.window.menus[menu_name].add_command(label=label, command=command)

    @staticmethod
    def get_delimiter(file):
        sniffer = csv.Sniffer()
        with open(file, "r") as csv_file:
            return str(sniffer.sniff(csv_file.readline()).delimiter)

    def update_config(self):
        self.config.read("pti.conf")
        if not self.config.sections():
            self.config.add_section("file")
        if platform.system() == "Windows":
            self.config["file"][os.path.splitext(self.program)[0] + "_Path"] = self.file
        else:
            self.config["file"][self.program + "_Path"] = self.file
        self.config["file"]["delimiter"] = self.get_delimiter(self.file)
        with open("pti.conf", "w") as configFile:
            self.config.write(configFile)

    def file_dialog(self):
        filetypes = (('csv files', '*.csv'), ('binary files', '*.bin'), ('text files (tab separted)', '*.txt'),
                     ('All files', '*.*'))
        self.file = filedialog.askopenfilenames(filetypes=filetypes)
        if self.file:
            self.file = self.file[0]
            self.update_config()

    def set_response_phases1(self):
        value = simpledialog.askfloat("Response Phases", "Detector 1", parent=self.window.root)
        self.config.read("pti.conf")
        if "system_phases" not in self.config.sections():
            self.config.add_section("system_phases")
        self.config["system_phases"]["detector_1"] = str(value)
        with open("pti.conf", "w") as configFile:
            self.config.write(configFile)

    def set_response_phases2(self):
        value = simpledialog.askfloat("Response Phases", "Detector 2", parent=self.window.root)
        self.config.read("pti.conf")
        if "system_phases" not in self.config.sections():
            self.config.add_section("system_phases")
        self.config["system_phases"]["detector_2"] = str(value)
        with open("pti.conf", "w") as configFile:
            self.config.write(configFile)

    def set_response_phases3(self):
        value = simpledialog.askfloat("Response Phases", "Detector 3", parent=self.window.root)
        self.config.read("pti.conf")
        if "system_phases" not in self.config.sections():
            self.config.add_section("system_phases")
        self.config["system_phases"]["detector_3"] = str(value)
        with open("pti.conf", "w") as configFile:
            self.config.write(configFile)

    def execute(self):
        if platform.system() == "Windows":
            os.system(self.program)
        else:
            os.system("./" + self.program)
        headers = 0
        data = pd.read_csv(self.file)
        labels = []
        for column in data:
            headers += 1
            labels.append(column)
        n = ceil(sqrt(headers))
        fig, axis = plt.subplots(n, n)
        k = 0
        for i in range(n):
            for j in range(n):
                axis[i, j].plot(range(len(data[labels[k]])), data[labels[k]], label=labels[k])
                k += 1
                axis[i, j].legend()
                axis[i, j].grid(True)

        canvas = FigureCanvasTkAgg(fig, master=self.window.root)  # A tk.DrawingArea.
        canvas.draw()
        canvas.get_tk_widget().pack(side=tkinter.TOP, fill=tkinter.BOTH, expand=1)

        toolbar = NavigationToolbar2Tk(canvas, self.window.root)
        toolbar.update()
        canvas.get_tk_widget().pack(side=tkinter.TOP, fill=tkinter.BOTH, expand=1)
