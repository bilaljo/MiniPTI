"""
Unit tests for the hardware API of the MiniPTI.
"""

import logging
import os
import unittest

import minipti

logging.disable()


class DAQTest(unittest.TestCase):
    """
    Base class for DAQ related unit tests. It provied a method to check the packages that the
    DAQ generates.
    """
    driver = minipti.hardware.motherboard.Driver()

    def setUp(self) -> None:
        self.driver.synchronize = False

    def _package_test(self, sample_index: int) -> None:
        self.assertEqual(self.driver.encoded_buffer_ref_size, 128 * sample_index)
        self.assertEqual(self.driver.encoded_buffer_dc_size, 128 * sample_index)
        self.assertEqual(self.driver.encoded_buffer_ac_size, 128 * sample_index)


class MotherBoardDAQ(DAQTest):
    """
    Unit tests for several kind of packages for the DAQ.
    """
    with open(f"{os.path.dirname(__file__)}/sample_data/hardware/daq.data", "r",
              encoding="ASCII") as daq_file:
        received_data_daq = daq_file.read().split("\n")

    def test_daq_1_full_package(self) -> None:
        """
        A valid package got directly used, the buffer keeps empty.
        """
        self.driver.received_data.put(self.received_data_daq[0] + "\n")
        self.driver.encode_data()
        self.assertEqual(self.driver.buffer_size, 0)
        self._package_test(1)

    def test_daq_2_incomplete_package_1(self) -> None:
        """
        A package with valid header but missing termination symbol.
        """
        self.driver.received_data.put(self.received_data_daq[1])
        self.driver.encode_data()
        self.assertEqual(self.driver.buffer_size, len(self.received_data_daq[1]))

    def test_daq_3_incomplete_package_2(self) -> None:
        """
        The continuation of the above package. The buffer get increased.
        """
        self.driver.received_data.put(self.received_data_daq[2])
        self.driver.encode_data()
        self.assertEqual(self.driver.buffer_size,
                         len(self.received_data_daq[1]) + len(self.received_data_daq[2]))

    def test_daq_4_completed_package(self) -> None:
        """
        The packages can now be completed to a full package because every missing data is preset
        now. This causes the buffer to be empty and increasing the total package size.
        """
        self.driver.received_data.put(self.received_data_daq[3] + "\n")
        self.driver.encode_data()
        self.assertEqual(self.driver.buffer_size, 0)
        self._package_test(2)

    def test_daq_5_invalid_crc(self) -> None:
        """
        Slightly changed CRC value causes to reject because it will not match with the calculated
        based on the packages.
        """
        self.driver.received_data.put(self.received_data_daq[4] + "\n")
        self.driver.encode_data()
        self.assertEqual(self.driver.saved_sample_numbers, 0)
        # Because of rejection of the package, the packages are completely cleared
        self._package_test(0)

    def test_daq_6_too_long_package(self) -> None:
        """
        If the package contains completely valid package and yet not finished
        the not finished package will be put into the buffer.
        """
        self.driver.received_data.put(self.received_data_daq[5][:4110] + "\n"
                                      + self.received_data_daq[5][4110:])
        self.driver.encode_data()
        self.assertEqual(self.driver.buffer_size, len(self.received_data_daq[5][4110:]))
        self._package_test(1)

    def test_daq_7_package_lost(self) -> None:
        """
        A package lost means that the package number of last package (2) does
        not confirm with the current package number. This causes that the
        buffer will be cleared and the total number of packages does not change.
        """
        self.driver.received_data.put(self.received_data_daq[6][:4110] + "\n"
                                      + self.received_data_daq[6][4110:])
        self.driver.encode_data()
        self.assertEqual(self.driver.buffer_size, len(self.received_data_daq[6][4110:]))
        self._package_test(1)
        self.driver.received_data.put(self.received_data_daq[7] + "\n")
        self.driver.encode_data()
        self.assertEqual(self.driver.buffer_size, 0)
        self._package_test(1)

    def test_daq_8_invalid_beginning(self) -> None:
        """
        A broken package that got not continued, on that a full package
        followed. In this case it cannot be determined the correct package, and
        it has to be rejected.
        """
        self.driver.received_data.put(self.received_data_daq[7])
        self.driver.encode_data()
        self.assertEqual(self.driver.buffer_size, len(self.received_data_daq[7]))
        self.driver.received_data.put(self.received_data_daq[8] + "\n")
        self.driver.encode_data()
        self.assertEqual(self.driver.buffer_size, 0)
        self._package_test(1)


class MotherBoardBMS(unittest.TestCase):
    """
    Unit tests for several kind of packages for the BMS.
    """
    driver = minipti.hardware.motherboard.Driver()

    with open(f"{os.path.dirname(__file__)}/sample_data/hardware/bms.data", "r",
              encoding="ASCII") as bms_file:
        received_data_bms = bms_file.read().split("\n")

    def _bms_check_1(self) -> None:
        bms_data = self.driver.bms
        self.assertTrue(bms_data.external_dc_power)
        self.assertTrue(bms_data.charging)
        self.assertEqual(bms_data.minutes_left, 65535)
        self.assertEqual(bms_data.battery_percentage, 89)
        self.assertEqual(bms_data.battery_temperature, 2959)
        self.assertEqual(bms_data.battery_current, 30)
        self.assertEqual(bms_data.battery_voltage, 16575)
        self.assertEqual(bms_data.full_charged_capacity, 5940)
        self.assertEqual(bms_data.remaining_capacity, 5346)

    def test_bms_1_full_package(self) -> None:
        """
        A valid BMS package can be directly encoded and used.
        """
        self.driver.received_data.put(self.received_data_bms[0] + "\n")
        self.driver.encode_data()
        self.assertEqual(self.driver.buffer_size, 0)
        self._bms_check_1()

    def test_bms_2_incomplete_package_1(self) -> None:
        """
        A BMS package that is not completed yet (no terminiation symbol encountered).
        """
        self.driver.received_data.put(self.received_data_bms[1])
        self.driver.encode_data()
        self.assertEqual(self.driver.buffer_size, len(self.received_data_bms[1]))

    def test_bms_3_completed_package(self) -> None:
        """
        The continuation of above package that is completed now.
        """
        self.driver.received_data.put(self.received_data_bms[2] + "\n")
        self.driver.encode_data()
        self._bms_check_1()

    def test_bms_4_invalid_crc(self) -> None:
        """
        Tests a package with a slightly changed (wrong) CRC value. This will cause to remove
        the package but keep the buffer.
        """
        self.driver.received_data.put(self.received_data_bms[3] + "\n" + self.received_data_bms[1])
        self.driver.encode_data()
        self.assertEqual(self.driver.buffer_size, len(self.received_data_bms[1]))
        self.assertTrue(self.driver.bms_package_empty)
        self.driver.clear_buffer()

    def test_bms_5_too_long_package(self) -> None:
        """
        Tests a package that consists with a full package plus a not yet completed one.
        """
        self.driver.received_data.put(
            self.received_data_bms[4][:40] + "\n" + self.received_data_bms[4][40:])
        self.driver.encode_data()
        self.assertEqual(self.driver.buffer_size, len(self.received_data_bms[4][40:]))
        self._bms_check_1()
        self.driver.clear_buffer()


class MotherBoardDAQBMS(DAQTest):
    """
    Unit tests for packages that contains DAQ and BMS data.
    """
    driver = minipti.hardware.motherboard.Driver()

    with open(f"{os.path.dirname(__file__)}/sample_data/hardware/package.data",
              "r", encoding="ASCII") as package_file:
        received_data_package = package_file.read().split("\n")

    def test_daq_bms_1_complete_package(self) -> None:
        """
        A test case where complete BMS and DAQ packages are in one run transmitted.
        """
        self.driver.received_data.put(self.received_data_package[0] + "\n"
                                      + self.received_data_package[1] + "\n"
                                      + self.received_data_package[2] + "\n")
        self.driver.encode_data()
        self.assertEqual(self.driver.buffer_size, 0)
        self._package_test(2)


if __name__ == '__main__':
    unittest.main()
