import pandas as pd
from matplotlib import pyplot as plt
import numpy as np


data = pd.read_csv("Decimation.csv")

#plt.plot(range(len(data["DC1"])), np.sqrt(data["X1"] ** 2 + data["Y1"] ** 2))
#plt.plot(range(len(data["DC1"])), np.sqrt(data["X2"] ** 2 + data["Y2"] ** 2))
#plt.plot(range(len(data["DC1"])), np.sqrt(data["X3"] ** 2 + data["Y3"] ** 2))

plt.plot(range(len(data["DC1"])), data["I"])
plt.plot(range(len(data["DC1"])), data["Q"])
#plt.plot(range(len(data["DC1"])), data["DC3"])
plt.grid()
plt.xlabel("Time in s", fontsize=12)
plt.ylabel("Photo Detector Voltage in V", fontsize=12)
plt.show()
