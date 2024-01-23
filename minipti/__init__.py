import pathlib

MODULE_PATH = pathlib.Path(__file__).parent

path_prefix = "Offline"

from . import algorithm

from . import hardware

from . import gui
