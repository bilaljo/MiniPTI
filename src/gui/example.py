import tkinter as tk
from tkinter import ttk


class App:
    def __init__(self, parent):
        self.root = parent

if __name__ == "__main__":
    root = tk.Tk()
    root.title("")

    # Simply set the theme
    root.tk.call("source", "azure.tcl")
    root.tk.call("set_theme", "light")

    app = App(root)


    # Set a minsize for the window, and place it in the middle


    root.mainloop()
