import tkinter
import platform


class MainWindow:
    def __init__(self, title, background):
        self.default_height = 600
        self.default_width = 600
        self.root = tkinter.Tk()
        self.root.title(title)
        self.menubar = tkinter.Menu(self.root)
        self.menus = {}
        self.file = None
        self.name = None
        self.config = None
        self.background = background
        if platform.system() == "Windows":
            self.root.configure(background=self.background)

    def create_menu_element(self, menu_name):
        self.root.config(menu=self.menubar, height=self.default_height, width=self.default_width)
        self.menus[menu_name] = tkinter.Menu(self.menubar, tearoff=False)
        self.menubar.add_cascade(label=menu_name, menu=self.menus[menu_name])

