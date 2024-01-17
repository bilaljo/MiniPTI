import json
from datetime import datetime
from typing import TypeVar, Type, Final

import dacite

import minipti

now = datetime.now()
PATH_PREFIX: Final = str(now.strftime("%Y-%m-%d"))


T = TypeVar("T")


def load_configuration(type_name: Type[T], scope: str, key: str) -> T:
    with open(f"{minipti.module_path}/algorithm/configs/algorithm.json") as config:
        loaded_configuration = json.load(config)["Algorithm"]
        return dacite.from_dict(type_name, loaded_configuration[scope][key])
