from typing import NamedTuple


class SerialValue:
    _BYTE_PREFIX = 3

    def __int__(self):
        self.value: str = ""

    def __ror__(self, other):
        if isinstance(other, str):
            self.value[SerialValue._BYTE_PREFIX:] = other
        else:
            self.value[SerialValue._BYTE_PREFIX:] = other.value


class Tec(NamedTuple):
    set_p_value: str = "SP0000"
    set_i_1_value: str = "SI0000"
    