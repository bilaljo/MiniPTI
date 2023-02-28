import itertools
import logging
import os
import tarfile
import typing
from datetime import datetime
from dataclasses import dataclass

import numpy as np
import pandas as pd
import psutil

import hardware.daq
from minipti import interferometry


@dataclass
class LockIn:
    amplitude: np.ndarray
    phase: np.ndarray


class Inversion:
    """
    Provided an API for the PTI algorithm described in [1] from Weingartner et al.

    [1]: Waveguide based passively demodulated photo-thermal
         interferometer for aerosol measurements
    """
    MICRO_RAD = 1e6
    LOCK_IN_HEADERS = [([f"X{i}" for i in range(1, 4)], [f"Y{i}" for i in range(1, 4)]),
                       ([f"x{i}" for i in range(1, 4)], [f"y{i}" for i in range(1, 4)]),
                       ([f"Lock in Amplitude {i}" for i in range(1, 4)], [f"Lock in Phase{i}" for i in range(1, 4)]),
                       ([f"AC CH{i}" for i in range(1, 4)], [f"AC Phase CH{i}" for i in range(1, 4)])]

    SYMMETRIC_MINIMUM = 1.154 - 1  # We subtract 1 to shift the optimium to 1

    def __init__(self, response_phases=None, sign=1, interferometer=None, settings_path="minipti/configs/settings.csv"):
        super().__init__()
        self.response_phases = response_phases
        self.pti_signal = 0  # type: float | np.array
        self.sensitivity = 0  # type:  np.array
        self.symmetry = 0  # type: float | np.array
        self.decimation_file_delimiter = ","
        self.dc_signals = np.empty(shape=3)
        self.settings_path = settings_path
        self.lock_in = LockIn(np.empty(shape=3), np.empty(shape=3))
        self.init_header = True
        self.sign = sign  # Makes the pti signal positive if it isn't
        self.interferometer = interferometer
        self.destination_folder = os.getcwd()
        self.load_response_phase()

    def __repr__(self) -> str:
        class_name = self.__class__.__name__
        representation = f"{class_name}(response_phases={self.response_phases}, pti_signal={self.pti_signal}," \
                         f"Symmetry={self.symmetry}, lock_in={repr(self.lock_in)}"
        return representation

    def __str__(self) -> str:
        return f"Interferometric Phase: {self.interferometer.phase}\n" \
               f"Symmetry: {self.symmetry}\nPTI signal: {self.pti_signal}"

    def load_response_phase(self) -> None:
        settings = pd.read_csv(self.settings_path, index_col="Setting")
        self.response_phases = np.deg2rad(settings.loc["Response Phases [deg]"].to_numpy())

    def _calculate_sign(self, channel: int) -> int:
        try:
            sign = np.ones(shape=len(self.interferometer.phase))
            sign[np.sin(self.interferometer.phase - self.interferometer.output_phases[channel]) < 0] = -1
        except TypeError:
            sign = 1 if np.sin(self.interferometer.phase - self.interferometer.output_phases[channel]) >= 0 else -1
        return sign

    def calculate_pti_signal(self) -> None:
        try:
            pti_signal = np.zeros(shape=(len(self.interferometer.phase)))
            weight = np.zeros(shape=(len(self.interferometer.phase)))
        except TypeError:
            pti_signal = 0
            weight = 0
        for channel in range(3):
            sign = self._calculate_sign(channel)
            response_phase = self.response_phases[channel]
            amplitude = self.interferometer.amplitudes[channel]
            demodulated_signal = self.lock_in.amplitude[channel] * np.cos(self.lock_in.phase[channel] - response_phase)
            pti_signal += demodulated_signal * sign * amplitude
            weight += amplitude * np.abs(np.sin(self.interferometer.phase - self.interferometer.output_phases[channel]))
        self.pti_signal = -pti_signal / weight * Inversion.MICRO_RAD

    def calculate_sensitivity(self) -> None:
        try:
            self.sensitivity = np.empty(shape=(3, len(self.interferometer.phase)))
        except TypeError:
            self.sensitivity = [0, 0, 0]
        for channel in range(3):
            amplitude = self.interferometer.amplitudes[channel]
            output_phase = self.interferometer.output_phases[channel]
            self.sensitivity[channel] = amplitude * np.abs(np.sin(self.interferometer.phase - output_phase))
        total_sensitivity = np.sum(self.sensitivity, axis=0)
        self.symmetry = np.max(total_sensitivity) / np.min(total_sensitivity)

    def _calculate_offline(self) -> None:
        data = self.interferometer.read_decimation()
        for header in interferometry.Interferometer.DC_HEADERS:
            try:
                dc_signals = data[header].to_numpy()
                break
            except KeyError:
                continue
        else:
            raise KeyError("Invalid key for DC values given")
        for lock_in_header_1, lock_in_header_2 in Inversion.LOCK_IN_HEADERS:
            try:
                # If it uses the X, Y notation we need to calculate amplitudes and phases first
                if lock_in_header_1[0].casefold == "x1":
                    self.lock_in.amplitude = np.sqrt(data[lock_in_header_1] ** 2
                                                     + data[lock_in_header_1] ** 2).to_numpy().T
                    self.lock_in.phase = np.arctan2(data[lock_in_header_2], data[lock_in_header_1]).to_numpy().T
                    pti_measurement = True
                    break
                # Otherwise the phases and amplitudes are already calculated
                else:
                    self.lock_in.amplitude = data[lock_in_header_1].to_numpy().T
                    self.lock_in.phase = data[lock_in_header_2].to_numpy().T
                    pti_measurement = True
                    break
            except KeyError:
                continue
        else:
            pti_measurement = False
        self.interferometer.calculate_phase(dc_signals)
        self.calculate_sensitivity()
        if pti_measurement:
            self.calculate_pti_signal()
        units, output_data = self._prepare_data(pti_measurement)
        pd.DataFrame(units, index=["s"]).to_csv(f"{self.destination_folder}/PTI_Inversion.csv", index_label="Time")
        pd.DataFrame(output_data).to_csv(f"{self.destination_folder}/PTI_Inversion.csv", index_label="Time", mode="a",
                                         header=False)
        logging.info("PTI Inversion calculated.")

    def _prepare_data(self, pti_measurement) -> tuple[typing.Mapping[str, str], typing.Mapping[str, np.ndarray]]:
        units = {"Interferometric Phase": "rad", "Symmetrie": "1",
                 "Sensitivity CH1": "V/rad", "Sensitivity CH2": "V/rad", "Sensitivity CH3": "V/rad"}
        output_data = {"Interferometric Phase": self.interferometer.phase, "Symmetry": self.symmetry}
        for i in range(3):
            output_data[f"Sensitivity CH{i + 1}"] = self.sensitivity[i]
        if pti_measurement:
            units["PTI Signal"] = ["µrad"]
            output_data["PTI Signal"] = self.pti_signal
        output_data["Interferometric Phase"] = np.array(output_data["Interferometric Phase"])
        return units, output_data

    def _calculate_online(self) -> None:
        output_data = {}
        if self.init_header:
            output_data["Interferometric Phase"] = "rad"
            for channel in range(1, 4):
                output_data[f"Sensitivity CH{channel}"] = "V/rad"
            output_data["Symmetry"] = "1"
            output_data["PTI Signal"] = "µrad"
            pd.DataFrame(output_data, index=["s"]).to_csv(f"{self.destination_folder}/PTI_Inversion.csv",
                                                          index_label="Time")
            self.init_header = False
        self.interferometer.calculate_phase(self.dc_signals)
        self.calculate_pti_signal()
        self.calculate_sensitivity()
        now = datetime.now()
        time_stamp = str(now.strftime("%Y-%m-%d %H:%M:%S"))
        output_data = {"Interferometric Phase": self.interferometer.phase, "Sensitivity CH1": self.sensitivity[0],
                       "Sensitivity CH2": self.sensitivity[1],  "Sensitivity CH3": self.sensitivity[2],
                       "Symmetry": self.symmetry, "PTI Signal": self.pti_signal}
        try:
            pd.DataFrame(output_data, index=[time_stamp]).to_csv(f"{self.destination_folder}/PTI_Inversion.csv",
                                                                 mode="a", index_label="Time", header=False)
        except PermissionError:
            logging.info(f"Could not write data. Missing values are: {str(output_data)[1:-1]} at {time_stamp}.")

    def __call__(self, live=True) -> None:
        if live:
            self._calculate_online()
        else:
            self._calculate_offline()


class Decimation:
    """
    Provided an API for the PTI decimation described in [1] from Weingartner et al.

    The number of samples

    [1]: Waveguide based passively demodulated photo-thermal
         interferometer for aerosol measurements
    """
    REF_VOLTAGE = 3.3  # V
    REF_PERIOD = 100  # Samples
    SAMPLES = hardware.daq.Driver.NUMBER_OF_SAMPLES
    DC_RESOLUTION = (1 << 12) - 1  # 12 Bit ADC
    AC_RESOLUTION = (1 << (16 - 1)) - 1  # 16 bit ADC with 2 complement
    AMPLIFICATION = 100  # Theoretical value given by the hardware

    MINIMUM_RAM = 1e-2 * psutil.virtual_memory().total  # 1 % of maximum RAM should be at least free
    MEMORY_ALLOCATION_SIZE = 1e-2  # 1 %
    DATA_BLOCK_SIZE = int(112e3)

    CHANNELS = 8

    def __init__(self, debug=True):
        self.dc_coupled = np.empty(shape=(3, Decimation.SAMPLES))
        self.ac_coupled = np.empty(shape=(3, Decimation.SAMPLES))
        self.dc_signals = np.empty(shape=3)
        self.lock_in = LockIn(np.empty(shape=3), np.empty(shape=3))
        self.ref = None
        self.save_raw_data = False
        self.in_phase = np.cos(2 * np.pi / Decimation.REF_PERIOD * np.arange(0, Decimation.SAMPLES))
        self.quadrature = np.sin(2 * np.pi / Decimation.REF_PERIOD * np.arange(0, Decimation.SAMPLES))
        self.destination_folder = "."
        self.file_path = ""
        self.init_header = True
        self.now = datetime.now()
        # Memory allocation is too expensive, so it's better to allocate the memory at startup once and reuse it
        self.buffer_size = int(psutil.virtual_memory().total * Decimation.MEMORY_ALLOCATION_SIZE)
        self.buffer_size //= Decimation.DATA_BLOCK_SIZE
        self.buffer = np.empty(shape=(self.buffer_size, Decimation.CHANNELS, Decimation.SAMPLES))
        self._actual_buffer_size = self.buffer_size
        self._raw_data_index = itertools.count()
        self._raw_data_file_index = itertools.count()
        self.flushed = False

    def save_to_buffer(self) -> None:
        """
        One package of raw data needs 8000 samples * (3 AC + 3 DC + 1 Ref) * 2 Bytes = 112 kB. To reduce the IO
        operations we buffer this data with until 10 % of available RAM is allocated. If the program finishes before
        raw data is saved the data will be flushed out. Same if available RAM is too low.
        """
        self.flushed = False
        current_data_frame = next(self._raw_data_index)
        if True: #current_data_frame + 1 == self.buffer_size:
            self.flush()
        elif psutil.virtual_memory().available < Decimation.MINIMUM_RAM:
            self._actual_buffer_size = current_data_frame + 1
            self.flush()
        else:
            for channel in range(3):
                self.buffer[current_data_frame][channel][:] = self.dc_coupled[channel]
                self.buffer[current_data_frame][channel + 3][:] = self.ac_coupled[channel]
            self.buffer[current_data_frame][Decimation.CHANNELS - 1][:] = self.ref

    def flush(self) -> None:
        if self._actual_buffer_size < self.buffer_size:
            # We had to flush earlier so the arrays needs to be smaller
            self.buffer.resize((self._actual_buffer_size, Decimation.CHANNELS))
        np.save(self.destination_folder + f"/raw_data_{next(self._raw_data_file_index)}", self.buffer)
        self.flushed = True
        self._raw_data_index = itertools.count()
        if self._actual_buffer_size < self.buffer_size:
            self._actual_buffer_size = self.buffer_size
            self.buffer.resize((self.buffer_size, Decimation.CHANNELS))

    def process_raw_data(self) -> None:
        """
        Reads the binary data and save it into numpy arrays. The data is saved into npy archives in debug mode.
        """
        if self.save_raw_data:
            self.save_to_buffer()
        dc_coupled = self.dc_coupled * Decimation.REF_VOLTAGE / Decimation.DC_RESOLUTION
        ac_coupled = self.ac_coupled / Decimation.AMPLIFICATION * Decimation.REF_VOLTAGE / Decimation.AC_RESOLUTION
        self.dc_coupled = dc_coupled
        self.ac_coupled = ac_coupled

    def get_raw_data(self) -> str:
        pass

    def calculate_dc(self) -> None:
        """
        Applies a low pass to the DC-coupled signals and decimate it to 1 s values.
        """
        np.mean(self.dc_coupled, axis=1, out=self.dc_signals)

    def common_mode_noise_reduction(self) -> None:
        noise_factor = np.sum(self.ac_coupled, axis=0) / sum(self.dc_signals)
        for channel in range(3):
            self.ac_coupled[channel] = self.ac_coupled[channel] - noise_factor * self.dc_signals[channel]

    def lock_in_amplifier(self) -> None:
        ac_x = np.mean(self.ac_coupled * self.in_phase, axis=1)
        ac_y = np.mean(self.ac_coupled * self.quadrature, axis=1)
        self.lock_in.phase = np.arctan2(ac_y, ac_x)
        self.lock_in.amplitude = np.sqrt(ac_x ** 2 + ac_y ** 2)

    def _calculate_decimation(self) -> None:
        self.calculate_dc()
        self.common_mode_noise_reduction()
        self.lock_in_amplifier()
        output_data = {}
        for channel in range(3):
            output_data[f"Lock In Amplitude CH{channel + 1}"] = self.lock_in.amplitude[channel]
            output_data[f"Lock In Phase CH{channel + 1}"] = np.rad2deg(self.lock_in.phase[channel])
            output_data[f"DC CH{channel + 1}"] = self.dc_signals[channel]
        now = datetime.now()
        time_stamp = str(now.strftime("%Y-%m-%d %H:%M:%S"))
        try:
            pd.DataFrame(output_data, index=[time_stamp]).to_csv(f"{self.destination_folder}/Decimation.csv", mode="a",
                                                                 index_label="Time", header=False)
        except PermissionError:
            logging.info(f"Could not write data. Missing values are: {str(output_data)[1:-1]} at {time_stamp}.")

    def __call__(self, live=True) -> None:
        if self.init_header:
            output_data = {}
            for channel in range(3):
                output_data[f"Lock In Amplitude CH{channel + 1}"] = "V"
                output_data[f"Lock In Phase CH{channel + 1}"] = "deg"
                output_data[f"DC CH{channel + 1}"] = "V"
            pd.DataFrame(output_data, index=["s"]).to_csv(f"{self.destination_folder}/Decimation.csv",
                                                          index_label="Time")
            self.init_header = False
        if live:
            self.process_raw_data()
            self._calculate_decimation()
        else:
            for file in self.get_raw_data():
                with np.load(file) as data:
                    self.dc_coupled = data["dc_coupled"]
                    self.ac_coupled = data["ac_coupled"]
                self._calculate_decimation()
