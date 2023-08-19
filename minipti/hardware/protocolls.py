from dataclasses import dataclass
import re
from typing import Final, NoReturn, Union
import dacite
from abc import abstractmethod, ABC

from overrides import override


class ASCIIProtocoll(ABC):
    def __init__(self, stream: str) -> None:
        self._stream: str = stream

    @property
    def stream(self) -> str:
        return self._stream

    @abstractmethod
    def __repr__(self) -> str:
        ...

    @abstractmethod
    def __str__(self) -> str:
        ...

    @abstractmethod
    def check_valid_command(self) -> Union[dict[str, str], NoReturn]:
        ...


@dataclass
class CommandKeyValue:
    key: str
    value: str
    index: Union[str, None] = None


class ASCIIMultimap(ASCIIProtocoll):
    _STREAM_PATTERNS: Final = [re.compile(r"(?P<key>(Set|Get|Do)\w+):(?P<value>([+-]?([0-9]*[.])?[0-9]?|\w+))\n",
                                          flags=re.MULTILINE),
                               re.compile(r"(?P<key>(Set|Get|Do)\w+):\[(?P<index>\d+),?(?P<value>[+-]?([0-9]*[.])?[0-9]+)\]\n",
                                          flags=re.MULTILINE)]

    def __init__(self, stream: Union[str, None] = None, key: Union[str, None] = None,
                 index: Union[int, None] = None, value: Union[float, str, None] = None) -> None:
        if stream is not None:
            if key is not None or index is not None or value is not None:
                raise RuntimeWarning("Other parameters wont be used")
        elif key is not None and value is not None:
            if index is not None:
                stream = f"{key}:[{index},{value}]\n"
            else:
                stream = f"{key}:{value}\n"
        else:
            raise ValueError(fr"Stream is None or key/value is missing")
        ASCIIProtocoll.__init__(self, stream)
        command = self.check_valid_command()
        self._command: CommandKeyValue = dacite.from_dict(CommandKeyValue, command)

    @override
    def __repr__(self) -> str:
        return f"ASCIIKeyValue(stream={self._stream})"

    @override
    def __str__(self) -> str:
        if self._command.index is None:
            return f"{self._command.key}:{self._command.value}"
        else:
            return f"{self._command.key}:[{self._command.index},{self._command.value}]"

    @property
    def key(self) -> str:
        return self._command.key

    @property
    def value(self) -> Union[float, str]:
        try:
            return float(self._command.value)
        except ValueError:
            return self._command.value

    @property
    def index(self) -> int:
        try:
            return int(self._command.index)
        except TypeError:
            return -1

    @value.setter
    def value(self, new_value: float) -> None:
        self._command.value = str(new_value)

    @property
    def stream(self) -> str:
        return self._stream

    @stream.setter
    def stream(self, new_stream: str) -> None:
        self._command = dacite.from_dict(CommandKeyValue, self.check_valid_command())
        self._stream = new_stream

    @override
    def check_valid_command(self) -> Union[dict[str, str], NoReturn]:
        for pattern in ASCIIMultimap._STREAM_PATTERNS:
            split_stream = pattern.fullmatch(self._stream)
            if split_stream is not None:
                return split_stream.groupdict()
        else:
            raise ValueError(f"Command {repr(self._stream)} is not valid")


@dataclass
class CommandHex:
    command: str
    value: str


class ASCIIHex(ASCIIProtocoll):
    _NUMBER_OF_HEX_DIGITS = 4
    _STREAM_PATTERN: Final = re.compile(r"(?P<command>([GSC][a-zA-Z][\da-zA-Z]))(?P<value>([\da-fA-F]{4}))")
    _MIN_VALUE = 0
    _MAX_VALUE = (1 << _NUMBER_OF_HEX_DIGITS * 4) - 1  # 1 hex byte corresponds to 4 binary bytes
    _VALUE_INDEX = 3

    def __init__(self, stream: str):
        """
        A serial stream consistent of three bytes whereby the first represents a command for the serial device
        (G for Get, S for Set and C for Command ("execute")). The next 4 bytes represent the value that is needed for
        the command. The values are represented in hex strings.
        """
        ASCIIProtocoll.__init__(self, stream)
        self._command: CommandHex = dacite.from_dict(CommandHex, self.check_valid_command())

    @override
    def __repr__(self) -> str:
        return f"ASCIIHex(stream={self._stream}, command={self.command}, value={self.value})"

    @override
    def __str__(self) -> str:
        return self._stream

    @override
    def check_valid_command(self) -> Union[dict[str, str], NoReturn]:
        split_stream = ASCIIHex._STREAM_PATTERN.fullmatch(self._stream)
        if split_stream is not None:
            return split_stream.groupdict()
        else:
            raise ValueError(f"Stream {self._stream} is not valid")

    @property
    def command(self) -> str:
        return self._command.command

    @command.setter
    def command(self, new_command: str) -> None:
        self._command.command = new_command

    @property
    def value(self) -> int:
        return int(self._command.value, base=16)

    @value.setter
    def value(self, value: Union[str, int]) -> None:
        if not (ASCIIHex._MIN_VALUE <= int(value) < ASCIIHex._MAX_VALUE):
            raise ValueError("Value is out of range for 4 digit hex values")
        elif not isinstance(value, str):
            value = f"{value:0{ASCIIHex._NUMBER_OF_HEX_DIGITS}X}"
        self._command.value = value
        self._stream = self._stream[:ASCIIHex._VALUE_INDEX] + value

    @property
    def stream(self) -> str:
        return self._stream
