import pathlib

MODULE_PATH = pathlib.Path(__file__).parent

path_prefix = ""

from . import algorithm

from . import hardware

from . import gui
