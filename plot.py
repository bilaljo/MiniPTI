import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy import signal


data = pd.read_csv("Decimation_Comercial.csv")[["DC CH1", "DC CH2", "DC CH3"]].to_numpy().T

#phases = np.linspace(0, 2.5 * np.pi, 1000)
#output_phases = np.array([0, 0.5, 0.9]) * 2 * np.pi
#intensities = data#np.array([np.cos(phases - output_phases[i]) for i in range(3)]).T + np.random.normal()
#print("Ideal: ", np.rad2deg(output_phases))
#period = (np.argmax(intensities, axis=1) - np.argmin(intensities, axis=1))[1] * 2
#print("Ist:   ", (np.argmax(intensities, axis=1) - 1235) / period * 360)

#maximum = np.mean(np.argsort(data[0])[-5:])
#minimum = np.mean(np.argsort(data[0][5:]))
#print(maximum / (maximum - minimum) * 180 % 360)
#maximum = np.mean(np.argsort(data[1])[-5:])
#minimum = np.mean(np.argsort(data[1][5:]))
#print(maximum / (maximum - minimum) * 180 % 360)
#print(minimum, maximum)
#plt.plot(data[1])
#plt.show()

#print(data[1][np.abs(data - np.max(data)) < 0.01])
print(signal.argrelmin(data[0], mode="wrap"))