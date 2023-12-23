from collections import defaultdict
from decimal import Decimal
from functools import cache
from typing import Any, List, Tuple

import yaml
from yaml import BaseLoader

from topping_bot.crk.toppings import INFO, Resonance, Substats, Topping, ToppingSet, Type
from topping_bot.optimize.objectives import Special, Combo, EDMG, Vitality, Objective
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
                if type(requirement) is str:
                    valid = cls.parse_valid_requirement(requirement)

                    if valid is None:
                        raise Exception(f"{cookie['name']} : could not parse {requirement}")
                    if type(valid) is Relative and valid.cookie not in cookie_names:
                        raise Exception(f"{cookie['name']} : relative target must be a previously seen cookie")

                    valid_reqs.append(valid)

                elif type(requirement) is dict:
                    if objective is not None:
                        raise Exception(f"{cookie['name']} : only one objective may be specified")
                    if requirement.get("max") is None:
                        raise Exception(f"{cookie['name']} : objective must have the 'max' key")

                    objective = cls.parse_objective_requirement(requirement, cookie_mods)

                    if type(objective) is Combo and not objective.types:
                        raise Exception(f"{cookie['name']} : Combo objective must specify substats")

            cookie_names.add(cookie["name"])
            resonances = [Resonance(resonance) for resonance in cookie.get("resonant", [])] + [Resonance.NORMAL]
            weight = (
                int(requirements["leaderboard"][cookie["name"]])
                if requirements.get("leaderboard", {}).get(cookie["name"])
                else None
            )

            cookies.append(Requirements(cookie["name"], valid_reqs, objective, cookie_mods, resonances, weight=weight))
        return cookies

    @staticmethod
    def parse_valid_requirement(requirement: str):
        for parser in (Normal, Range, Equality, Relative):
            result = parser.parse(requirement)
            if result:
                return result

    @staticmethod
    def parse_objective_requirement(requirement: dict, cookie_mods):
        objective = Type(requirement["max"])

        if objective == Type.COMBO:
            return Combo([Type(substat) for substat in requirement["substats"]])
        elif objective == Type.E_DMG:
            for substat in cookie_mods:
                cookie_mods[substat] += Decimal(requirement.get(substat.value, "0"))
            return EDMG(cookie_mods)
        elif objective == Type.VITALITY:
            for substat in cookie_mods:
                cookie_mods[substat] += Decimal(requirement.get(substat.value, "0"))
            return Vitality(cookie_mods)
        else:
            return Objective(substat=objective)

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

        if isinstance(self.objective, Special):
            bounds = self.objective.bounds
            for req in self.floor_reqs():
                substat, required = req.substat, req.target
                if bounds.get(substat):
                    bounds[substat]["min"] = min(bounds[substat]["min"], required / Decimal("100"))
            for req in self.ceiling_reqs():
                substat, required = req.substat, req.target
                if bounds.get(substat):
                    bounds[substat]["max"] = min(bounds[substat]["max"], required / Decimal("100"))

    @property
    @cache
    def valid_substats(self):
        return tuple(r.substat for r in self.valid if r.op.str == ">=" and r.substat not in self.objective.types)

    @property
    @cache
    def all_substats(self):
        return tuple(set(self.valid_substats + self.objective.types))

    @cache
    def floor(self, substat: Type):
        for req in self.valid:
            if req.substat == substat and req.op.str == ">=":
                return req.target
        return Decimal(0)

    @cache
    def floor_reqs(self):
        return [valid for valid in self.valid if valid.op.str == ">="]

    @cache
    def ceiling_reqs(self):
        return [valid for valid in self.valid if valid.op.str == "<=" and valid.target != Decimal(0)]

    @cache
    def zero_reqs(self):
        return [valid for valid in self.valid if valid.op.str == "<=" and valid.target == Decimal(0)]

    # def fast_non_obj(self, combo: List[Topping], topping: Topping) -> int:
    #     total_non_obj_count = 0
    #     partial_set = ToppingSet(combo + [topping])
    #
    #     for r in self.floor_reqs():  # valid floor check
    #         substat, required = r.substat, r.target
    #
    #         non_obj_count = 0
    #         for obj_count in range(5 - len(combo) + 1)[::-1]:
    #             # if met, break
    #             non_obj_count += 1
    #         if partial_set.value(substat) >= required:
    #             pass
    #
    #     return total_non_obj_count

    def best_possible_set_effect(self, combo: List[Topping], substats: Tuple[Type], non_match_count: int):
        best_set_bonuses = {
            2: Decimal(0),
            3: Decimal(0),
            5: Decimal(0),
        }

        for s in substats:
            for req, bonus in INFO[s]["combos"]:
                if non_match_count <= 5 - req - sum(1 for t in combo if t.flavor not in substats):
                    best_set_bonuses[req] = max(best_set_bonuses[req], bonus)

        return max(best_set_bonuses[2] + best_set_bonuses[3], best_set_bonuses[5])
