import json
from typing import TypeVar, Type

import dacite

import minipti


T = TypeVar("T")


def load_configuration(type_name: Type[T], scope: str, key: str) -> T:
    with open(f"{minipti.MODULE_PATH}/algorithm/configs/algorithm.json") as config:
        loaded_configuration = json.load(config)["Algorithm"]
        return dacite.from_dict(type_name, loaded_configuration[scope][key])
