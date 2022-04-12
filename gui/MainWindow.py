import tkinter


class MainWindow:
    def __init__(self, title):
        self.default_height = 200
        self.default_width = 200
        self.root = tkinter.Tk()
        self.root.title(title)
        self.menubar = tkinter.Menu(self.root)
        self.menus = {}
        self.file = None
        self.name = None
        self.config = None

    def create_menu_element(self, menu_name):
        self.root.config(menu=self.menubar)
        self.menus[menu_name] = tkinter.Menu(self.menubar, tearoff=False)
        self.menubar.add_cascade(label=menu_name, menu=self.menus[menu_name])

