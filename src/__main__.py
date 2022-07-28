import tkinter as tk
from tkinter import ttk

import sv_ttk

from gui.action import Action
from gui.button import create_button
from pti.decimation import Decimation
from pti.inversion import Inversion
from pti.phase_scan import PhaseScan
from gui.settings import Settings
from gui.tabs import Tabs


def main():
    root = tk.Tk()
    sv_ttk.use_light_theme()
    root.title("Mini PTI")

    decimation = Decimation()
    inversion = Inversion()
    phase_scan = PhaseScan()
    settings = Settings()

    settings_frame = Tabs(root)
    settings_frame.set_tab_frame()
    settings_frame.create_tab(text="Settings")

    dc_plot_frame = Tabs(root)
    dc_plot_frame.create_tab(text="DC Intensities")

    phase_plot_frame = Tabs(root)
    phase_plot_frame.create_tab(text="Interferometric Phase")

    pti_plot_frame = Tabs(root)
    pti_plot_frame.create_tab(text="PTI Signal")

    actions = Action(decimation, inversion, phase_scan, dc_frame=dc_plot_frame.tab, phase_frame=phase_plot_frame.tab,
                     pti_frame=pti_plot_frame.tab)

    config_frame = ttk.LabelFrame(master=settings_frame.tab, text="Configuration", padding=(20, 10))
    config_frame.pack(side="top", anchor="nw", padx=10, pady=10, expand=True, fill=tk.BOTH)
    settings.setup_config(config_frame)
    create_button(frame=config_frame, text="Save Config", action=settings.save_config)
    create_button(frame=config_frame, text="Load Config", action=settings.load_config)

    path_frame = ttk.LabelFrame(master=settings_frame.tab, text="File Paths", padding=(20, 10))
    path_frame.pack(side="top", anchor="nw", padx=10, pady=10, expand=True, fill=tk.BOTH)
    create_button(frame=path_frame, text="Decimation", action=actions.set_file_path("Decimation"))
    create_button(frame=path_frame, text="Inversion", action=actions.set_file_path("Inversion"))
    create_button(frame=path_frame, text="Phase Scan", action=actions.set_file_path("Phase Scan"))

    offline_frame = ttk.LabelFrame(master=settings_frame.tab, text="Offline", padding=(20, 10))
    offline_frame.pack(side="top", anchor="nw", padx=10, pady=10, expand=True, fill=tk.BOTH)

    create_button(frame=offline_frame, text="Decimation", action=actions.decimate)
    create_button(frame=offline_frame, text="Inversion", action=actions.invert)
    create_button(frame=offline_frame, text="Phase Scan", action=actions.scan)

    plot_frame = ttk.LabelFrame(master=settings_frame.tab, text="Plotting", padding=(20, 10))
    plot_frame.pack(side="top", anchor="nw", padx=10, pady=10, expand=True, fill=tk.BOTH)
    create_button(frame=plot_frame, text="Decimation", action=actions.plot_decimation)
    create_button(frame=plot_frame, text="Inversion", action=actions.plot_inversion)
    create_button(frame=plot_frame, text="Phase Scan", action=actions.scan)

    online_frame = ttk.LabelFrame(master=settings_frame.tab, text="Live")
    online_frame.pack(side="top", anchor="nw", padx=10, pady=10, expand=True, fill=tk.BOTH)
    create_button(frame=online_frame, text="Run", action=actions.live)
    create_button(frame=online_frame, text="Destination Folder", action=actions.set_live_path)

    root.mainloop()


if __name__ == "__main__":
    main()
