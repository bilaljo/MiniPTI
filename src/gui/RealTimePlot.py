from Plotting import Plotting
import csv
import matplotlib.pyplot as plt
from collections import deque
import matplotlib.animation as animation
import matplotlib.dates as mdates
from datetime import date


class RealTimePlot(Plotting):
    def __init__(self, main_window, intervall=600):
        super.__init__(main_window)
        self.figures = {"PTI Signal":  plt.Figure((2, 9), dpi=100),
                        "Interferometric Phase": plt.Figure((2, 9), dpi=100)}
        self.axes = {"PTI Signal": self.figures["PTI Signal"].add_subplot(),
                     "Interferometric Phase": self.figures["Interferometric Phase"].add_subplot()}
        self.time = deque(maxlen=intervall)
        self.pti = deque(maxlen=intervall)  # With this we limit the maxium drawn points in plot.
        self.phase = deque(maxlen=intervall)
        self.data = None
        self.pti_data = None
        self.phase_data = None

    @staticmethod
    def __get_data_generator():
        with open("PTI.csv", "r") as csvfile:
            reader = csv.DictReader(csvfile)
            while True:
                try:
                    row = next(reader)
                    yield float(row["Interferometric Phase"]), float(row["PTI Signal"])
                except StopIteration:
                    yield -1

    def set_csv(self):
        self.data = self.__get_data_generator()

    def set_data(self):
        self.pti_data, self.phase_data = next(self.data)

    def animate_pti(self, i):
        self.set_data()
        self.axes["PTI Signal"].clear()
        xfmt = mdates.DateFormatter("%d-%m-%y %H:%M")
        self.axes["PTI Signal"].xaxis.set_major_formatter(xfmt)
        self.axes["PTI Signal"].autofmt_xdate()
        self.time.append(date.today().strftime("%d-%m-%y %H:%M"))
        self.pti.append(self.pti_data)
        self.axes["PTI Signal"].plot(self.time, self.pti)
        self.axes["PTI Signal"].set_xlabel("Time in s", fontsize=12)
        self.axes["PTI Signal"].set_ylabel("PTI Signal in rad", fontsize=12)
        self.axes["PTI Signal"].grid()

    def animate_phase(self, i):
        self.axes["Interferometric Phase"].clear()
        xfmt = mdates.DateFormatter('%d-%m-%y %H:%M:%s')
        self.axes["Interferometric Phase"].xaxis.set_major_formatter(xfmt)
        self.axes["Interferometric Phase"].autofmt_xdate()
        self.pti.append(self.phase_data)
        self.axes["Interferometric Phase"].plot(self.time, self.phase)
        self.axes["Interferometric Phase"].set_xlabel("Time in s", fontsize=12)
        self.axes["Interferometric Phase"].set_ylabel("PTI Signal in rad", fontsize=12)
        self.axes["Interferometric Phase"].grid()

    def draw_plots(self, program, config):
        self.create_plot(self.tab_pti, self.figures["PTI Signal"])
        self.create_plot(self.tab_interferometric_phase, self.figures["Interferometric Phase"])

    def live_plot(self):
        animation.FuncAnimation(self.figures["PTI Signal"], self.animate_pti, interval=1000, frames=1)
        animation.FuncAnimation(self.figures["Interferometric Phase"], self.animate_phase, interval=1000, frames=1)
        plt.show()

    def execute(self):
        self.live_plot()
        self.main_window.after()
