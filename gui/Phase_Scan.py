import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import (
    FigureCanvasTkAgg, NavigationToolbar2Tk)
from tkinter import ttk
import tkinter
import tkinter as tk


class Plotting:
    def __init__(self, main_window):
        self.tab_control = ttk.Notebook(main_window)
        self.tab_control.pack(expand=True)
        self.tab_dc = ttk.Frame(self.tab_control)
        self.tab_qudratur = ttk.Frame(self.tab_control)
        self.tab_in_phase = ttk.Frame(self.tab_control)
        self.tab_pti = ttk.Frame(self.tab_control)
        style = ttk.Style(main_window)
        self.canvas = None
        style.configure('TNotebook.Tab', width=main_window.winfo_screenwidth(), height=main_window.winfo_height())

    def plot_dc(self, file_name):
        data = pd.read_csv(file_name)
        fig, ax = plt.subplots()
        for i in range(1, 4):
            ax.plot(range(len(data["DC1"])), data[f"DC{i}"], label=f"DC{i}")
            plt.legend()
            plt.grid(True)
            plt.xlabel("Time in s", fontsize=12)
            plt.ylabel("Photo Detector Voltage in V", fontsize=12)
            plt.legend(fontsize=12)
        self.tab_dc.pack(fill='both', expand=True)
        self.tab_control.add(self.tab_dc, text="DC Detector Voltages")
        return fig

    def plot_in_phase_component(self, file_name):
        data = pd.read_csv(file_name)
        fig, ax = plt.subplots()
        for i in range(1, 4):
            ax.plot(range(len(data["X1"])), data[f"X{i}"], label=f"X{i}")
            plt.legend()
            plt.grid(True)
            plt.xlabel("Time in s", fontsize=12)
            plt.ylabel("In-Phase Component in V", fontsize=12)
            plt.legend(fontsize=12)
        self.tab_control.add(self.tab_in_phase, text="AC In-Phase Component")
        return fig

    def plot_quadratur_component(self, file_name):
        data = pd.read_csv(file_name)
        fig, ax = plt.subplots()
        for i in range(1, 4):
            ax.plot(range(len(data["Y1"])), data[f"Y{i}"], label=f"Y{i}")
            plt.legend()
            plt.grid(True)
            plt.xlabel("Time in s", fontsize=12)
            plt.ylabel("Quadratur Component in V", fontsize=12)
        plt.legend(fontsize=12)
        self.tab_control.add(self.tab_qudratur, text="AC Quadratur Component")
        return fig

    def plot_pti_signal(self, file_name):
        data = pd.read_csv(file_name)
        fig, ax = plt.subplots()
        ax.plot(range(len(data["PTI"])), data["PTI"])
        plt.grid(True)
        plt.xlabel("Time in s", fontsize=12)
        plt.ylabel("PTI Signal in rad", fontsize=12)
        self.tab_control.add(self.tab_pti, text="PTI Signal")
        return fig

    def remove_plots(self):
        for item in self.canvas.get_tk_widget().find_all():
            self.canvas.get_tk_widget().delete(item)

    def create_plot(self, tab, fig):
        self.canvas = FigureCanvasTkAgg(fig, master=tab)
        self.remove_plots()
        self.canvas.get_tk_widget().pack()
        self.canvas.draw()
        self.canvas.get_tk_widget().pack(side=tkinter.TOP, fill=tkinter.BOTH, expand=1)

        toolbar = NavigationToolbar2Tk(self.canvas, tab)
        toolbar.update()
        self.canvas.get_tk_widget().pack(side=tkinter.TOP, fill=tkinter.BOTH, expand=1)

    def draw_plots(self, program):
        if program == "PTI_Inversion" or program == "PTI_Inversion.exe":
            fig = self.plot_dc("data.csv")
            self.create_plot(self.tab_dc, fig)
            fig = self.plot_in_phase_component("data.csv")
            self.create_plot(self.tab_in_phase, fig)
            fig = self.plot_quadratur_component("data.csv")
            self.create_plot(self.tab_qudratur, fig)
            self.tab_control.pack(expand=True)
            fig = self.plot_pti_signal("output.csv")
            self.create_plot(self.tab_pti, fig)
            self.tab_control.pack(expand=True)
