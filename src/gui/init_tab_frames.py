from tkinter import ttk


def init_tab_frames(actions, settings, settings_frame):
    def create_button(frame, text, action):
        button = ttk.Button(master=frame, text=text, command=action)
        button.pack(side="left", padx=10, pady=10)
        return button

    config_frame = settings_frame.set_frame("Configuration")
    settings.setup_config(config_frame)
    create_button(frame=config_frame, text="Save Config", action=settings.save_config)
    create_button(frame=config_frame, text="Load Config", action=settings.load_config)

    path_frame = settings_frame.set_frame("File Paths")
    create_button(frame=path_frame, text="Decimation", action=actions.set_file_path("Decimation"))
    create_button(frame=path_frame, text="Inversion", action=actions.set_file_path("Inversion"))
    create_button(frame=path_frame, text="Phase Scan", action=actions.set_file_path("Phase Scan"))

    offline_frame = settings_frame.set_frame("Offline")
    create_button(frame=offline_frame, text="Decimation", action=actions.calculate_decimation)
    create_button(frame=offline_frame, text="Inversion", action=actions.calculate_inversion)
    create_button(frame=offline_frame, text="Phase Scan", action=actions.scan)

    plot_frame = settings_frame.set_frame("Plotting")
    create_button(frame=plot_frame, text="Decimation", action=actions.plot_dc)
    create_button(frame=plot_frame, text="Inversion", action=actions.plot_inversion)
    create_button(frame=plot_frame, text="Phase Scan", action=actions.scan)

    online_frame = settings_frame.set_frame("Live")
    create_button(frame=online_frame, text="Run", action=actions.live)
    create_button(frame=online_frame, text="Destination Folder", action=actions.set_live_path)
