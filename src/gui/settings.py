import tkinter as tk

import pandas as pd
from tksheet import Sheet


class Settings:
    def __init__(self):
        self.sheet = None

    def setup_config(self, settings_frame):
        data = pd.read_csv("settings.csv", index_col="Setting")
        self.sheet = Sheet(parent=settings_frame, data=data.values.tolist(), headers=list(data.columns),
                           row_index=list(data.index), show_x_scrollbar=False, show_y_scrollbar=False,
                           height=160, width=460, font=("Arial", 11, "normal"), header_font=("Arial", 11, "normal"),
                           column_width=100, row_index_width=150)
        self.sheet.enable_bindings()
        self.sheet.extra_bindings(bindings="end_edit_cell")
        self.sheet.pack(side="top", padx=10, expand=True, fill=tk.BOTH)

    def load_config(self):
        data = pd.read_csv("settings.csv", index_col="Setting").T
        contrast = round((data["Max Intensities"] - data["Min Intensities"]) / (
                    data["Max Intensities"] + data["Min Intensities"]), 2)
        data["Contrast"] = contrast
        self.sheet.set_sheet_data(data=data.T.values.tolist())

    def save_config(self):
        data = self.sheet.get_sheet_data(get_header=False, get_index=False)
        row_index = ["Max Intensities", "Min Intensities", "Output Phases", "Response Phases", "Contrast"]
        headers = ["Detector 1", "Detector 2", "Detector 3"]
        settings = pd.DataFrame(data=data, columns=headers, index=row_index)
        settings.index.name = "Setting"
        settings.to_csv("settings.csv")
