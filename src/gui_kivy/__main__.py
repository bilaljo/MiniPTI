import queue
import threading
from collections import namedtuple

import numpy as np
import pandas as pd
from kivy.uix.floatlayout import FloatLayout
from matplotlib import pyplot as plt
from kivy.app import App
from kivy.properties import ListProperty
from kivy.uix.tabbedpanel import TabbedPanel
from kivy.uix.widget import Widget
from kivy.garden.matplotlib.backend_kivyagg import FigureCanvasKivyAgg

from tkinter import filedialog
from pti import PTI


class Home(Widget):
    min_intensities = ListProperty([np.nan, np.nan, np.nan])
    max_intensities = ListProperty([np.nan, np.nan, np.nan])
    output_phases = ListProperty([np.nan, np.nan, np.nan])
    response_phases = ListProperty([np.nan, np.nan, np.nan])


class Controller(TabbedPanel, FloatLayout):
    running = False
    decimation_data = queue.Queue(maxsize=1000)
    pti_values = namedtuple("PTI", ("phase", "pti_signal"))
    pti_data = queue.Queue(maxsize=1000)
    pti = PTI()
    decimation_path = "280422.bin"
    settings_path = "settings.csv"
    file_paths = {"Decimation": "", "Inversion": "", "Phase Scan": ""}

    def __init__(self, max_size):
        TabbedPanel.__init__(self)
        FloatLayout.__init__(self)

    @staticmethod
    def set_file_path(program):
        if program == "Decimation":
            default_extension = "*.bin"
            file_types = (("Binary File", "*.bin"), ("All Files", "*"))
        else:
            default_extension = "*.csv"
            file_types = (("CSV File", "*.csv"), ("Tab Separated File", "*.txt"), ("All Files", "*"))
        file = filedialog.askopenfilename(defaultextension=default_extension, filetypes=file_types,
                                          title=f"{program} File Path")
        Controller.file_paths[program] = file

    @staticmethod
    def calculate_decimation():
        threading.Thread(target=Controller.pti.decimate, args=(Controller.file_paths["Decimation"])).start()

    def live_measurement(self, dt):
        self.pti.pti(self.decimation_path, self.settings_path)
        self.decimation_data.put(self.pti.decimation.dc_down_sampled)
        self.pti_values.phase = self.pti.inversion.interferometric_phase
        self.pti_values.pti_signal = self.pti.inversion.pti_signal
        self.pti_data.put(self.pti_values)

    axes = {"DC Signals": None, "Interferometric Phase": None, "Output Phases": None, "Min-Max-Intensities": None,
            "PTI Signal": None}
    figs = {"DC Signals": None, "Interferometric Phase": None, "Output Phases": None, "Min-Max-Intensities": None,
            "PTI Signal": None}

    def __int__(self, **kwargs):
        super().__init__(**kwargs)

    @staticmethod
    def __setup_plots(tab):
        Controller.figs[tab], Controller.axes[tab] = plt.subplots()
        if tab == "DC Signal":
            Controller.axes[tab].plot([], [], label="CH1")
            Controller.axes[tab].plot([], [], label="CH2")
            Controller.axes[tab].plot([], [], label="CH3")
            Controller.axes[tab].legend(fontsize=11)
        elif tab == "Output Phases":
            Controller.axes[tab].hist([], label="Detector 2")
            Controller.axes[tab].hist([], label="Detector 3")
            Controller.axes[tab].legend(fontsize=11)
        else:
            Controller.axes[tab].plot([], [])

    @staticmethod
    def __draw_plot(x_label, y_label, x_data, y_data, tab):
        Controller.axes[tab].cla()
        Controller.axes[tab].grid()
        Controller.axes[tab].set_xlabel(x_label, fontsize=11)
        Controller.axes[tab].set_ylabel(y_label, fontsize=11)
        if tab == "DC Signals":
            for channel in range(3):
                Controller.axes[tab].plot(x_data, y_data[f"DC CH{channel + 1}"], label=f"CH{channel + 1}")
                Controller.axes[tab].legend(fontsize=11)
        else:
            Controller.axes[tab].scatter(x_data, y_data, s=2)

    def plot_dc(self):
        file_path = "Decimation.csv" #Controller.__plot_path("Inversion")
        if file_path is None:
            return
        data = pd.read_csv(file_path)
        Controller.__setup_plots(tab="DC Signals")
        Controller.__draw_plot(x_label="Time [s]", y_label="Intensity [V]", x_data=range(len(data)), y_data=data,
                             tab="DC Signals")
        print(self.ids.dc)
        dc = self.ids.dc.ids.dc
        dc.add_widget(FigureCanvasKivyAgg(Controller.figs["DC Signals"]))

class ControllerApp(App):
    def build(self):
        return Controller(1000)


def main():
    # gui_controller = Controllerler(max_size=1000)
    # Clock.schedule_interval(callback=gui_controller.live_measurement, timeout=1)
    ControllerApp().run()


if __name__ == "__main__":
    main()
