import pandas as pd
from matplotlib import pyplot as plt
import numpy as np


data = pd.read_csv("PTI_Inversion.csv")

plt.plot(range(len(data["PTI Signal"])), data["Interferometric Phase"])
#plt.plot(range(len(data["PTI Signal"])), data["PTI Signal"] * 1e6)
plt.grid()
plt.xlabel("Time in s", fontsize=12)
plt.ylabel("Photo Detector Voltage in V", fontsize=12)
plt.show()
