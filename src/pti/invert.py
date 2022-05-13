from inversion import Inversion
from decimate import decimate
import numpy as np
import pandas as pd


def invert(file, outputfile, output_phases, live=False):
    signals = decimate(file, outputfile)
    while True:
        if not live:
            data = pd.read_csv(file)
            dc_signals = np.array([data[f"RMS CH{i}"] for i in range(1, 4)])
            root_mean_squares = np.array([data[f"RMS CH{i}"] for i in range(1, 4)])
            response_phases = np.array([data[f"Response Phase CH{i}"] for i in range(1, 4)])
        else:
            dc_signals = signals["DC"]
            root_mean_squares = signals["RMS"]
            response_phases = signals["Response Phases"]
        inversion = Inversion(response_phases=np.array([-2.2, -2.2, -2.2]), output_phases=output_phases,
                              signals=dc_signals)
        inversion.scale_data()
        interferometric_phase = inversion.get_interferometric_phase()
        inversion.set_max()
        inversion.set_min()
        inversion.calculate_pti_signal(root_mean_squares, response_phases)
        pd.DataFrame({"Interometric Phase": interferometric_phase,
                      "PTI Signal": inversion.pti}).to_csv("Phase.csv")
        if not live:
            break
