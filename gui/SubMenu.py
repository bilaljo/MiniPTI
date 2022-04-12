from tkinter import filedialog
import os
import configparser
import platform
import csv


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
        self.file = filedialog.askopenfilenames(filetypes=filetypes)[0]
        self.update_config()

    def execute(self):
        if platform.system() == "Windows":
            os.system(self.program)
        else:
            os.system("./" + self.program)
