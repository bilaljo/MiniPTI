import os
import sys
import unittest
import pathlib

sys.path.extend(".")

import minipti


class DriverTests(unittest.TestCase):
    driver = minipti.hardware.laser.Driver()

    def setUp(self) -> None:
        pathlib.Path("tmp.txt").touch()

    def tearDown(self) -> None:
        os.remove("tmp.txt")


class LowPowerLaserConfig(DriverTests):
    """
    Failed loading config because of not being existent.
    """
    def test_no_config(self):
        self.driver.low_power_laser.config_path = "tmp.txt"
        self.assertFalse(self.driver.low_power_laser.load_configuration())


class HighPowerLaserConfig(DriverTests):
    """
    Failed loading config because of not being existent.
    """
    def test_no_config(self):
        self.driver.high_power_laser.config_path = "tmp.txt"
        self.assertFalse(self.driver.high_power_laser.load_configuration())


if __name__ == '__main__':
    unittest.main()
