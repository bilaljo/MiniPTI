from tkinter import ttk


def create_button(frame, text, action):
    button = ttk.Button(master=frame, text=text, command=action)
    button.pack(side="left", padx=10, pady=10)
    return button
