from pti.inversion import Inversion
from pti.decimate import decimate
import numpy as np
import pandas as pd


def invert(file, outputfile, live=False):
    while True:
        if not live:
            data = pd.read_csv(file)
            dc_signals = np.array([data[f"DC CH{i}"] for i in range(1, 4)])
            root_mean_squares = np.array([data[f"RMS CH{i}"] for i in range(1, 4)])
            response_phases = np.array([data[f"Response Phase CH{i}"] for i in range(1, 4)])
        else:
            signals = decimate(file, outputfile)
            dc_signals = signals["DC"]
            root_mean_squares = signals["RMS"]
            response_phases = signals["Response Phases"]
        inversion = Inversion(response_phases=np.array([-2.2, -2.2, -2.2]), signals=dc_signals)
        inversion.scale_data()
        interferometric_phase = inversion.get_interferometric_phase()
        inversion.calculate_pti_signal(root_mean_squares, response_phases)
        pd.DataFrame({"Interferometric Phase": interferometric_phase,
                      "PTI Signal": inversion.pti}).to_csv("PTI_Inversion.csv")
        if not live:
            break
