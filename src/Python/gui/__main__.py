import tkinter as tk
from tkinter import ttk

from matplotlib import pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg


class MainWindow(ttk.Frame):
    def __init__(self, parent):
        super().__init__()
        self.parent = parent
        self.tree = None

    def setup_tree(self, settings_frame):
        self.tree = ttk.Treeview(settings_frame, columns=("Configuration", "Value"), show="tree", )
        self.tree.column("#0", width=150, stretch=False)
        self.tree.column("#1", width=80, stretch=False)
        self.tree.pack(side="top", padx=10, pady=10, fill=tk.Y)

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


def draw():
    root = tk.Tk()
    root.title("Mini PTI")
    root.tk.call("source", "azure.tcl")
    root.tk.call("set_theme", "light")
    main_window = MainWindow(root)

    settings_frame = tk.Frame()
    settings_frame.pack(side="left", anchor="nw")

    main_window.setup_tree(settings_frame)

    phase_scan = ttk.LabelFrame(master=settings_frame, text="File Paths", padding=(20, 10))
    phase_scan.pack(side="top", anchor="nw", expand=True, padx=10, pady=10)

    phase_scan_button.

    decimation_button = ttk.Button(phase_scan, text="Decimation")
    decimation_button.pack(side="left", anchor="nw", padx=10, pady=10)

    inversion_button = ttk.Button(phase_scan, text="PTI Inversion")
    inversion_button.pack(side="left", padx=10, pady=10, fill=tk.BOTH, expand=True)

    programms = ttk.LabelFrame(master=settings_frame, text="Offline", padding=(20, 10))
    programms.pack(side="top", anchor="nw", expand=True, padx=10, pady=10)

    phase_scan_button = ttk.Button(programms, text="Phase Scan")
    phase_scan_button.pack(side="left", padx=10, pady=10)

    decimation_button = ttk.Button(programms, text="Decimation")
    decimation_button.pack(side="left", anchor="nw", padx=10, pady=10)

    inversion_button = ttk.Button(programms, text="PTI Inversion")
    inversion_button.pack(side="left", padx=10, pady=10, anchor="nw", expand=True)

    programms_online = ttk.LabelFrame(master=settings_frame, text="Online", padding=(20, 10))
    programms_online.pack(side="top", anchor="nw", padx=10, pady=10, expand=True)

    run_button = ttk.Button(programms_online, text="Run")
    run_button.pack(side="left", anchor="nw", padx=10, pady=10)

    stop_button = ttk.Button(programms_online, text="Stop")
    stop_button.pack(side="left", anchor="nw", padx=10, pady=10)

    plot_frame = tk.Frame()
    plot_frame.pack(side=tk.LEFT, anchor="nw")

    fig = plt.figure()

    dc_plot = fig.add_subplot(321)
    phase_plot = fig.add_subplot(323)
    pti_plot = fig.add_subplot(325)

    dc_plot.get_xaxis().set_visible(False)
    phase_plot.get_xaxis().set_visible(False)

    dc_plot.grid()
    phase_plot.grid()
    pti_plot.grid()

    dc_plot.set_ylabel("$I_k$", fontsize=11)
    phase_plot.set_ylabel(r"$\varphi$ [rad]", fontsize=11)
    pti_plot.set_ylabel(r"$\Delta \varphi$ [rad]", fontsize=11)

    pti_plot.set_xlabel("Time [s]", fontsize=11)

    dc_plot.set_title("DC Signals", fontsize=11)
    phase_plot.set_title("Interferometric Phase", fontsize=11)
    pti_plot.set_title("PTI Signal", fontsize=11)

    output_phase_1 = fig.add_subplot(222)
    output_phase_2 = fig.add_subplot(224)

    output_phase_1.grid()
    output_phase_2.grid()

    output_phase_1.set_xlabel(r"$\rho_2$ [rad]", fontsize=11)
    output_phase_2.set_xlabel(r"$\rho_3$ [rad]", fontsize=11)

    output_phase_1.set_ylabel(r"Count", fontsize=11)
    output_phase_2.set_ylabel(r"Count", fontsize=11)

    output_phase_1.set_title("Output Phases", fontsize=11)

    canvas = FigureCanvasTkAgg(fig, master=root)
    canvas.draw()
    canvas.get_tk_widget().pack(side="top", fill=tk.BOTH, expand=True, anchor="nw")

    root.mainloop()


if __name__ == "__main__":
    draw()
