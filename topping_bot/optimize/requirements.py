from collections import defaultdict
from decimal import Decimal
from functools import cache
from typing import Any, List

import yaml
from yaml import BaseLoader

from topping_bot.crk.toppings import INFO, Resonance, ToppingSet, Type
from topping_bot.optimize.objectives import Combo, EDMG, Vitality, Objective
from topping_bot.optimize.validity import Normal, Range, Equality, Relative
from topping_bot.util.const import TMP_PATH


DEFAULT_MODIFIERS = {
    Type.ATK: {
        "Base": Decimal(100),
    },
    Type.CRIT: {
        "Base": Decimal(5),
        "Eerie Haunted House Landmark": Decimal(8),
    },
    Type.CRIT_DMG: {
        "Base": Decimal(150),
        "CRIT DMG Bonus Lab": Decimal(20),
        "Chocolate Alter of the Fallen Landmark": Decimal(20),
    },
    Type.HP: {"Base": Decimal(100)},
}


def sanitize(requirements_fp, user_id=0, rem_leaderboard=False):
    tmp = TMP_PATH / f"{user_id}.yaml"

    with open(requirements_fp) as f:
        requirements = yaml.safe_load(f)

    if rem_leaderboard:
        requirements.pop("leaderboard", None)

    for cookie in requirements.get("cookies", []):
        for i, requirement in enumerate(cookie.get("requirements", [])):
            if type(requirement) == dict and requirement.get("max") and requirement["max"] == "E[Vit]":
                converted_req = {"max": "Vitality"}
                for substat, value in requirement.items():
                    if substat != "max":
                        converted_req[substat] = value
                cookie["requirements"][i] = converted_req

    filtered_mods = {}
    for substat, mods in requirements.get("modifiers", {}).items():
        filtered_substat = [mod for mod in mods if mod["source"] not in DEFAULT_MODIFIERS.get(Type(substat), {})]
        if filtered_substat:
            filtered_mods[substat] = filtered_substat
    if filtered_mods:
        requirements["modifiers"] = filtered_mods

    with open(tmp, "w") as f:
        yaml.safe_dump(requirements, f, indent=2, sort_keys=False)

    return tmp


class Requirements:
    def __init__(self, name: str, valid: List, objective: Any, mods: dict, resonance: List, weight: int = None):
        if not objective:
            raise Exception(f"{name} : one objective must be specified")
        self.name = name
        self.valid = valid
        self.objective = objective
        self.mods = mods
        self.resonance = resonance
        self.weight = weight

    def __str__(self):
        result = f"**{self.name.upper()}**"
        result += "\n```"
        if self.valid:
            result += "\nValidity"
            for valid in self.valid:
                result += f"\n├ {str(valid)}"
        result += "\nObjective"
        result += f"\n├ max {self.objective.type.value}"
        if self.objective.type == Type.COMBO:
            for substat in self.objective.objectives:
                result += f"\n  ↳ {substat.value}"
        return result + "```"

    @property
    @cache
    def valid_substats(self):
        return tuple(
            req.substat for req in self.valid if req.op.str == ">=" and req.substat not in self.objective_substats
        )

    @property
    @cache
    def objective_substats(self):
        return self.objective.types

    @property
    @cache
    def all_substats(self):
        return tuple(set(self.valid_substats + self.objective_substats))

    @cache
    def floor(self, substat: Type):
        for req in self.valid:
            if type(req) == Normal and req.substat == substat and req.op.str == ">=":
                return req.target
        return Decimal(0)

    @cache
    def floor_reqs(self):
        return [valid for valid in self.valid if valid.op.str == ">="]

    @cache
    def ceiling_reqs(self):
        return [valid for valid in self.valid if valid.op.str == "<="]

    @cache
    def zero_reqs(self):
        return [valid for valid in self.valid if valid.op.str == "<=" and valid.target == Decimal(0)]

    def non_objective_count(self, topping_set: ToppingSet):
        return sum(1 for topping in topping_set.toppings if topping.flavor not in self.objective_substats)

    def cut_topping(self, topping, valid_plane, obj_plane, all_plane):
        if self.objective.valid_cut(valid_plane, topping, self.valid_substats):
            return True
        if self.objective.obj_cut(obj_plane, topping, self.objective_substats):
            return True
        if self.objective.all_cut(all_plane, topping, self.valid_substats, self.objective_substats, self.all_substats):
            return True
        return False

    @cache
    def best_possible_set_effect(self, non_match_count: int):
        best_bonus = Decimal(0)
        for substat in self.objective_substats:
            for req, bonus in INFO[substat]["combos"]:
                if non_match_count <= 5 - req:
                    best_bonus = max(best_bonus, bonus)
        return best_bonus

    def realize(self, cookie_sets: dict):
        self.valid = [req for valid in self.valid for req in valid.convert(cookies=cookie_sets)]

        collapsed = {}
        for valid in self.valid:
            valid.fuzz()

            if collapsed.get(valid):
                extreme = max if valid.op.str == ">=" else min
                collapsed[valid] = extreme(collapsed[valid], valid, key=lambda x: x.target)  # noqa
            else:
                collapsed[valid] = valid

        self.valid = list(collapsed.values())

    @classmethod
    def from_yaml(cls, fp):
        """Loads cookie requirements from a properly formatted yaml file"""
        with open(fp) as f:
            requirements = yaml.load(f, BaseLoader)

        mods = defaultdict(Decimal)
        for stat, buffs in DEFAULT_MODIFIERS.items():
            for source, value in buffs.items():
                mods[stat] += value

        for stat, buffs in requirements.get("modifiers", {}).items():
            for buff in buffs:
                mods[Type(stat)] += Decimal(buff["value"])

        cookies = []
        cookie_names = set()

        for cookie in requirements["cookies"]:

            cookie_mods = mods.copy()
            valid_reqs, objective = [], None

            for requirement in cookie["requirements"]:
                if type(requirement) == str:

                    valid = None
                    for parser in (Normal, Range, Equality, Relative):
                        result = parser.parse(requirement)
                        if result:
                            valid = result

                    if valid is None:
                        raise Exception(f"{cookie['name']} : could not parse {requirement}")
                    if type(valid) == Relative and valid.cookie not in cookie_names:
                        raise Exception(f"{cookie['name']} : relative target must be a previously seen cookie")

                    valid_reqs.append(valid)

                elif type(requirement) == dict:
                    if objective is not None:
                        raise Exception(f"{cookie['name']} : only one objective may be specified")
                    if requirement.get("max") is None:
                        raise Exception(f"{cookie['name']} : objective must have the 'max' key")

                    objective = Type(requirement["max"])

                    if objective == Type.COMBO:
                        substats = [Type(substat) for substat in requirement["substats"]]
                        if not substats:
                            raise Exception(f"{cookie['name']} : Combo objective must specify substats")
                        objective = Combo([Type(substat) for substat in requirement["substats"]])
                    elif objective == Type.E_DMG:
                        for substat in cookie_mods:
                            cookie_mods[substat] += Decimal(requirement.get(substat.value, "0"))
                        objective = EDMG(cookie_mods)
                    elif objective == Type.VITALITY:
                        for substat in cookie_mods:
                            cookie_mods[substat] += Decimal(requirement.get(substat.value, "0"))
                        objective = Vitality(cookie_mods)
                    else:
                        objective = Objective(substat=objective)

            cookie_names.add(cookie["name"])
            resonances = [Resonance(resonance) for resonance in cookie.get("resonant", [])] + [Resonance.NORMAL]
            weight = (
                int(requirements["leaderboard"][cookie["name"]])
                if requirements.get("leaderboard", {}).get(cookie["name"])
                else None
            )

            cookies.append(Requirements(cookie["name"], valid_reqs, objective, cookie_mods, resonances, weight=weight))
        return cookies
