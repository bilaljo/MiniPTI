from MainWindow import MainWindow
from SubMenu import SubMenu
import platform


def main():
    main_window = MainWindow(title="Passepartout")
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

    lock_in_menu.add_menu_options(menu_name="Decimation", label="Open file...", command=lock_in_menu.file_dialog)
    lock_in_menu.add_menu_options(menu_name="Decimation", label="Run", command=lock_in_menu.execute)
    pti_inversion_menu.add_menu_options(menu_name="PTI Inversion", label="Open file...",
                                        command=pti_inversion_menu.file_dialog)
    pti_inversion_menu.add_menu_options(menu_name="PTI Inversion", label="Run", command=pti_inversion_menu.execute)
    phase_scan_menu.add_menu_options(menu_name="Phase Scan", label="Open file...", command=phase_scan_menu.file_dialog)
    phase_scan_menu.add_menu_options(menu_name="Phase Scan", label="Run", command=phase_scan_menu.execute)

    response_phases.add_menu_options(menu_name="Set Response Phases", label="Detector 1",
                                     command=response_phases.set_response_phases1)
    response_phases.add_menu_options(menu_name="Set Response Phases", label="Detector 2",
                                     command=response_phases.set_response_phases2)
    response_phases.add_menu_options(menu_name="Set Response Phases", label="Detector 3",
                                     command=response_phases.set_response_phases3)

    main_window.root.mainloop()


if __name__ == "__main__":
    main()
