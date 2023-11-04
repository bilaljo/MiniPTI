import pathlib

module_path = pathlib.Path(__file__).parent

from . import algorithm

try:
    from . import hardware
except ModuleNotFoundError:
    pass
try:
    from . import gui
except ModuleNotFoundError:
    pass
