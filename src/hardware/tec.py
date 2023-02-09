import hardware
from dataclasses import dataclass


@dataclass
class Data:
    pass


class Driver(hardware.serial.Driver):
    HARDWARE_ID = b"0003"
    NAME = "Tec"

    def __init__(self):
        hardware.serial.Driver.__init__(self)

    @property
    def device_id(self):
        return Driver.HARDWARE_ID

    @property
    def device_name(self):
        return Driver.NAME

    @property
    def end_data_frame(self) -> int:
        return 0
