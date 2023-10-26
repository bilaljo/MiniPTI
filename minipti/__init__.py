import pathlib

module_path = pathlib.Path(__file__).parent
print(module_path)

try:
    from . import hardware
except ModuleNotFoundError:
    pass  # Hardware not needed
from . import algorithm

try:
    from . import gui
except ModuleNotFoundError:
    pass  # No GUI needed
