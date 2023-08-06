try:
    import hardware
except ModuleNotFoundError:
    pass  # Hardware not needed
import algorithm

"""
try:
    from . import gui
except (ModuleNotFoundError, ImportError):
    pass  # In case the GUI is not needed
"""
import gui
