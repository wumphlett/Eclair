from collections import defaultdict
from enum import Flag, auto
from typing import List

from topping_bot.crk.toppings import Topping, Type
from topping_bot.optimize.requirements import Requirements


class Prune(Flag):
    NONE = auto()
    FLOOR_FAILURE = auto()
    CEILING_FAILURE = auto()
    CONFLICTING_REQS_FAILURE = auto()

    COMBINED_VALID_FAILURE = auto()
    COMBINED_OBJ_FAILURE = auto()
    COMBINED_SPECIAL_OBJ_FAILURE = auto()
    COMBINED_ALL_FAILURE = auto()
    COMBINED_SPECIAL_ALL_FAILURE = auto()

class Cutter:
    def __init__(self, reqs: Requirements):
        self.reqs = reqs

    def init_planes(self):
        return {
            Prune.FLOOR_FAILURE: defaultdict(lambda: float("-inf")),
            Prune.CEILING_FAILURE: defaultdict(lambda: float("inf")),
            Prune.COMBINED_VALID_FAILURE: [],
            Prune.COMBINED_OBJ_FAILURE: [],
            Prune.COMBINED_ALL_FAILURE: [],
            Prune.COMBINED_SPECIAL_OBJ_FAILURE: [],
            Prune.COMBINED_SPECIAL_ALL_FAILURE: [],
        }

    def update_planes(
        self, topping: Topping, planes: dict, failures: Prune, floor_substats: List[Type], ceil_substats: List[Type]
    ):
        if Prune.FLOOR_FAILURE in failures:
            for s in floor_substats:
                planes[Prune.FLOOR_FAILURE][s] = max(planes[Prune.FLOOR_FAILURE][s], topping.value(s))
        if Prune.CEILING_FAILURE in failures:
            for s in ceil_substats:
                planes[Prune.CEILING_FAILURE][s] = min(planes[Prune.CEILING_FAILURE][s], topping.value(s))
        if Prune.COMBINED_VALID_FAILURE in failures:
            planes[Prune.COMBINED_VALID_FAILURE].append(tuple(topping.value(s) for s in self.reqs.valid_substats))
        if Prune.COMBINED_OBJ_FAILURE in failures:
            planes[Prune.COMBINED_OBJ_FAILURE].append(
                tuple(topping.value(s) for s in self.reqs.valid_substats) + (topping.value(self.reqs.objective.types),))
        if Prune.COMBINED_ALL_FAILURE in failures:
            planes[Prune.COMBINED_ALL_FAILURE].append(
                tuple(topping.value(s) for s in self.reqs.valid_substats) + (topping.value(self.reqs.all_substats),))
        if Prune.COMBINED_SPECIAL_OBJ_FAILURE in failures:
            planes[Prune.COMBINED_SPECIAL_OBJ_FAILURE].append(
                tuple(topping.value(s) for s in self.reqs.valid_substats) + tuple(topping.value(s) for s in self.reqs.objective.types)
            )
        if Prune.COMBINED_SPECIAL_OBJ_FAILURE in failures:
            planes[Prune.COMBINED_SPECIAL_ALL_FAILURE].append(
                tuple(topping.value(s) for s in self.reqs.valid_substats) + tuple(topping.value(s) for s in self.reqs.objective.types)
            )

    def cut_topping(self, topping: Topping, planes: dict):
        if any(topping.value(s) <= floor for s, floor in planes[Prune.FLOOR_FAILURE].items()):
            return True
        if any(topping.value(s) >= floor for s, floor in planes[Prune.CEILING_FAILURE].items()):
            return True
        if self.is_dominated(topping, planes[Prune.COMBINED_VALID_FAILURE], *self.reqs.valid_substats):
            return True
        if self.is_dominated(topping, planes[Prune.COMBINED_OBJ_FAILURE], *self.reqs.valid_substats,self.reqs.objective.types):
            return True
        if self.is_dominated(topping, planes[Prune.COMBINED_ALL_FAILURE], *self.reqs.valid_substats, self.reqs.all_substats):
            return True
        if self.is_dominated(topping, planes[Prune.COMBINED_SPECIAL_OBJ_FAILURE], *self.reqs.valid_substats, *self.reqs.objective.types):
            return True
        if self.is_dominated(topping, planes[Prune.COMBINED_SPECIAL_ALL_FAILURE], *self.reqs.valid_substats, *self.reqs.objective.types):
            return True
        return False

    def is_dominated(self, topping, plane, *substats):
        return any(all(topping.value(s) <= p[i] for i, s in enumerate(substats)) for p in plane)
