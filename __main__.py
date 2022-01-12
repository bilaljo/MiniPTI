from DCSignal import DCSignal
from ACSignal import ACSignal
import pandas as pd


def main():
    DC_signals = pd.read("DC.csv")
    AC_signals = pd.read("AC.csv")
    I_DC = [DCSignal(), DCSignal(), DCSignal()]
    I_AC = [ACSignal(), ACSignal(), ACSignal()]
    for DC in I_DC:
        DC.scale_intensity()
    for AC in I_AC:
        AC.scale_intensity()


if __name__ == "__main__":
    main()
