from distutils.core import setup
import py2exe, sys, os

entry_point = sys.argv[1]
sys.argv.pop()
sys.argv.append('py2exe')
sys.argv.append('-q')

opts = {
    'py2exe': {
        'compressed': 0,
        'optimize': 2,
        'bundle_files': 1,
    }
}

setup(windows = [{'script': "__main__.py",
                "icon_resources": [(0, "fhnw.ico")]}], options=opts, zipfile="main.zip")
