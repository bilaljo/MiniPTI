import pathlib

module_path = pathlib.Path(__file__).parent

try:
    from . import hardware
except ModuleNotFoundError:
    pass  # Hardware not needed

from . import algorithm

try:
    from . import gui
except ModuleNotFoundError:
    pass  # No GUI needed
