import sv_ttk

from gui.controller import Controller


def main():
    controller = Controller()
    sv_ttk.use_light_theme()
    controller.view.mainloop()


if __name__ == "__main__":
    main()
