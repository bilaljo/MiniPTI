import time
import pandas as pd
import os
import logging
from decimation import Decimation


def decimate(file, outputfile):
    """
    Applies the Noise-Reduction Algorithm, Decimation and Lock-In-Amplifier on binary data of given
    filename.

    Every iteration writes the results

    :param file: str
        The file name of the binary raw data.
    :param outputfile: str
        The filename of the output file for the results.
    :return: None
    """
    start = time.process_time()
    decimation = Decimation(file_name=file)
    if decimation.file is None:
        logging.error("The file does not exist.")
        return
    if os.path.exists(outputfile):
        os.remove(outputfile)
    elements = 1800
    pd.DataFrame()
    for i in range(elements):
        decimation.read_data()
        decimation.calucalte_dc()
        decimation.common_mode_noise_reduction()
        decimation.lock_in_amplifier()
        dc = decimation.dc_down_sampled
        x = decimation.ac_x
        y = decimation.ac_y
        pd.DataFrame({"X1": x[0], "X2": x[0], "X3": x[2],
                      "Y1": y[0], "Y2": x[0], "Y3": y[2],
                      "DC1": dc[0], "DC2": dc[1], "DC3": dc[2]},
                     index=[0]
                     ).to_csv(outputfile, mode="a", header=not os.path.exists(outputfile))
    decimation.file.close()
    print(time.process_time() - start)
