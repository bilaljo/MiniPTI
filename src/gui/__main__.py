import tkinter as tk
from tkinter import ttk


class MainWindow(ttk.Frame):
    def __init__(self, parent):
        super().__init__()
        self.mode_frame = None
        self.offline = None
        self.live = tk.IntVar()
        self.live_button = None
        self.offline = self.live
        self.offline_button = None
        self.theme = "light"
        self.parent = parent
        self.setup()

    def setup(self):
        self.mode_frame = ttk.LabelFrame(self, text="Mode", padding=(20, 10))
        self.mode_frame.grid(row=2, column=0, padx=(20, 10), pady=10, sticky="nsew")

        self.offline_button = ttk.Radiobutton(self.mode_frame, text="Offline", variable=self.offline, value=1)
        self.offline_button.grid(row=0, column=0, padx=5, pady=10, sticky="nsew")
        self.live_button = ttk.Radiobutton(self.mode_frame, text="Live", variable=self.live, value=2)
        self.live_button.grid(row=1, column=0, padx=5, pady=10, sticky="nsew")

    def set_theme(self, event):
        self.theme = "dark" if self.theme == "light" else "light"
        self.parent.tk.call("set_theme", self.theme)


def main():
    root = tk.Tk()
    root.tk.call("source", "azure.tcl")
    root.tk.call("set_theme", "light")
    main_window = MainWindow(root)
    main_window.pack(fill="both", expand=True)
    root.bind("<F1>", main_window.set_theme)
    root.mainloop()


if __name__ == "__main__":
    main()
