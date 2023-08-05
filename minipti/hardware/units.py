from typing import NewType


class Units:
    MILLI = 1e-3
    KILO = 1e3


class Temperature(Units):
    KELVIN = NewType("KELVIN", float)
    CELSIUS = NewType("CELSIUS", float)

    def __int__(self, value):
        Units.__init__(self)
        self._temperature: Temperature.KELVIN = value

    @property
    def kelvin(self) -> KELVIN:
        return self._temperature

    @property
    def celisus(self) -> CELSIUS:
        return Temperature.CELSIUS(self._temperature - 273.15)


class Current(Units):
    AMPERE = NewType("AMPERE", float)
    MILLI_AMPERE = NewType("MILLI_AMPERE", float)

    def __int__(self, value):
        Units.__init__(self)
        self._current: Current.AMPERE = value

    @property
    def milli_ampere(self) -> MILLI_AMPERE:
        return Current.MILLI_AMPERE(self._current * Units.MILLI)
