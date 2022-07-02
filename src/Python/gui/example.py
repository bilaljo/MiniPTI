"""
Example script for testing the Azure ttk theme
Author: rdbende
License: MIT license
Source: https://github.com/rdbende/ttk-widget-factory
"""


import tkinter as tk
from tkinter import ttk


class App(ttk.frame):
    def __init__(self, parent):
        self.root = parent

        # Create widgets :)
        self.setup_widgets()

    def setup_widgets(self):
        # Create a Frame for the Radiobuttons
        self.radio_frame = ttk.LabelFrame(self.root, text="Mode", padding=(20, 10))
        self.radio_frame.grid(row=2, column=0, padx=(20, 10), pady=10, sticky="nsew")

        # Radiobuttons
        self.radio_1 = ttk.Radiobutton(
            self.radio_frame, text="Unselected", variable=None, value=1)
        self.radio_1.grid(row=0, column=0, padx=5, pady=10, sticky="nsew")

if __name__ == "__main__":
    root = tk.Tk()
    root.title("")

    # Simply set the theme
    root.tk.call("source", "azure.tcl")
    root.tk.call("set_theme", "light")

    app = App(root)


    # Set a minsize for the window, and place it in the middle


    root.mainloop()
