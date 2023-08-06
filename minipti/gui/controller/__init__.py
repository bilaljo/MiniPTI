import pathlib

from . import interface

if pathlib.Path(__file__).parent != "view":
    # It's not alloweed to use the Controller API inside the view namespace to avoid cyclular imports.
    # For this reason the virtual interface exists and should be used instead.
    from . import api
