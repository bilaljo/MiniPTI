import tkinter as tk
from tkinter import ttk

from mode import Mode


class Theme:
    theme = "dark"

    root = None

    @staticmethod
    def set_theme(event=None):
        Theme.theme = "dark" if Theme.theme == "light" else "light"
        Theme.root.tk.call("set_theme", Theme.theme)


def main():
    root = tk.Tk()
    #Theme.root = root
    root.tk.call("source", "azure.tcl")
    root.tk.call("set_theme", "light")
    #root.bind("<F1>", Theme.set_theme)

    mode_frame = ttk.LabelFrame(root, text="Mode", padding=(20, 10))
    mode_frame.grid(row=2, column=0, padx=(20, 10), pady=10, sticky="nsew")
    live_button = tk.Radiobutton(mode_frame, text="Live", command="", value=1)
    offline_button = tk.Radiobutton(mode_frame, text="Offline", command="", value=2)
    live_button.grid(row=2, column=0, sticky="nsew")
    offline_button.grid(row=3, column=0)
    root.mainloop()


if __name__ == "__main__":
    main()
