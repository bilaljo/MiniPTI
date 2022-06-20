import tkinter as tk
from tkinter import ttk

class Mode:
    def __init__(self, main_window):
        self.main_window = main_window
        self.mode = None
        self.actions = None
        self.buttons = None
        self.settings = None
        self.treeview = None
        self.tab_1 = None
        self.notebook = None

    def draw_mode_menu(self):
        self.redraw()
        self.buttons = {"Live": tk.Button(self.main_window, text="Live", font="Aerial 13 bold",
                                          command=self.set_offline),
                        "Offline": tk.Button(self.main_window, text="Offline", font="Aerial 13 bold",
                                             command=self.set_offline)}
        self.buttons["Live"].grid(column=0, row=0, sticky="nwes")
        self.buttons["Offline"].grid(column=0, row=1, sticky="nwes")
        self.main_window.grid_columnconfigure(0, weight=1)
        self.main_window.grid_rowconfigure(0, weight=1)
        self.main_window.grid_rowconfigure(1, weight=1)

    def draw_settings(self):
        self.redraw()
        self.settings = {"Back": tk.Button(self.main_window, text="Back", font="Aerial 13 bold",
                         command=self.set_offline),
                         "Response Phases": tk.Button(self.main_window, text="Response Phases", font="Aerial 13 bold",
                                                      command=self.set_offline),
                         "Output Phases": tk.Button(self.main_window, text="Output Phases", font="Aerial 13 bold",
                                                    command=self.set_offline),
                         "Contrasts": tk.Button(self.main_window, text="Contrasts", font="Aerial 13 bold",
                                                command=self.set_offline)}
        self.settings["Response Phases"].grid(column=0, row=0, sticky="nwes")
        self.settings["Output Phases"].grid(column=1, row=0, sticky="nwes")
        self.settings["Contrasts"].grid(column=2, row=0, sticky="nwes")
        self.settings["Back"].grid(column=0, row=5, sticky="nwes")

    def redraw(self):
        for item in self.main_window.grid_slaves():
            item.grid_forget()

    def set_offline(self):
        self.redraw()
        self.mode = "Offline"
        self.buttons = {}
        self.actions = {"Phase Scan": tk.Button(self.main_window, text="Phase Scan", font="Aerial 13 bold",
                                                command=self.set_offline),
                        "Decimation": tk.Button(self.main_window, text="Decimation", font="Aerial 13 bold",
                                                command=self.set_offline),
                        "PTI Inversion": tk.Button(self.main_window, text="PTI Inversion", font="Aerial 13 bold",
                                                   command=self.set_offline),
                        "Back": tk.Button(self.main_window, text="Back", font="Aerial 13 bold",
                                          command=self.draw_mode_menu),
                        "Settings": tk.Button(self.main_window, text="Settings", font="Aerial 13 bold",
                                              command=self.draw_settings)}
        self.actions["Phase Scan"].grid(column=0, row=0, sticky="nwes")
        self.actions["Decimation"].grid(column=1, row=0, sticky="nwes")
        self.actions["PTI Inversion"].grid(column=2, row=0, sticky="nwes")
        self.actions["Back"].grid(column=0, row=5, sticky="nwes")
        self.actions["Settings"].grid(column=5, row=5, sticky="nwes")
        self.main_window.grid_columnconfigure(0, weight=1)
        self.main_window.grid_columnconfigure(1, weight=1)
        self.main_window.grid_columnconfigure(2, weight=1)
        self.main_window.grid_columnconfigure(5, weight=1)
        self.main_window.grid_rowconfigure(0, weight=1)
        self.main_window.grid_rowconfigure(5, weight=1)

    def set_mode(self, mode):
        self.mode = mode

    def get_mode(self):
        return self.mode
