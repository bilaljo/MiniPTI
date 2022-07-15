from tkinter import ttk


class Button:
    def __init__(self, frame, text, action):
        self.button = ttk.Button(master=frame, text=text, command=action)
        self.button.pack(side="left", anchor="nw", padx=10, pady=10)
