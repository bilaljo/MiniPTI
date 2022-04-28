from Decimation import Decimation
import numpy as np


def main():
    decimation = Decimation(file_name="data.bin")
    try:
        with open("Decimation.csv", "w") as csv:
            csv.write("i,DC1,DC2,DC3,X1,Y1,X2,Y2,X3,Y3")
        for i in range(500):
            decimation.read_data()
            decimation.calucalte_dc()
            decimation.common_mode_noise_reduction()
            decimation.lock_in_amplifier()
            for channel in range(3):
                csv.write(decimation.dc_down_sampled[channel])
                csv.write(",")
                csv.write(decimation.ac_x[channel])
                csv.write(",")
                csv.write(decimation.ac_y[channel])
                csv.write(",")
            csv.write("\n")
            csv.flush()
    finally:
        decimation.file.close()


if __name__ == "__main__":
    main()
