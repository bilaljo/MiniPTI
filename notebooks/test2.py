import numpy as np
from matplotlib import pyplot as plt
from matplotlib import animation
import collections
import pandas as pd

# First set up the figure, the axis, and the plot element we want to animate
fig, ax = plt.subplots()
line, = ax.plot([], [], lw=2)

x = collections.deque(maxlen=1000)
y1 = collections.deque(maxlen=1000)
y2 = collections.deque(maxlen=1000)
y3 = collections.deque(maxlen=1000)
data = pd.read_csv("Decimation.csv")


def animate(i):
    x.append(i)
    y1.append(data["DC CH1"][i])
    y2.append(data["DC CH2"][i])
    y3.append(data["DC CH3"][i])
    plt.cla()
    plt.plot(x, y1)
    plt.plot(x, y2)
    plt.plot(x, y3)
    return line,


ani = animation.FuncAnimation(
    fig, animate, interval=50, blit=False, save_count=50)

# To save the animation, use e.g.
#
# ani.save("movie.mp4")
#
# or
#
# writer = animation.FFMpegWriter(
#     fps=15, metadata=dict(artist='Me'), bitrate=1800)
# ani.save("movie.mp4", writer=writer)

plt.show()