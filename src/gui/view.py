import tkinter as tk
from tkinter import ttk

import pandas as pd
from matplotlib import pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
from tksheet import Sheet


class View(tk.Tk):
    def __init__(self, controller):
        super().__init__()
        self.controller = controller
        self.tab_control = None
        self.sheet = None
        self.tab_control = ttk.Notebook(self)
        self.tab_control.pack(expand=1, fill="both")
        self.figs = {"DC Signals": None, "Interferometric Phase": None, "PTI Signal": None, "Output Phases": None}
        self.axes = {"DC Signals": None, "Interferometric Phase": None, "PTI Signal": None, "Output Phases": None}
        self.canvas = {"DC Signals": None, "Interferometric Phase": None, "PTI Signal": None, "Output Phases": None}
        self.plot_toolbar = {"DC Signals": None, "Interferometric Phase": None, "PTI Signal": None,
                             "Output Phases": None}
        self.tabs = dict()
        self.frames = dict()
        self.init_tabs()
        self.init_frames()
        self.setup_config(self.frames["Configuration"])
        self.init_buttons()
        self.protocol("WM_DELETE_WINDOW", controller.on_close)

    def create_tab(self, text):
        if self.tab_control is None:
            raise ValueError("Tab control is none")
        self.tabs[text] = ttk.Frame(self.tab_control)
        self.tab_control.add(self.tabs[text], text=text)

    def set_frame(self, master, title):
        self.frames[title] = ttk.LabelFrame(master=master, text=title, padding=(20, 10))
        self.frames[title].pack(side="top", anchor="n", padx=10, pady=10, expand=True, fill=tk.BOTH)

    def init_tabs(self):
        self.create_tab("Home")
        self.create_tab("DC Signals")
        # self.create_tab("Min and Max Values")
        # self.create_tab("Output Phases")
        self.create_tab("Interferometric Phase")
        self.create_tab("PTI Signal")

    def init_frames(self):
        self.set_frame(self.tabs["Home"], "Configuration")
        self.set_frame(self.tabs["Home"], "Offline")
        self.set_frame(self.tabs["Home"], "Plotting")
        self.set_frame(self.tabs["Home"], "Live Measurement")

    def init_buttons(self):
        def create_button(frame, text, action):
            button = ttk.Button(master=frame, text=text, command=action)
            button.pack(side="left", padx=10, pady=10)
            return button

        create_button(frame=self.frames["Configuration"], text="Save Config", action=self.controller.save_config)
        create_button(frame=self.frames["Configuration"], text="Load Config", action=self.controller.load_config)

        create_button(frame=self.frames["Offline"], text="Decimation", action=self.controller.decimation_button_pressed)
        create_button(frame=self.frames["Offline"], text="Inversion", action=self.controller.inversion_button_pressed)
        create_button(frame=self.frames["Offline"], text="Characterisation",
                      action=self.controller.characterisation_button_pressed)

        create_button(frame=self.frames["Plotting"], text="Decimation", action=self.controller.plot_dc)
        create_button(frame=self.frames["Plotting"], text="Inversion", action=self.controller.plot_inversion)
        create_button(frame=self.frames["Plotting"], text="Output Phases", action=self.plot_phase_scan)

        create_button(frame=self.frames["Live Measurement"], text="Run", action=self.controller.run)
        create_button(frame=self.frames["Live Measurement"], text="Stop", action=self.controller.stop)
        create_button(frame=self.frames["Live Measurement"], text="Destination Folder",
                      action=self.controller.online_path_cooser)

    def setup_config(self, settings_frame):
        self.controller.settings.data = pd.read_csv(self.controller.settings.file_path, index_col="Setting")
        self.sheet = Sheet(parent=settings_frame, data=self.controller.settings.data.values.tolist(),
                           headers=list(self.controller.settings.data.columns),
                           row_index=list(self.controller.settings.data.index), show_x_scrollbar=False,
                           show_y_scrollbar=False, height=160, width=460, font=("Arial", 11, "normal"),
                           header_font=("Arial", 11, "normal"), column_width=100, row_index_width=160)
        self.sheet.enable_bindings()
        self.sheet.extra_bindings(bindings="end_edit_cell")
        self.sheet.pack(side="top", padx=10, expand=True, fill=tk.BOTH)
        self.controller.settings.sheet = self.sheet

    def draw_plot(self, x_label, y_label, x_data, y_data, tab):
        self.axes[tab].cla()
        self.axes[tab].grid()
        self.axes[tab].set_xlabel(x_label, fontsize=11)
        self.axes[tab].set_ylabel(y_label, fontsize=11)
        if tab == "DC Signals":
            for channel in range(3):
                self.axes[tab].plot(x_data, y_data[f"DC CH{channel + 1}"], label=f"CH{channel + 1}")
                self.axes[tab].legend(fontsize=11)
        else:
            self.axes[tab].plot(x_data, y_data)
        self.canvas[tab].draw()

    def setup_plots(self, tab):
        self.figs[tab], self.axes[tab] = plt.subplots()
        if tab == "DC Signals":
            self.axes[tab].plot([], [], label="CH1")
            self.axes[tab].plot([], [], label="CH2")
            self.axes[tab].plot([], [], label="CH3")
            self.axes[tab].legend(fontsize=11)
        elif tab == "Output Phases":
            self.axes[tab].hist([], label="Detector 2")
            self.axes[tab].hist([], label="Detector 3")
            self.axes[tab].legend(fontsize=11)
        else:
            self.axes[tab].plot([], [])
        if self.canvas[tab] is not None:
            self.canvas[tab].get_tk_widget().pack_forget()
            self.plot_toolbar[tab].pack_forget()
        self.canvas[tab] = FigureCanvasTkAgg(self.figs[tab], master=self.tabs[tab])
        self.canvas[tab].draw()
        self.canvas[tab].get_tk_widget().pack()
        self.plot_toolbar[tab] = NavigationToolbar2Tk(self.canvas[tab], self.tabs[tab])
        self.plot_toolbar[tab].update()
        self.canvas[tab].get_tk_widget().pack(side=tk.TOP, fill=tk.BOTH, expand=1)

    def plot_phase_scan(self):
        pass

    def setup_live_plotting(self):
        self.setup_plots(tab="DC Signals")
        self.setup_plots(tab="Interferometric Phase")
        self.setup_plots(tab="PTI Signal")

    def live_plot(self, time, decimation_data, pti_values):
        self.draw_plot(x_label="Time [s]", y_label="Intensity [V]", x_data=time, y_data=decimation_data,
                       tab="DC Signals")
        self.draw_plot(x_label="Time [s]", y_label=r"$\varphi$ [rad]", x_data=time,
                       y_data=pti_values["Interferometric Phase"], tab="Interferometric Phase")
        self.draw_plot(x_label="Time [s]", y_label=r"$\Delta\varphi$ [rad]", x_data=time,
                       y_data=pti_values["PTI Signal"], tab="PTI Signal")
