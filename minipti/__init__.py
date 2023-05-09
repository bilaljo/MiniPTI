try:
    from . import hardware
except ModuleNotFoundError:
    pass
from . import algorithm
from . import json_parser
try:
    from . import gui
except ModuleNotFoundError:
    pass  # In case the GUI is not needed
