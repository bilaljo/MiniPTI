import pandas as pd
import os
from pti.decimation import Decimation


def decimate(file="../pti/280422.bin", outputfile="Decimation.csv", live=False):
    """
    Applies the Noise-Reduction Algorithm, Decimation and Lock-In-Amplifier on binary data of given
    filename.
    Test
    Every iteration writes the results

    :param file: str
        The file name of the binary raw data.
    :param outputfile: str
        The filename of the output file for the results.
    :param live: bool
        If true the function returns in every call the result.
    :return: dict if live is true else None
    """
    decimation = Decimation(file_name=file)
    if os.path.exists(outputfile):
        os.remove(outputfile)
    while True:
        while not decimation.eof:
            decimation.read_data()
            decimation.calucalte_dc()
            decimation.common_mode_noise_reduction()
            decimation.lock_in_amplifier()
            root_mean_square, response_phase = decimation.get_lock_in_values()
            dc = decimation.dc_down_sampled
            pd.DataFrame({"RMS CH1": root_mean_square[0], "Response Phase CH1": response_phase[0],
                          "RMS CH2": root_mean_square[1], "Response Phase CH2": response_phase[1],
                          "RMS CH3": root_mean_square[2], "Response Phase CH3": response_phase[2],
                          "DC CH1": dc[0], "DC CH2": dc[1], "DC CH3": dc[2]},
                         index=[0]
                         ).to_csv(outputfile, mode="a", header=not os.path.exists(outputfile))
            if live:
                yield {"DC": decimation.dc_down_sampled, "RMS": root_mean_square, "Lock-In Phase": response_phase}
        if not live:
            break
    decimation.file.close()
