import tkinter
from MainWindow import MainWindow
from SubMenu import SubMenu
import platform


def main():
    main_window = MainWindow(title="Passepartout", background="white")
    if platform.system() == "Windows":
        icon = tkinter.PhotoImage(file=r"icons\fhnw.png")
    else:
        icon = tkinter.PhotoImage(file="icons/fhnw.png")
    main_window.root.iconphoto(False, icon)
    if platform.system() == "Windows":  # *.exe files
        lock_in_menu = SubMenu(window=main_window, menu_name="Lock in Amplifier", program="Decimation.exe")
        phase_scan_menu = SubMenu(window=main_window, menu_name="Phase Scan", program="Phase_Scan.exe")
        pti_inversion_menu = SubMenu(window=main_window, menu_name="PTI Inversion", program="PTI_Inversion.exe")
    else:
        lock_in_menu = SubMenu(window=main_window, menu_name="Lock in Amplifier", program="Decimation")
        phase_scan_menu = SubMenu(window=main_window, menu_name="Phase Scan", program="Phase_Scan")
        pti_inversion_menu = SubMenu(window=main_window, menu_name="PTI Inversion", program="PTI_Inversion")
    response_phases = SubMenu(window=main_window, menu_name="Set Response Phases", program="")

    main_window.create_menu_element("Phase Scan")
    main_window.create_menu_element("Decimation")
    main_window.create_menu_element("PTI Inversion")
    main_window.create_menu_element("Set Response Phases")
    main_window.create_menu_element("About")

    lock_in_menu.add_menu_options(menu_name="Decimation", label="Open file...", command=lock_in_menu.file_dialog)
    lock_in_menu.add_menu_options(menu_name="Decimation", label="Run", command=lock_in_menu.execute)
    pti_inversion_menu.add_menu_options(menu_name="PTI Inversion", label="Open file...",
                                        command=pti_inversion_menu.file_dialog)
    main_window.menus["PTI Inversion"].add_checkbutton(label="Verbose output", variable=pti_inversion_menu.verbose,
                                                       command=pti_inversion_menu.verbose_output)

    pti_inversion_menu.add_menu_options(menu_name="PTI Inversion", label="Run", command=pti_inversion_menu.execute)
    phase_scan_menu.add_menu_options(menu_name="Phase Scan", label="Open file...", command=phase_scan_menu.file_dialog)
    phase_scan_menu.add_menu_options(menu_name="Phase Scan", label="Run", command=phase_scan_menu.execute)

    response_phases.add_menu_options(menu_name="Set Response Phases", label="Detector 1",
                                     command=response_phases.set_response_phases1)
    response_phases.add_menu_options(menu_name="Set Response Phases", label="Detector 2",
                                     command=response_phases.set_response_phases2)
    response_phases.add_menu_options(menu_name="Set Response Phases", label="Detector 3",
                                     command=response_phases.set_response_phases3)


    top = tkinter.Frame(main_window.root)
    if platform.system() == "Windows":
        top.configure(background=main_window.background)
    top.pack(side=tkinter.TOP)
    if platform.system() == "Windows":
        pause_picture = tkinter.PhotoImage(file=r"icons\pause.png")
        play_picture = tkinter.PhotoImage(file=r"icons\play.png")
        stop_picture = tkinter.PhotoImage(file=r"icons\stop.png")
    else:
        pause_picture = tkinter.PhotoImage(file="icons/pause.png")
        play_picture = tkinter.PhotoImage(file="icons/play.png")
        stop_picture = tkinter.PhotoImage(file="icons/stop.png")

    play_button = tkinter.Button(main_window.root, command="")
    play_button.config(image=play_picture, height=25, width=25, highlightthickness=0, bd=0)
    play_button.pack(in_=top, side=tkinter.LEFT)

    pause_button = tkinter.Button(main_window.root, command="",)
    pause_button.config(image=pause_picture, height=25, width=25, highlightthickness=0, bd=0)
    pause_button.pack(in_=top, side=tkinter.LEFT)

    stop_button = tkinter.Button(main_window.root, command="")
    stop_button.config(image=stop_picture, height=25, width=25, highlightthickness=0, bd=0)
    stop_button.pack(in_=top, side=tkinter.LEFT)

    if platform.system() == "Windows":
        play_button.configure(background=main_window.background)
        pause_button.configure(background=main_window.background)
        stop_button.configure(background=main_window.background)

    main_window.root.minsize(500, 200)
    main_window.root.mainloop()


if __name__ == "__main__":
    main()
