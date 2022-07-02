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
        self.tab_root_mean_square = ttk.Frame(self.tab_control)
        self.tab_response_phase = ttk.Frame(self.tab_control)
        self.tab_interferometric_phase = ttk.Frame(self.tab_control)
        self.tab_demodulated_signal = ttk.Frame(self.tab_control)
        style = ttk.Style(main_window)
        self.canvas = None
        self.plot = None
        style.configure('TNotebook.Tab', width=main_window.winfo_screenwidth(), height=main_window.winfo_height())

    def plot_dc(self, file_name):
        self.tab_dc = ttk.Frame(self.tab_control)
        data = pd.read_csv(file_name)
        fig = Figure((2, 9), dpi=100)
        ax = fig.add_subplot()
        for i in range(1, 4):
            ax.plot(range(len(data["DC CH1"])), data[f"DC CH{i}"], label=f"Detector {i}")
        ax.legend()
        ax.grid(True)
        ax.set_xlabel("Time in s", fontsize=12)
        ax.set_ylabel("Photo Detector Voltage in V", fontsize=12)
        ax.legend(fontsize=12)
        self.tab_dc.pack(fill='both', expand=True)
        self.tab_control.add(self.tab_dc, text="DC Detector Voltages")
        return fig

    def plot_pti_signal(self, file_name):
        data = pd.read_csv(file_name)
        fig = Figure((2, 9), dpi=100)
        ax = fig.add_subplot()
        ax.plot(range(len(data["PTI Signal"])), data["PTI Signal"])
        ax.grid(True)
        ax.set_xlabel("Time in s", fontsize=12)
        ax.set_ylabel("PTI Signal in rad", fontsize=12)
        self.tab_control.add(self.tab_pti, text="PTI Signal")
        return fig

    def plot_root_mean_square_cartesian(self, file_name):
        data = pd.read_csv(file_name)
        fig = Figure((2, 9), dpi=100)
        ax = fig.add_subplot()
        for i in range(1, 4):
            ax.plot(range(len(data["RMS CH1"])), data[f"RMS CH{i}"], label=f"Detector {i}")
        ax.legend(fontsize=12)
        ax.grid(True)
        ax.set_xlabel("Time in s", fontsize=12)
        ax.set_ylabel("Root Mean Square in V", fontsize=12)
        ax.legend(fontsize=12)
        self.tab_control.add(self.tab_root_mean_square, text="Root Mean Square")
        return fig

    def plot_response_phases(self, file_name):
        data = pd.read_csv(file_name)
        fig = Figure((2, 9), dpi=100)
        ax = fig.add_subplot()
        for i in range(1, 4):
            ax.plot(range(len(data["Response Phase CH1"])), data[f"Response Phase CH{i}"], label=f"Detector {i}")
        ax.legend(fontsize=12)
        ax.grid(True)
        ax.set_xlabel("Time in s", fontsize=12)
        ax.set_ylabel("Response Phase in rad", fontsize=12)
        ax.legend(fontsize=12)
        self.tab_control.add(self.tab_response_phase, text="Response Phase")
        return fig

    def plot_demodulated_signal(self, file_name):
        data = pd.read_csv(file_name)
        fig = Figure((2, 9), dpi=100)
        ax = fig.add_subplot()
        for i in range(1, 4):
            ax.plot(range(len(data["Demodulated Signal 1"])), data[f"Demodulated Signal {i}"], label=f"Detector {i}")
        ax.legend(fontsize=12)
        ax.grid(True)
        ax.set_xlabel("Time in s", fontsize=12)
        ax.set_ylabel("Demodulated Signal in V", fontsize=12)
        ax.legend(fontsize=12)
        self.tab_control.add(self.tab_demodulated_signal, text="Demodulated Signal")
        return fig

    def plot_interferometric_phase(self, file_name):
        data = pd.read_csv(file_name)
        fig = Figure((2, 9), dpi=100)
        ax = fig.add_subplot()
        ax.plot(range(len(data["Interferometric Phase"])), data["Interferometric Phase"])
        ax.grid(True)
        ax.set_xlabel("Time in s", fontsize=12)
        ax.set_ylabel("Interferometric Phase in rad", fontsize=12)
        self.tab_control.add(self.tab_interferometric_phase, text="Interferometric Phase")
        return fig

    def create_plot(self, tab, fig):
        self.canvas = FigureCanvasTkAgg(fig, master=tab)
        self.canvas.get_tk_widget().pack()
        self.canvas.draw()
        self.plot = self.canvas.get_tk_widget().pack(side=tkinter.TOP, fill=tkinter.BOTH, expand=1)
        toolbar = NavigationToolbar2Tk(self.canvas, tab)
        toolbar.update()
        self.canvas.get_tk_widget().pack(side=tkinter.TOP, fill=tkinter.BOTH, expand=1)

    def draw_plots(self, program):
        if program == "Decimation":
            fig = self.plot_dc("Decimation.csv")
            self.create_plot(self.tab_dc, fig)
            fig = self.plot_root_mean_square_cartesian("Decimation.csv")
            self.create_plot(self.tab_root_mean_square, fig)
            fig = self.plot_response_phases("Decimation.csv")
            self.create_plot(self.tab_response_phase, fig)
        if program == "PTI_Inversion":
            fig = self.plot_pti_signal("PTI_Inversion.csv")
            self.create_plot(self.tab_pti, fig)
            #fig = self.plot_demodulated_signal("PTI_Inversion.csv")
            #self.create_plot(self.tab_demodulated_signal, fig)
            fig = self.plot_interferometric_phase("PTI_Inversion.csv")
            self.create_plot(self.tab_interferometric_phase, fig)
        self.tab_control.pack(expand=True)
