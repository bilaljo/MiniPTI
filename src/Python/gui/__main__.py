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

    def setup_tree(self, settings_frame):
        self.tree = ttk.Treeview(settings_frame, columns=("Configuration", "Value"), show="tree",)
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

    def set_theme(self, event):
        self.theme = "dark" if self.theme == "light" else "light"
        self.parent.tk.call("set_theme", self.theme)


def main():
    root = tk.Tk()
    root.title("Mini PTI")
    root.tk.call("source", "azure.tcl")
    root.tk.call("set_theme", "light")
    main_window = MainWindow(root)

    settings_frame = tk.Frame()
    settings_frame.pack(side="left")

    main_window.setup_tree(settings_frame)

    phase_scan = ttk.LabelFrame(master=settings_frame, text="File Paths", padding=(20, 10))
    phase_scan.pack(side="top", anchor="nw", expand=True, padx=10, pady=10)

    phase_scan_button = ttk.Button(phase_scan, text="Phase Scan")
    phase_scan_button.pack(side="left", anchor="nw", padx=10, pady=10)

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
    programms_online.pack(side="top", anchor="nw",  padx=10, pady=10, expand=True)

    run_button = ttk.Button(programms_online, text="Run")
    run_button.pack(side="left", anchor="nw", padx=10, pady=10)

    stop_button = ttk.Button(programms_online, text="Stop")
    stop_button.pack(side="left", anchor="nw", padx=10, pady=10)


    plot_frame = tk.Frame()
    plot_frame.pack(side=tk.LEFT)

    fig = plt.figure()

    dc_plot = fig.add_subplot(321)
    phase_plot = fig.add_subplot(323)
    pti_plot = fig.add_subplot(325)

    dc_plot.grid()
    phase_plot.grid()
    pti_plot.grid()

    output_phase_1 = fig.add_subplot(222)
    output_phase_2 = fig.add_subplot(224)

    canvas = FigureCanvasTkAgg(fig, master=root)
    canvas.draw()
    canvas.get_tk_widget().pack(side="top", fill=tk.BOTH, expand=True)

    root.bind("<F1>", main_window.set_theme)
    root.mainloop()


if __name__ == "__main__":
    main()
