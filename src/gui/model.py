import threading
from collections import deque

import numpy as np

from pti.pti import PTI


class Model:
    def __init__(self, queue_size=1000):
        self.decimation_data = {"DC CH1": deque(maxlen=queue_size),
                                "DC CH2": deque(maxlen=queue_size),
                                "DC CH3": deque(maxlen=queue_size)}
        self.pti_values = {"Interferometric Phase": deque(maxlen=queue_size),
                           "PTI Signal": deque(maxlen=queue_size)}
        self.pti_signal_mean = deque(maxlen=queue_size)
        self.pti_signal_mean_queue = deque(maxlen=60)
        self.current_time = 0
        self.time = deque(maxlen=queue_size)
        self.pti = PTI()
        self.decimation_path = ""
        self.settings_path = "./settings.csv"
        self.destination_folder = ""

    def calculate_decimation(self, decimation_path):
        decimate_thread = threading.Thread(target=self.pti.decimate, daemon=True, args=[decimation_path])
        decimate_thread.start()

    def calculate_characitersation(self, dc_file_path, inversion_path="", use_inversion=False, settings_path=""):
        self.pti.characterise(dc_signals_path=dc_file_path, inversion_path=inversion_path, use_inversion=use_inversion,
                              settings_path=settings_path)

    def calculate_inversion(self, settings_path, inversion_path):
        self.pti.init_inversion(settings_path)
        self.pti.invert(inversion_path)

    def live_calculation(self):
        self.pti.pti(self.decimation_path, self.settings_path, self.destination_folder)
        self.decimation_data["DC CH1"].append(self.pti.decimation.dc_down_sampled[0])
        self.decimation_data["DC CH2"].append(self.pti.decimation.dc_down_sampled[1])
        self.decimation_data["DC CH3"].append(self.pti.decimation.dc_down_sampled[2])
        self.pti_values["Interferometric Phase"].append(self.pti.inversion.interferometric_phase)
        self.pti_values["PTI Signal"].append(self.pti.inversion.pti_signal * (-1e6))
        self.pti_signal_mean_queue.append(self.pti.inversion.pti_signal * (-1e6))
        self.pti_signal_mean.append(np.mean(self.pti_signal_mean_queue))
        self.current_time += 1
        self.time.append(self.current_time)
