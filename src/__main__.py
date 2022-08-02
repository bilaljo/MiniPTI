import tkinter as tk

import sv_ttk

from gui.action import Action
from gui.init_tab_frames import init_tab_frames
from gui.settings import Settings
from gui.tabs import Tabs


def main():
    root = tk.Tk()
    sv_ttk.use_light_theme()
    root.title("Mini PTI")

    settings = Settings()
    settings_frame = Tabs(root)
    phase_plot_frame = Tabs(root)
    pti_plot_frame = Tabs(root)
    dc_plot_frame = Tabs(root)
    output_phase_plot = Tabs(root)

    settings_frame.set_tab_frame()
    settings_frame.create_tab(text="Settings")
    dc_plot_frame.create_tab(text="DC Intensities")
    phase_plot_frame.create_tab(text="Interferometric Phase")
    pti_plot_frame.create_tab(text="PTI Signal")
    output_phase_plot.create_tab(text="Output Phases")

    actions = Action(settings=settings, dc_frame=dc_plot_frame.tab, phase_frame=phase_plot_frame.tab,
                     pti_frame=pti_plot_frame.tab, output_phases_frame=output_phase_plot.tab)

    init_tab_frames(actions, settings, settings_frame)

    root.protocol("WM_DELETE_WINDOW", actions.on_close(root))
    root.mainloop()


if __name__ == "__main__":
    main()
