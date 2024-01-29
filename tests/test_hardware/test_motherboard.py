"""
Unit tests for the hardware.Motherboard API of the MiniPTI.
"""
import itertools
import os

import numpy as np
import pytest
import logging

logging.disable()

import minipti


class DriverTests:
    driver = minipti.hardware.motherboard.Driver()

    @pytest.fixture(autouse=True)
    def setup(self) -> None:
        DriverTests.driver.daq.synchronize = False
        DriverTests.driver.bms.running.set()
        DriverTests.driver.daq.running.set()
        DriverTests.driver.connected.set()
        yield
        DriverTests.driver.bms.running.clear()
        DriverTests.driver.daq.running.clear()
        self.driver.reset()

    @classmethod
    def transmission(cls, data: str) -> None:
        cls.driver.received_data.put(data)
        assert not cls.driver.received_data.empty()
        cls.driver.encode_data()


class DAQTest(DriverTests):
    """
    Base class for DAQ related unit tests. It provided a method to check the packages that the
    DAQ generates.
    """
    def _package_test(self, sample_index: int) -> None:
        assert self.driver.daq.samples_buffer_size == 128 * sample_index


class TestMotherBoardDAQ(DAQTest):
    """
    Unit tests for several kind of packages for the DAQ.
    """
    received_data_daq = ""

    @pytest.fixture(autouse=True)
    def open_data(self) -> None:
        with open(f"{os.path.dirname(__file__)}/sample_data/daq.data", "r",
                  encoding="ASCII") as daq_file:
            self.received_data_daq = daq_file.read().split("\n")

    def test_daq_1_full_package(self) -> None:
        """
        A valid package got directly used, the buffer keeps empty.
        """
        self.transmission(self.received_data_daq[0] + "\n")
        assert self.driver.buffer_size == 0
        self._package_test(1)

    def test_daq_2_incomplete_package_1(self) -> None:
        """
        A package with valid header but missing termination symbol.
        """
        self.transmission(self.received_data_daq[1])
        assert self.driver.buffer_size == len(self.received_data_daq[1])

    def test_daq_3_incomplete_package_2(self) -> None:
        """
        The continuation of the above package. The buffer get increased.
        """
        self.transmission(self.received_data_daq[1])
        self.transmission(self.received_data_daq[2])
        assert (self.driver.buffer_size == len(self.received_data_daq[1])
                + len(self.received_data_daq[2]))

    def test_daq_4_completed_package(self) -> None:
        """
        The packages can now be completed to a full package because every missing data is preset
        now. This causes the buffer to be empty and increasing the total package size.
        """
        self.transmission(self.received_data_daq[1])
        self.transmission(self.received_data_daq[2])
        self.transmission(self.received_data_daq[3] + "\n")
        assert self.driver.buffer_size == 0
        self._package_test(1)

    def test_daq_5_invalid_crc(self) -> None:
        """
        Slightly changed CRC value causes to reject because it will not match with the calculated
        based on the packages.
        """
        assert self.driver.received_data.empty()
        self.transmission(self.received_data_daq[4] + "\n")
        # Because of rejection of the package, the packages are completely cleared
        self._package_test(0)

    def test_daq_6_too_long_package(self) -> None:
        """
        If the package contains completely valid package and yet not finished
        the not finished package will be put into the buffer.
        """
        self.transmission(self.received_data_daq[5][:4109] + "\n"
                          + self.received_data_daq[5][4109:])
        assert self.driver.buffer_size == len(self.received_data_daq[5][4109:])
        self._package_test(1)

    def test_daq_7_package_lost(self) -> None:
        """
        A package lost means that the package number of last package (2) does
        not confirm with the current package number. This causes that the
        buffer will be cleared and the total number of packages does not change.
        """
        self.transmission(self.received_data_daq[5][:4109] + "\n"
                          + self.received_data_daq[5][4109:])
        self.transmission(self.received_data_daq[6][:4109] + "\n"
                          + self.received_data_daq[6][4109:])
        assert self.driver.buffer_size == len(self.received_data_daq[6][4109:])
        self._package_test(1)
        self.transmission(self.received_data_daq[7] + "\n")
        assert self.driver.buffer_size == 0
        self._package_test(1)

    def test_daq_8_invalid_beginning(self) -> None:
        """
        A broken package that got not continued, on that a full package
        followed. In this case it cannot be determined the correct package, and
        it has to be rejected.
        """
        self.transmission(self.received_data_daq[7])
        assert self.driver.buffer_size == len(self.received_data_daq[7])
        self.transmission(self.received_data_daq[8] + "\n")
        assert self.driver.buffer_size == 0
        self._package_test(0)


class TestMotherBoardBMS(DAQTest):
    """
    Unit tests for several kind of packages for the BMS.
    """
    received_data_bms = ""

    @pytest.fixture(autouse=True)
    def open_bms_data(self):
        with open(f"{os.path.dirname(__file__)}/sample_data/bms.data", "r",
                  encoding="ASCII") as bms_file:
            self.received_data_bms = bms_file.read().split("\n")

    def _bms_check_1(self) -> None:
        shutdown, bms_data = self.driver.bms.data
        assert shutdown < minipti.hardware.motherboard.BMS.SHUTDOWN
        assert bms_data.external_dc_power
        assert bms_data.charging
        assert bms_data.minutes_left == float("inf")
        assert bms_data.battery_percentage == 89
        assert bms_data.battery_temperature == 2959
        assert bms_data.battery_current == 30
        assert bms_data.battery_voltage == 16575
        assert bms_data.full_charged_capacity == 5940
        assert bms_data.remaining_capacity == 5346

    def test_bms_1_full_package(self) -> None:
        """
        A valid BMS package can be directly encoded and used.
        """
        self.driver.received_data.put(self.received_data_bms[0] + "\n")
        self.driver.encode_data()
        assert self.driver.buffer_size == 0
        self._bms_check_1()

    def test_bms_2_incomplete_package_1(self) -> None:
        """
        A BMS package that is not completed yet (no termination symbol encountered).
        """
        self.driver.received_data.put(self.received_data_bms[1])
        self.driver.encode_data()
        assert self.driver.buffer_size == len(self.received_data_bms[1])

    def test_bms_3_completed_package(self) -> None:
        """
        The continuation of above package that is completed now.
        """
        self.transmission(self.received_data_bms[1])
        self.transmission(self.received_data_bms[2] + "\n")
        self._bms_check_1()

    def test_bms_4_invalid_crc(self) -> None:
        """
        Tests a package with a slightly changed (wrong) CRC value. This will cause to remove
        the package but keep the buffer.
        """
        self.driver.received_data.put(self.received_data_bms[3] + "\n" + self.received_data_bms[1])
        self.driver.encode_data()
        assert self.driver.buffer_size, len(self.received_data_bms[1])
        assert self.driver.bms.empty

    def test_bms_5_too_long_package(self, setup, open_bms_data) -> None:
        """
        Tests a package that consists with a full package plus a not yet completed one.
        """
        self.driver.received_data.put(self.received_data_bms[4][:39]
                                      + "\n" + self.received_data_bms[4][39:])
        self.driver.encode_data()
        assert self.driver.buffer_size, len(self.received_data_bms[4][39:])
        self._bms_check_1()


class TestMotherBoardDAQBMS(DAQTest):
    """
    Unit tests for packages that contains DAQ and BMS data.
    """
    received_data_package = ""

    @pytest.fixture(autouse=True)
    def open_data(self):
        with open(f"{os.path.dirname(__file__)}/sample_data/package.data",
                  "r", encoding="ASCII") as package_file:
            self.received_data_package = package_file.read().split("\n")

    def test_daq_bms_1_complete_package(self) -> None:
        """
        A test case where complete BMS and DAQ packages are in one run transmitted.
        """
        self.driver.daq.is_running = True
        self.driver.received_data.put(self.received_data_package[0] + "\n"
                                      + self.received_data_package[1] + "\n"
                                      + self.received_data_package[2] + "\n", block=False)
        self.driver.encode_data()


class TestSynchronizeWithRef(DriverTests):
    def test_sync_with_ref(self) -> None:
        self.driver.daq.encoded_buffer.ref_signal.extend([1 if i <= 10 else 0 for i in range(100)])
        for i in range(3):
            # Random data, not really needed
            self.driver.daq.encoded_buffer.ac_coupled[i].extend([1 if i <= 10 else 0 for i in range(100)])
            self.driver.daq.encoded_buffer.dc_coupled[i].extend([1 if i <= 10 else 0 for i in range(100)])
        self.driver.daq.encoded_buffer.dc_coupled[3].extend([1 if i <= 10 else 0 for i in range(100)])
        self.driver.daq.synchronize = True
        self.driver.daq.synchronize_with_ref()
        ref = self.driver.daq.encoded_buffer.ref_signal
        ref_period = self.driver.daq.configuration.ref_period // 2
        assert not sum(itertools.islice(ref, ref_period))
