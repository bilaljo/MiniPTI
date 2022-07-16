import tkinter as tk
from tkinter import ttk

from action import Action
from button import Button
from pti.decimation import Decimation
from pti.inversion import Inversion
from pti.inversion import PhaseScan
from settings import Settings


def main():
    root = tk.Tk()
    root.style = ttk.Style()
    decimation = Decimation()
    inversion = Inversion()
    phase_scan = PhaseScan()
    settings = Settings()
    Settings.check_config_file()
    actions = Action(decimation, inversion, phase_scan)
    root.title("Mini PTI")
    root.tk.call("source", "gui/azure.tcl")
    root.tk.call("set_theme", "light")
    settings_frame = tk.Frame()
    settings_frame.pack(side="left", anchor="nw")
    settings.setup_tree(settings_frame)
    path_frame = ttk.LabelFrame(master=settings_frame, text="File Paths", padding=(20, 10))
    path_frame.pack(side="top", anchor="nw", padx=10, pady=10, expand=True, fill=tk.BOTH)
    Button(frame=path_frame, text="Decimation", action=actions.set_file_path("Decimation"))
    Button(frame=path_frame, text="Inversion", action=actions.set_file_path("Inversion"))
    Button(frame=path_frame, text="Phase Scan", action=actions.set_file_path("Phase Scan"))

    offline_frame = ttk.LabelFrame(master=settings_frame, text="Offline", padding=(20, 10))
    offline_frame.pack(side="top", anchor="nw", padx=10, pady=10, expand=True, fill=tk.BOTH)

    Button(frame=offline_frame, text="Decimation", action=actions.decimate)
    Button(frame=offline_frame, text="Inversion", action=actions.invert)
    Button(frame=offline_frame, text="Phase Scan", action=actions.scan)

    root.mainloop()


if __name__ == "__main__":
    main()
