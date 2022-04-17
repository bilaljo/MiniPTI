import tkinter
from tkinter import ttk
import pandas as pd
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
from matplotlib.figure import Figure


class Plotting:
    def __init__(self, main_window):
        self.tab_control = ttk.Notebook(main_window)
        self.main_window = main_window
        self.tab_dc = ttk.Frame(self.tab_control)
        self.tab_qudratur = ttk.Frame(self.tab_control)
        self.tab_in_phase = ttk.Frame(self.tab_control)
        self.tab_pti = ttk.Frame(self.tab_control)
        style = ttk.Style(main_window)
        self.open_tabs = {"PTI Inversion": False, "Decimation": False}
        self.canvas = None
        self.plot = None
        style.configure('TNotebook.Tab', width=main_window.winfo_screenwidth(), height=main_window.winfo_height())

    def plot_dc(self, file_name):
        self.tab_dc = ttk.Frame(self.tab_control)
        data = pd.read_csv(file_name)
        fig = Figure((2, 9), dpi=100)
        ax = fig.add_subplot()
        for i in range(1, 4):
            ax.plot(range(len(data["DC1"])), data[f"DC{i}"], label=f"DC{i}")
        ax.legend()
        ax.grid(True)
        ax.set_xlabel("Time in s", fontsize=12)
        ax.set_ylabel("Photo Detector Voltage in V", fontsize=12)
        ax.legend(fontsize=12)
        self.tab_dc.pack(fill='both', expand=True)
        self.tab_control.add(self.tab_dc, text="DC Detector Voltages")
        return fig

    def plot_in_phase_component(self, file_name):
        data = pd.read_csv(file_name)
        fig = Figure((2, 9), dpi=100)
        ax = fig.add_subplot()
        for i in range(1, 4):
            ax.plot(range(len(data["X1"])), data[f"X{i}"], label=f"X{i}")
        ax.legend(fontsize=12)
        ax.grid(True)
        ax.set_xlabel("Time in s", fontsize=12)
        ax.set_ylabel("In-Phase Component in V", fontsize=12)
        self.tab_control.add(self.tab_in_phase, text="AC In-Phase Component")
        return fig

    def plot_quadratur_component(self, file_name):
        data = pd.read_csv(file_name)
        fig = Figure((2, 9), dpi=100)
        ax = fig.add_subplot()
        for i in range(1, 4):
            ax.plot(range(len(data["Y1"])), data[f"Y{i}"], label=f"Y{i}")
        ax.legend(fontsize=12)
        ax.grid(True)
        ax.set_xlabel("Time in s", fontsize=12)
        ax.set_ylabel("Quadratur Component in V", fontsize=12)
        ax.legend(fontsize=12)
        self.tab_control.add(self.tab_qudratur, text="AC Quadratur Component")
        return fig

    def plot_pti_signal(self, file_name):
        data = pd.read_csv(file_name)
        fig = Figure((2, 9), dpi=100)
        ax = fig.add_subplot()
        ax.plot(range(len(data["PTI"])), data["PTI"])
        ax.grid(True)
        ax.set_xlabel("Time in s", fontsize=12)
        ax.set_ylabel("PTI Signal in rad", fontsize=12)
        self.tab_control.add(self.tab_pti, text="PTI Signal")
        return fig

    def create_plot(self, tab, fig):
        self.canvas = FigureCanvasTkAgg(fig, master=tab)
        self.canvas.get_tk_widget().pack()
        self.canvas.draw()
        self.plot = self.canvas.get_tk_widget().pack(side=tkinter.TOP, fill=tkinter.BOTH, expand=1)
        toolbar = NavigationToolbar2Tk(self.canvas, tab)
        toolbar.update()
        self.canvas.get_tk_widget().pack(side=tkinter.TOP, fill=tkinter.BOTH, expand=1)

    def draw_plots(self, program, file):
        if program == "Decimation" or program == "Decimation.exe" or self.open_tabs["Decimation"]:
            fig = self.plot_dc("Decimation.csv")
            self.create_plot(self.tab_dc, fig)
            fig = self.plot_in_phase_component(file)
            self.create_plot(self.tab_in_phase, fig)
            fig = self.plot_quadratur_component(file)
            self.create_plot(self.tab_qudratur, fig)
            self.open_tabs["Decimation"] = True
        if program == "PTI_Inversion" or program == "PTI_Inversion.exe" or self.open_tabs["PTI Inversion"]:
            fig = self.plot_pti_signal("PTI_Inversion.csv")
            self.create_plot(self.tab_pti, fig)
            self.open_tabs["PTI Inversion"] = True
        self.tab_control.pack(expand=True)
