import os
import platform
from collections import namedtuple
from tkinter import filedialog, messagebox

import pandas as pd

from gui.model import Model
from gui.view import View


class Controller:
    def __init__(self):
        self.live_destination = "./"
        self.live_plot = None
        self.settings = namedtuple("Settings", ("file_path", "data", "sheet"))
        self.settings.file_path = "settings.csv"
        self.running = False
        self.init_settings()
        self.model = Model()
        self.view = View(self)
        self.file_path = ""

    def on_close(self):
        if messagebox.askokcancel("Quit", "Do you want to quit?"):
            self.view.destroy()

    def init_settings(self):
        headers = ["Detector 1", "Detector 2", "Detector 3"]
        index = ["Max Intensities [V]", "Min Intensities [V]", "Output Phases [deg]", "Response Phases [deg]",
                 "Contrast [%]"]
        if not os.path.exists("settings.csv"):  # If no settings found, a new empty file is created.
            self.settings.data = pd.DataFrame(index=index, columns=headers)
            self.settings.data.to_csv("settings.csv", index=True, index_label="Setting")
        else:
            try:
                settings = pd.read_csv(filepath_or_buffer="settings.csv", index_col="Setting")
            except ValueError:
                self.settings.data = pd.DataFrame(index=index, columns=headers)
                self.settings.data.to_csv("settings.csv", index=True, index_label="Setting")
            else:
                if list(settings.columns) != headers or list(settings.index) != index:  # The file is in any way broken.
                    self.settings.data = pd.DataFrame(index=index, columns=headers)
                    self.settings.data.to_csv("settings.csv", index=True, index_label="Setting")

    def load_config(self):
        default_extension = "*.csv"
        file_types = (("CSV File", "*.csv"), ("Tab Separated File", "*.txt"), ("All Files", "*"))
        self.settings.file_path = filedialog.askopenfilename(defaultextension=default_extension, filetypes=file_types,
                                                             title="Settings File Path")
        self.settings.data = pd.read_csv(self.settings.file_path, index_col="Setting")
        contrast = round(
            (self.settings.data.loc["Max Intensities [V]"] - self.settings.data.loc["Min Intensities [V]"]) /
            (self.settings.data.loc["Max Intensities [V]"] + self.settings.data.loc["Min Intensities [V]"]), 2)
        self.settings.data.loc["Contrast [%]"] = contrast
        self.settings.sheet.set_sheet_data(data=self.settings.data.values.tolist())

    def save_config(self):
        data = self.settings.sheet.get_sheet_data(get_header=False, get_index=False)
        headers = ["Detector 1", "Detector 2", "Detector 3"]
        index = ["Max Intensities [V]", "Min Intensities [V]", "Output Phases [deg]", "Response Phases [deg]",
                 "Contrast [%]"]
        self.settings.data = pd.DataFrame(data=data, columns=headers, index=index)
        self.settings.data.index.name = "Setting"
        self.settings.data.to_csv(self.settings.file_path)

    def decimation_button_pressed(self):
        default_extension = "*.bin"
        file_types = (("Binary File", "*.bin"), ("All Files", "*"))
        file_path = filedialog.askopenfilename(defaultextension=default_extension, filetypes=file_types,
                                               title="Decimation File Path")
        if not file_path:
            return
        self.model.calculate_decimation(file_path)

    def inversion_button_pressed(self):
        default_extension = "*.csv"
        file_types = (("CSV File", "*.csv"), ("Tab Separated File", "*.txt"), ("All Files", "*"))
        file_path = filedialog.askopenfilename(defaultextension=default_extension, filetypes=file_types,
                                               title="Inversion File Path")
        if not file_path:
            return
        self.model.calculate_inversion(settings_path=self.settings.file_path, inversion_path=file_path)

    def characterisation_button_pressed(self):
        default_extension = "*.csv"
        file_types = (("CSV File", "*.csv"), ("Tab Separated File", "*.txt"), ("All Files", "*"))
        file_path = filedialog.askopenfilename(defaultextension=default_extension, filetypes=file_types,
                                               title="Inversion File Path")
        if not file_path:
            return
        self.model.calculate_characitersation(file_path)
        self.settings.data.loc["Output Phases [deg]"] = self.model.pti.interferometer_characterisation.output_phases
        self.settings.data.loc["Min Intensities [V]"] = self.model.pti.interferometer_characterisation.min_intensities
        self.settings.data.loc["Max Intensities [V]"] = self.model.pti.interferometer_characterisation.max_intensities
        self.settings.sheet.set_sheet_data(data=self.settings.data.values.tolist())

    def online_path_cooser(self):
        default_extension = "*.bin"
        file_types = (("Binary File", "*.bin"), ("All Files", "*"))
        file_path = filedialog.askopenfilename(defaultextension=default_extension, filetypes=file_types,
                                               title="Decimation File Path")
        if not file_path:
            return
        if platform.system() == "Windows":
            desktop = os.path.join(os.path.join(os.environ['USERPROFILE']), 'Desktop')
            self.model.destination_folder = filedialog.askdirectory(initialdir=desktop)
        else:
            self.model.destination_folder = filedialog.askdirectory(initialdir="~")
        self.model.decimation_path = file_path
        self.model.settings_path = self.settings.file_path

    def __set_file_path(self):
        default_extension = "*.csv"
        file_types = (("CSV File", "*.csv"), ("Tab Separated File", "*.txt"), ("All Files", "*"))
        file_path = filedialog.askopenfilename(defaultextension=default_extension, filetypes=file_types,
                                               title="Plotting File Path")
        if file_path is None:
            return
        self.file_path = file_path

    def plot_inversion(self):
        self.__set_file_path()
        if self.file_path is None:
            return
        data = pd.read_csv(self.file_path)
        self.view.setup_plots(tab="Interferometric Phase")
        self.view.draw_plot(x_label="Time [s]", y_label=r"$\varphi$ [rad]", x_data=range(len(data)),
                            y_data=data["Interferometric Phase"], tab="Interferometric Phase")
        self.view.setup_plots(tab="PTI Signal")
        self.view.draw_plot(x_label="Time [s]", y_label=r"$\Delta\varphi$ [rad]", x_data=range(len(data)),
                            y_data=data["PTI Signal"], tab="PTI Signal")

    def plot_dc(self):
        self.__set_file_path()
        if self.file_path is None:
            return
        data = pd.read_csv(self.file_path)
        self.view.setup_plots(tab="DC Signals")
        self.view.draw_plot(x_label="Time [s]", y_label="Intensity [V]", x_data=range(len(data)), y_data=data,
                            tab="DC Signals")

    def run(self):
        self.running = True
        self.view.setup_live_plotting()

        def live():
            self.model.live_calculation()
            self.view.live_plot(self.model.time, self.model.decimation_data, self.model.pti_values,
                                self.model.pti_signal_mean)
            if self.running:
                self.view.after(1000, live)

        return self.view.after(1000, live)

    def stop(self):
        self.running = False
