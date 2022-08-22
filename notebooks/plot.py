import matplotlib.pyplot as plt
import numpy as np


def detector_1(x): return 1 / 2 * (1 + np.cos(x))
def detector_2(x): return 1 / 2 * (1 - np.cos(x))

phi = np.linspace(0, 2 * np.pi, 1000)
plt.rc('text', usetex=True)
plt.rc('font', family='serif')
fig, ax = plt.subplots()
ax.plot(phi, detector_1(phi), label="Detector 1")
ax.plot(phi, detector_2(phi), label="Detector 2")
ax.set_xlabel(r"$\varphi$ [rad]", fontsize=11)
ax.set_ylabel(r"Intensität [dimensionlos]", fontsize=11)
ax.legend(fontsize=11)
ax.set_xticks([0, np.pi / 2, np.pi, 3 / 2 * np.pi, 2 * np.pi])
ax.set_xticklabels(["0", r"$\frac{\pi}{2}$", r"$\pi$", r"$\frac{3\pi}{2}$", r"$2\pi$"], fontsize=11)
plt.grid()
plt.show()