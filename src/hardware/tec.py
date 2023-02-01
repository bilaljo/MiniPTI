import hardware


class Driver(hardware.driver.Serial):
    HARDWARE_ID = b"0003"
    NAME = "Tec"

    def __init__(self):
        hardware.driver.Serial.__init__(self)

    @property
    def device_id(self):
        return Driver.HARDWARE_ID

    @property
    def device_name(self):
        return Driver.NAME

    def encode_data(self):
        pass
