from tkinter import filedialog
from Plotting import Plotting
from tkinter import simpledialog
import pti
import pandas as pd


class SubMenu:
    def __init__(self, window, menu_name, program, parameters=""):
        self.window = window
        self.menu_name = menu_name
        self.file = ""
        self.program = program
        self.parameters = parameters
        self.plotting = Plotting(main_window=self.window.root)

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

    def execute(self):
        if self.program == "Decimation":
            pti.decimate(self.file, "Decimation.csv")
        elif self.program == "Inversion":
            pti.invert(file="Decimation.csv", outputfile="PTI_Inversion.csv", output_phases=[], live=False)
        elif self.program == "Phase_Scan":
            signals = pd.read_csv(self.file)
            phase_scan = pti.PhaseScan(signals=[signals["DC CH1"], signals["DC CH2"], signals["DC CH3"]])
            phase_scan.scaled_signals()
            phase_scan.calulcate_output_phases()
        self.plotting.draw_plots(program=self.program)
