import tkinter as tk
from tkinter import filedialog

import pandas as pd
from tksheet import Sheet


class Settings:
    file_path = "settings.csv"
    data = None

    def __init__(self):
        self.sheet = None

    def setup_config(self, settings_frame):
        Settings.data = pd.read_csv(Settings.file_path, index_col="Setting")
        self.sheet = Sheet(parent=settings_frame, data=Settings.data.values.tolist(),
                           headers=list(Settings.data.columns),
                           row_index=list(Settings.data.index), show_x_scrollbar=False, show_y_scrollbar=False,
                           height=160, width=460, font=("Arial", 11, "normal"), header_font=("Arial", 11, "normal"),
                           column_width=100, row_index_width=150)
        self.sheet.enable_bindings()
        self.sheet.extra_bindings(bindings="end_edit_cell")
        self.sheet.pack(side="top", padx=10, expand=True, fill=tk.BOTH)

    def load_config(self):
        default_extension = "*.csv"
        file_types = (("CSV File", "*.csv"), ("Tab Separated File", "*.txt"), ("All Files", "*"))
        Settings.settings_path = filedialog.askopenfilename(defaultextension=default_extension, filetypes=file_types,
                                                            title="Settings File Path")
        Settings.data = pd.read_csv(Settings.file_path, index_col="Setting")
        contrast = round((Settings.data.loc["Max Intensities"] - Settings.data.loc["Min Intensities"]) / (
                Settings.data.loc["Max Intensities"] + Settings.data.loc["Min Intensities"]), 2)
        Settings.data.loc["Contrast"] = contrast
        self.sheet.set_sheet_data(data=Settings.data.values.tolist())

    def save_config(self):
        data = self.sheet.get_sheet_data(get_header=False, get_index=False)
        row_index = ["Max Intensities", "Min Intensities", "Output Phases", "Response Phases", "Contrast"]
        headers = ["Detector 1", "Detector 2", "Detector 3"]
        settings = pd.DataFrame(data=data, columns=headers, index=row_index)
        settings.index.name = "Setting"
        Settings.data = settings
        settings.to_csv(Settings.file_path)
