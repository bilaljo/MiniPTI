import os
import pathlib

import pytest

import minipti


class DriverTests:
    driver = minipti.hardware.laser.Driver()

    @pytest.fixture(autouse=True)
    def create_config(self):
        pathlib.Path("tmp.txt").touch()
        yield
        os.remove("tmp.txt")


class TestLowPowerLaserConfig(DriverTests):
    """
    Failed loading config because of not being existent.
    """
    def test_no_config(self):
        self.driver.low_power_laser.config_path = "tmp.txt"
        assert not self.driver.low_power_laser.load_configuration()


class TestHighPowerLaserConfig(DriverTests):
    """
    Failed loading config because of not being existent.
    """
    def test_no_config(self):
        self.driver.high_power_laser.config_path = "tmp.txt"
        assert not self.driver.high_power_laser.load_configuration()
