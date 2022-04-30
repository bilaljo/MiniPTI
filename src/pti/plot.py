import pandas as pd
from matplotlib import pyplot as plt
import numpy as np


data = pd.read_csv("Decimation.csv")
plt.plot(range(len(data["DC1"])), data["X1"], label="Mean")
plt.legend()
plt.grid()
plt.show()
