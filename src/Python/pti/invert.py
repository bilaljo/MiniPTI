from pti.inversion import Inversion
from pti.decimate import decimate
import numpy as np
import pandas as pd


def invert(file, outputfile, response_phases, live=False):
    while True:
        if not live:
            data = pd.read_csv(file)
            dc_signals = np.array([data[f"DC CH{i}"] for i in range(1, 4)])
            root_mean_squares = np.array([data[f"RMS CH{i}"] for i in range(1, 4)])
            lock_in_phase = np.array([data[f"Response Phase CH{i}"] for i in range(1, 4)])
        else:
            signals = decimate(file, outputfile)
            dc_signals = signals["DC"]
            root_mean_squares = signals["RMS"]
            lock_in_phase = signals["Lock-In Phase"]
        inversion = Inversion(response_phases=response_phases, signals=dc_signals)
        inversion.scale_data()
        interferometric_phase = inversion.get_interferometric_phase()
        inversion.calculate_pti_signal(root_mean_squares, lock_in_phase)
        pd.DataFrame({"Interferometric Phase": interferometric_phase,
                      "PTI Signal": inversion.pti,
                      }).to_csv("PTI_Inversion.csv")
        if not live:
            break
