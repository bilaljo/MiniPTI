import array

import networkx as nx
import numpy as np
from scipy import optimize


class PhaseScan:
    """
    Implements a passive phase scan. A phase scan means calculating the output phases and can be done if there are
    enough elements for the algorithm. Enoug means that every phase-bucket has at least one occoured.
    """

    def __init__(self, signals=None, step_size=None):
        self.signals = signals
        self.phases = None
        self.scaled_signals = None
        self.step_size = step_size
        self.phase_graph = nx.Graph(directed=True)
        self.roots = []
        self.colored_nodes = []
        self.last_node = 0
        self.enough_values = False
        self.output_phases = np.empty(3)

    min_intensities = None

    max_intensities = None

    def set_signals(self, signal):
        self.signals = signal

    def set_phases(self, phases):
        self.phases = phases

    def set_min(self):
        PhaseScan.min_intensities = np.min(self.signals, axis=1)

    def set_max(self):
        PhaseScan.max_intensities = np.max(self.signals, axis=1)

    def scale_data(self):
        self.scaled_signals = 2 * (self.signals.T - PhaseScan.min_intensities) / (
                PhaseScan.max_intensities - PhaseScan.min_intensities) - 1

    def create_graph(self):
        for i in range(1, self.step_size + 1):
            self.phase_graph.add_node(2 * np.pi / self.step_size * i)
            self.roots.append(2 * np.pi / self.step_size * i)

    def add_phase(self, phase, time):
        k = int(self.step_size * phase / (2 * np.pi))
        self.phase_graph.add_edge(self.roots[k - 1], time)

    def color_nodes(self):
        for i in range(self.last_node, self.step_size):
            root = self.roots[i]
            neighbors = list(self.phase_graph[root])
            if neighbors:
                colored_node = neighbors[0]  # We choice the first neighbor since it doesn't matter which we use.
                self.colored_nodes.append(colored_node)
                self.phase_graph.remove_node(colored_node)
            else:
                self.last_node = i
                self.enough_values = False
                break
        else:
            self.enough_values = True

    def calulcate_output_phases(self):
        if self.scaled_signals is None:
            raise ValueError("Signals are not scaled")

        def error_function(intensity, channel):
            return lambda x: np.sum((np.cos(x - self.phases) - intensity[channel]) ** 2)

        self.output_phases[1] = optimize.fminbound(func=error_function(self.scaled_signals.T, 1), x1=0, x2=2*np.pi)
        self.output_phases[2] = optimize.fminbound(func=error_function(self.scaled_signals.T, 2), x1=0, x2=2*np.pi)
