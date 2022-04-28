from Decimation import Decimation
import numpy as np


def main():
    decimation = Decimation(file_name="data.bin")
    try:
        with open("Decimation.csv", "w") as csv:
            csv.write("DC1,DC2,DC3,X1,Y1,X2,Y2,X3,Y3,I,Q\n")
            for i in range(1):
                decimation.read_data()
                decimation.calucalte_dc()
                decimation.common_mode_noise_reduction()
                decimation.lock_in_amplifier()
                for j in decimation.in_phase:
                    csv.write(str(j))
                    csv.write(",")
                for j in decimation.quadratur:
                    csv.write(str(j))
                    csv.write(",")
                for channel in range(3):
                    csv.write(str(decimation.dc_down_sampled[channel]))
                    csv.write(",")
                    csv.write(str(decimation.ac_x[channel]))
                    csv.write(",")
                    csv.write(str(decimation.ac_y[channel]))
                    csv.write(",")
                csv.write("\n")
                csv.flush()
    finally:
        if decimation.file is not None:
            decimation.file.close()


if __name__ == "__main__":
    main()
