import tkinter as tk
from tkinter import ttk


class Tabs:
    tab_control = None

    def __init__(self, frame):
        self.frame = frame
        self.tab = None

    def set_tab_frame(self):
        Tabs.tab_control = ttk.Notebook(self.frame)
        self.tab_control.pack(expand=1, fill="both")

    def create_tab(self, text):
        if self.tab_control is None:
            raise ValueError("Tab control is none")
        self.tab = tk.Frame(self.tab_control)
        self.tab_control.add(self.tab, text=text)
