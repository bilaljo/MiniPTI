from tkinter import filedialog
from Plotting import Plotting
from tkinter import simpledialog
from PTI.
import tkinter


class SubMenu:
    def __init__(self, window, menu_name, program, parameters=""):
        self.window = window
        self.menu_name = menu_name
        self.file = ""
        self.program = program
        self.parameters = parameters
        # self.verbose = tkinter.BooleanVar(window.root)
        SubMenu.plotting = Plotting(main_window=self.window.root)

    def add_menu_options(self, menu_name, label, command):
        self.window.menus[menu_name].add_command(label=label, command=command)

    def file_dialog(self):
        filetypes = (('csv files', '*.csv'), ('binary files', '*.bin'), ('text files (tab separated)', '*.txt'),
                     ('All files', '*.*'))
        file_name = filedialog.askopenfilenames(filetypes=filetypes)
        if file_name:
            self.file = file_name[0]

    def set_response_phases(self, detector):
        return simpledialog.askfloat(f"Response Phases", f"Detector {detector}", parent=self.window.root)

    def execute(self, program):
        if program == "Decimation":

        SubMenu.plotting.draw_plots(program=self.program, config=self.config)
