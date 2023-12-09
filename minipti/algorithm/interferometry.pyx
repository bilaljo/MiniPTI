import itertools
import logging
import os
import threading
import typing
from collections import defaultdict
from collections.abc import Generator
from dataclasses import dataclass
from datetime import datetime
from typing import Final, Union

from scipy.optimize import cython_optimize

