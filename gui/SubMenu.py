from tkinter import filedialog
from Phase_Scan import Plotting
import os
import configparser
import platform
import csv

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
        if "file" not in self.config.sections():
            self.config.add_section("file")
        if platform.system() == "Windows":
            self.config["file"][os.path.splitext(self.program)[0] + "_Path"] = self.file
        else:
            self.config["file"][self.program + "_Path"] = self.file
        self.config["file"]["delimiter"] = self.get_delimiter(self.file)
        with open("pti.conf", "w") as configFile:
            self.config.write(configFile)

    def file_dialog(self):
        filetypes = (('csv files', '*.csv'), ('binary files', '*.bin'), ('text files (tab separated)', '*.txt'),
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
        plotting = Plotting(main_window=self.window.root)
        plotting.draw_plots(self.program)
