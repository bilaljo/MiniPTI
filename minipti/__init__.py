try:
    from . import hardware
except ModuleNotFoundError:
    pass  # Hardware not needed
from . import algorithm

try:
    from . import gui
except (ModuleNotFoundError, ImportError):
    pass  # In case the GUI is not needed
