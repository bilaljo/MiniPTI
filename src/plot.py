import matplotlib.pyplot as plt
import pandas as pd
import numpy as np


data = pd.read_csv("PTI_Inversion.csv")
plt.plot(range(len(data)), 2 * np.pi * np.ones(len(data)), label="$2\pi$")
plt.scatter(range(len(data)), data["Interferometric Phase"], label="Phase", s=2,
        color="green")
plt.grid()
plt.xlabel("Time [s]")
plt.ylabel(r"$\varphi$ [rad]")
plt.legend()
plt.show()
