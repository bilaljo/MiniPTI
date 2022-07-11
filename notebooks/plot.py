import numpy as np
import matplotlib.pyplot as plt

t= np.arange(1000)/100.
x = np.sin(2*np.pi*10*t)
y = np.cos(2*np.pi*10*t)

fig=plt.figure()
ax1 = plt.subplot(311)
ax2 = plt.subplot(312)
ax3 = plt.subplot(313)

ax1.plot(t,x)
ax2.plot(t,y)
ax3.plot(t,y)

ax1.get_shared_x_axes().join(ax1, ax2, ax3)
ax1.set_xticklabels([])
ax2.set_xticklabels([])

plt.subplots_adjust(hspace=.0)

# ax2.autoscale() ## call autoscale if needed

plt.show()

