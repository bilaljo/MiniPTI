import configparser
import tkinter as tk
from tkinter import ttk


class Settings:
    def __init__(self):
        self.tree = None

    @staticmethod
    def check_config_file():
        pti_config = configparser.ConfigParser()
        required_sections = ["Max Intensities", "Min Intensities", "Output Phases", "Response Phases"]
        for section in required_sections:
            if section not in pti_config.sections():
                pti_config.add_section(section)
        for section in pti_config.sections():
            for channel in range(1, 4):
                if f"Detector {channel}" not in pti_config[section]:
                    pti_config[section][f"Detector {channel}"] = "Nan"
        with open("pti.conf", "w") as config:
            pti_config.write(config)

    def setup_tree(self, settings_frame):
        pti_config = configparser.ConfigParser()
        pti_config.read("pti.conf")
        self.tree = ttk.Treeview(settings_frame, columns=("Configuration", "Value"), show="tree")
        self.tree.column("#0", width=150, stretch=False)
        self.tree.column("#1", width=150, stretch=False)
        self.tree.pack(side="top", padx=10, pady=10, expand=True, fill=tk.BOTH)

        output_phases = self.tree.insert("", "end", text='Output Phases', values=[], open=False)
        self.tree.insert(output_phases, "end", text='Detector 1', values=["0.00 rad"], open=False)
        self.tree.insert(output_phases, "end", text='Detector 2',
                         values=[f"{round(float(pti_config['Output Phases']['Detector 2']), 2)} rad"], open=False)
        self.tree.insert(output_phases, "end", text='Detector 3',
                         values=[f"{round(float(pti_config['Output Phases']['Detector 3']), 2)} rad"], open=False)

        def calulcate_contrast(min_value, max_value):
            return round((max_value - min_value) / (max_value + min_value) * 100, 2)

        contrasts = self.tree.insert("", "end", text='Contrasts', values=[], open=False)
        contrast = calulcate_contrast(float(pti_config['Min Intensities']['Detector 1']),
                                      float(pti_config['Max Intensities']['Detector 1']))
        self.tree.insert(contrasts, "end", text='Detector 1', values=[f"{contrast} %"], open=False)
        contrast = calulcate_contrast(float(pti_config['Min Intensities']['Detector 2']),
                                      float(pti_config['Max Intensities']['Detector 2']))
        self.tree.insert(contrasts, "end", text='Detector 2', values=[f"{contrast} %"], open=False)
        contrast = calulcate_contrast(float(pti_config['Min Intensities']['Detector 3']),
                                      float(pti_config['Max Intensities']['Detector 3']))
        self.tree.insert(contrasts, "end", text='Detector 3', values=[f"{contrast} %"], open=False)
        response_phases = self.tree.insert("", "end", text='Response Phases', values=[], open=False)
        self.tree.insert(response_phases, "end", text='Detector 1',
                         values=[f"{round(float(pti_config['Response Phases']['Detector 2']), 2)} rad"], open=False)
        self.tree.insert(response_phases, "end", text='Detector 1',
                         values=[f"{round(float(pti_config['Response Phases']['Detector 2']), 2)} rad"], open=False)
        self.tree.insert(response_phases, "end", text='Detector 1',
                         values=[f"{round(float(pti_config['Response Phases']['Detector 3']), 2)} rad"], open=False)
