import unittest
import minipti
import logging


logging.disable()


class MotherBoard(unittest.TestCase):
    driver = minipti.hardware.motherboard.Driver()
    file = open("tests/hardware_sample_data.data", "r")
    received_data = file.read().split("\n")

    def setUp(self) -> None:
        self.driver._synchronize = False

    def _package_test(self, sample_index: int) -> None:
        self.assertEqual(
            len(self.driver._encoded_buffer.ref_signal),
            128 * sample_index
        )
        for i in range(3):
            self.assertEqual(
                len(self.driver._encoded_buffer.ac_coupled[i]),
                128 * sample_index
            )
            self.assertEqual(
                len(self.driver._encoded_buffer.ac_coupled[i]),
                128 * sample_index
            )

    def test_daq_1_full_package(self) -> None:
        """
        A valid package got directly used, the buffer keeps empty.
        """
        self.driver.received_data.put(self.received_data[0] + "\n")
        self.driver.encode_data()
        self.assertEqual(len(self.driver._buffer), 0)
        self._package_test(1)

    def test_daq_2_incomplete_package_1(self) -> None:
        """
        A package with valid header but missing termination symbol.
        """
        self.driver.received_data.put(self.received_data[1])
        self.driver.encode_data()
        self.assertEqual(len(self.driver._buffer), len(self.received_data[1]))

    def test_daq_3_incomplete_package_2(self) -> None:
        """
        The continuation of the above package. The buffer get increased.
        """
        self.driver.received_data.put(self.received_data[2])
        self.driver.encode_data()
        self.assertEqual(
            len(self.driver._buffer),
            len(self.received_data[1]) + len(self.received_data[2])
        )

    def test_daq_4_completed_package(self) -> None:
        """
        The packages can now be completed to a full package because every
        missing data is preset now. This causes the buffer to be empty and
        increasing the total package size.
        """
        self.driver.received_data.put(self.received_data[3] + "\n")
        self.driver.encode_data()
        self.assertEqual(len(self.driver._buffer), 0)
        self._package_test(2)

    def test_daq_5_invalid_crc(self) -> None:
        """
        Slightly changed CRC value causes to reject because it will not match
        with the calculated based on the packages.
        """
        self.driver.received_data.put(self.received_data[4] + "\n")
        self.driver.encode_data()
        self.assertEqual(len(self.driver._buffer), 0)
        self.assertEqual(len(self.driver._sample_numbers), 0)
        # Because of rejection of the package, the packages are completely cleared
        self._package_test(0)

    def test_daq_6_too_long_package(self) -> None:
        """
        If the package contains completely valid package and yet not finished
        the not finished package will be put into the buffer.
        """
        self.driver.received_data.put(
            self.received_data[5][:4110] + "\n" + self.received_data[5][4110:]
        )
        self.driver.encode_data()
        self.assertEqual(
            len(self.driver._buffer),
            len(self.received_data[5][4110:])
        )
        self._package_test(1)

    def test_daq_7_package_lost(self) -> None:
        """
        A package lost means that the package number of last package (2) does
        not confirm with the current package number. This causes that the
        buffer will be cleared and the total number of packages does not change.
        """
        self.driver.received_data.put(
            self.received_data[6][:4110] + "\n" + self.received_data[6][4110:]
        )
        self.driver.encode_data()
        self.assertEqual(len(self.driver._buffer), len(self.received_data[6][4110:]))
        self._package_test(1)
        self.driver.received_data.put(self.received_data[7] + "\n")
        self.driver.encode_data()
        self.assertEqual(len(self.driver._buffer), 0)
        self._package_test(1)

    def test_daq_8_invalid_beginning(self) -> None:
        """
        A broken package that got not continued, on that a full package
        followed. In this case it cannot be determined the correct package, and
        it has to be rejected.
        """
        self.driver.received_data.put(self.received_data[7])
        self.driver.encode_data()
        self.assertEqual(len(self.driver._buffer), len(self.received_data[7]))
        self.driver.received_data.put(self.received_data[8] + "\n")
        self.driver.encode_data()
        self.assertEqual(len(self.driver._buffer), 0)
        self._package_test(1)

    def test_bms_1(self) -> None:
        pass

    def tearDown(self) -> None:
        self.file.close()


if __name__ == '__main__':
    unittest.main()
