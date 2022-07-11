import tkinter as tk
from tkinter import ttk
from matplotlib import pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
from matplotlib.backend_bases import key_press_handler
from matplotlib.figure import Figure


class MainWindow(ttk.Frame):
    def __init__(self, parent):
        super().__init__()
        self.mode_frame = None
        self.offline = None
        self.live = tk.IntVar()
        self.live_button = None
        self.offline = self.live
        self.offline_button = None
        self.theme = "light"
        self.parent = parent
        self.tree = None

    def setup_radio_buttons(self):
        self.mode_frame = ttk.LabelFrame(self, text="Mode", padding=(20, 10))
        self.mode_frame.grid(row=0, column=0, padx=(0, 10), pady=10, sticky="nsew")
        self.offline_button = ttk.Radiobutton(self.mode_frame, text="Offline", variable=self.offline, value=1)
        self.offline_button.grid(row=0, column=0, padx=5, pady=10, sticky="nsew")
        self.live_button = ttk.Radiobutton(self.mode_frame, text="Live", variable=self.live, value=2)
        self.live_button.grid(row=1, column=0, padx=5, pady=10, sticky="nsew")

    def setup_tree(self, main_frame):
        self.tree = ttk.Treeview(columns=("Configuration", "Value"), show="tree")
        self.tree.column("#0", width=150, stretch=False)
        self.tree.column("#1", width=80, stretch=False)
        self.tree.pack(side="left", padx=10, pady=10, anchor="nw")

        output_phases = self.tree.insert("", "end", text='Output Phases', values=[], open=False)
        self.tree.insert(output_phases, "end", text='Detector 1', values=["0.00 rad"], open=False)
        self.tree.insert(output_phases, "end", text='Detector 2', values=[f"{1.85} rad"], open=False)
        self.tree.insert(output_phases, "end", text='Detector 3', values=[f"{3.75} rad"], open=False)

        contrasts = self.tree.insert("", "end", text='Contrasts', values=[], open=False)
        self.tree.insert(contrasts, "end", text='Detector 1', values=[f"{95.15} %"], open=False)
        self.tree.insert(contrasts, "end", text='Detector 2', values=[f"{95.15} %"], open=False)
        self.tree.insert(contrasts, "end", text='Detector 3', values=[f"{95.15} %"], open=False)

        response_phases = self.tree.insert("", "end", text='Response Phases', values=[], open=False)
        self.tree.insert(response_phases, "end", text='Detector 1', values=[f"{2.2} rad"], open=False)
        self.tree.insert(response_phases, "end", text='Detector 2', values=[f"{2.2} rad"], open=False)
        self.tree.insert(response_phases, "end", text='Detector 3', values=[f"{2.2} rad"], open=False)

    def set_theme(self, event):
        self.theme = "dark" if self.theme == "light" else "light"
        self.parent.tk.call("set_theme", self.theme)


def main():
    root = tk.Tk()
    root.tk.call("source", "azure.tcl")
    root.tk.call("set_theme", "light")
    main_window = MainWindow(root)
    main_window.setup_tree(root)

    fig_dc = plt.figure(figsize=(7, 10), dpi=100)
    ax1 = plt.subplot()
    ax1.set_title("DC Signals", fontsize=12)
    ax1.set_xticklabels([])
    ax1.grid()
    ax1.set_ylabel(r"$I_k$ [V]", fontsize=12)
    ax1.legend(["CH1", "CH2", "CH3"])

    fig_phi = plt.figure(figsize=(7, 10), dpi=100)
    ax2 = plt.subplot()
    ax2.set_title("Interferometric Phase", fontsize=12)
    ax2.set_xticklabels([])
    ax2.grid()
    ax2.set_ylabel(r"$\varphi$ [rad]", fontsize=12)
    """
    ax3.set_title("PTI Signal", fontsize=12)
    ax3.grid()
    ax3.set_xlabel("Time [s]", fontsize=12)
    ax3.set_ylabel(r"$\Delta \varphi$ [$10^{-6}$ rad]", fontsize=12)

    pti_plots = FigureCanvasTkAgg(fig, master=root)
    pti_plots.draw()
    pti_plots.get_tk_widget().pack(side="left")

    fig_phases = plt.figure(figsize=(7, 10), dpi=100)
    ax1 = plt.subplot(211)
    ax2 = plt.subplot(212)

    ax1.set_xticklabels([])
    ax1.set_title("Output Phase 2", fontsize=12)
    ax1.grid()
    ax1.set_xlabel(r"$\rho_2$ [rad]", fontsize=12)
    ax1.set_ylabel("Count", fontsize=12)

    ax2.set_title("Output Phase 3", fontsize=12)
    ax2.grid()
    ax2.set_xlabel(r"$\rho_3$ [rad]", fontsize=12)
    ax2.set_ylabel("Count", fontsize=12)
    """

    phase_scan = ttk.LabelFrame(text="File Paths", padding=(20, 10))
    phase_scan.pack(side="top", anchor="nw", padx=10, pady=10)

    """
    phase_scan_button = ttk.Button(phase_scan, text="Phase Scan")
    phase_scan_button.pack(side="top", anchor="nw", padx=10, pady=10)

    decimation_button = ttk.Button(phase_scan, text="Decimation")
    decimation_button.pack(side="top", anchor="nw", padx=10, pady=10)"""

    inversion_button = ttk.Button(phase_scan, text="PTI Inversion")
    inversion_button.pack(side="top", anchor="nw", padx=10, pady=10)

    canvas = FigureCanvasTkAgg(fig_dc, master=root)
    canvas.draw()
    canvas.get_tk_widget().pack(side="top")

    canvas = FigureCanvasTkAgg(fig_phi, master=root)
    canvas.draw()
    canvas.get_tk_widget().pack(side="top")

    root.bind("<F1>", main_window.set_theme)
    root.mainloop()


if __name__ == "__main__":
    main()
