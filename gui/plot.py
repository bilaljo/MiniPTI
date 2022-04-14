import pandas as pd
from math import sqrt
from math import ceil
import matplotlib.pyplot as plt


data = pd.read_csv("data.csv")


headers = 0
labels = []
for column in data:
    headers += 1
    labels.append(column)

n = ceil(sqrt(headers))
figure, axis = plt.subplots(n, n)

k = 0
for i in range(n):
    for j in range(n):
        axis[i, j].plot(range(len(data[labels[k]])), data[labels[k]], label=labels[k])
        k += 1
        axis[i, j].legend()
plt.show()

