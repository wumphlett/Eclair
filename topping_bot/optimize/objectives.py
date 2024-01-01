from abc import ABC, abstractmethod
from decimal import Decimal, ROUND_UP
from functools import cache
import math
from typing import List


from topping_bot.optimize.toppings import Topping, ToppingSet, Type


class Objective:
    type = None

    def __init__(self, substat: Type):
        self.type = substat

    @property
    @cache
    def types(self):
        return tuple((self.type,))

    def value(self, topping_set: ToppingSet):
        return topping_set.value(self.type)

    def upper(self, combined: Decimal):
        return combined

    def floor(self, topping_set: ToppingSet):
        return topping_set.value(self.type)

    def fancy_value(self, topping_set: ToppingSet):
        return {self.type: self.value(topping_set)}


class Special(Objective, ABC):
    bounds = None

    def __init__(self, *args, **kwargs):
        self.bounds = {substat: {"max": float("inf"), "min": float("-inf")} for substat in self.types}
        super().__init__(*args, **kwargs)

    @abstractmethod
    def special_upper(self, combined: Decimal, full_set: ToppingSet, combo: List[Topping]):
        pass


class Combo(Special):
    def __init__(self, objectives: list, modifiers: dict):
        self.objectives = objectives
        self.mods = {s: mod / Decimal(100) for s, mod in modifiers.items()}
        super().__init__(substat=Type.COMBO)

    @property
    @cache
    def types(self):
        return tuple(self.objectives)

    @cache
    def value(self, topping_set: ToppingSet):
        """Combined value of valued substats"""
        return sum(topping_set.value(substat) for substat in self.objectives)

    def special_upper(self, combined: Decimal, full_set: ToppingSet, combo: List[Topping]):
        """Maximum Combo value possible given combined value pool"""
        combo = ToppingSet(combo)
        for substat in self.objectives:
            combined -= combo.value(substat) - min(  # don't min check, always want to maximize
                combo.value(substat) / Decimal(100), self.bounds[substat]["max"]
            ) * Decimal(100)
        return combined

    @cache
    def upper(self, combined: Decimal):
        """Maximum possible combined value given combined value pool"""
        return combined

    @cache
    def floor(self, topping_set: ToppingSet):
        return self.value(topping_set)

    def fancy_value(self, topping_set: ToppingSet):
        fancy = {Type.COMBO: self.value(topping_set)}
        for substat in self.objectives:
            fancy[substat] = topping_set.value(substat)
        return fancy


class EDMG(Special):
    def __init__(self, modifiers: dict):
        self.base_atk, self.base_crit = modifiers[Type.ATK] / Decimal("100"), modifiers[Type.CRIT] / Decimal("100")
        self.crit_dmg = modifiers[Type.CRIT_DMG] / Decimal("100")
        self.mult = modifiers[Type.ATK_MULT]
        super().__init__(substat=Type.E_DMG)

    @property
    @cache
    def types(self):
        return tuple((Type.ATK, Type.CRIT))

    def e_dmg(self, atk: Decimal, crit: Decimal):
        return (self.crit_dmg - 1) * atk * crit + (1 + self.mult) * atk

    @cache
    def value(self, topping_set: ToppingSet):
        """E[DMG] of a given topping set"""
        atk = topping_set.value(Type.ATK) / Decimal("100") + self.base_atk
        crit = topping_set.value(Type.CRIT) / Decimal("100") + self.base_crit

        return self.e_dmg(atk, crit)

    def special_upper(self, combined: Decimal, full_set: ToppingSet, combo: List[Topping]):
        """Maximum E[DMG] possible given combined atk/crit pool"""
        combo = ToppingSet(combo)
        atk, crit = (
            combo.value(Type.ATK) / Decimal("100") + self.base_atk,
            combo.value(Type.CRIT) / Decimal("100") + self.base_crit,
        )

        combined = combined / Decimal("100") + self.base_atk + self.base_crit
        optimal_atk = (combined * (self.crit_dmg - 1) + (1 + self.mult)) / (2 * (self.crit_dmg - 1))

        ideal_possible_atk = (
            max(min(max(atk, optimal_atk) - self.base_atk, self.bounds[Type.ATK]["max"]), self.bounds[Type.ATK]["min"])
            + self.base_atk
        )
        ideal_possible_crit = (
            max(
                min(max(crit, combined - ideal_possible_atk) - self.base_crit, self.bounds[Type.CRIT]["max"]),
                self.bounds[Type.CRIT]["min"],
            )
            + self.base_crit
        )
        ideal_possible_atk = combined - ideal_possible_crit

        return self.e_dmg(ideal_possible_atk, ideal_possible_crit)

    @cache
    def floor(self, topping_set: ToppingSet):
        """Minimum combined atk/crit pool needed to meet topping set E[DMG]"""
        obj = self.value(topping_set)

        minimum_atk = Decimal(math.sqrt(obj / (self.crit_dmg - 1)))
        minimum_crit = (obj - (1 + self.mult) * minimum_atk) / ((self.crit_dmg - 1) * minimum_atk)

        return ((minimum_atk + minimum_crit - self.base_atk - self.base_crit) * Decimal(100)).quantize(
            Decimal(".1"), rounding=ROUND_UP
        )

    def fancy_value(self, topping_set: ToppingSet):
        crit = min(Decimal(1), topping_set.value(Type.CRIT) / Decimal(100) + self.base_crit)
        rng = Decimal(-float(crit) * math.log2(crit) - float(1 - crit) * math.log2(1 - crit)).quantize(Decimal(".001"))
        return {Type.E_DMG: self.value(topping_set) * 100, Type.RNG: rng * 100}


class Vitality(Special):
    def __init__(self, modifiers: dict):
        self.base_hp, self.base_dmgres = modifiers[Type.HP] / Decimal("100"), modifiers[Type.DMGRES] / Decimal("100")
        super().__init__(substat=Type.VITALITY)

    @property
    @cache
    def types(self):
        return tuple((Type.DMGRES, Type.HP))

    @staticmethod
    def vitality(hp, dmgres):
        return hp * (Decimal(1) / (Decimal(1) - dmgres))

    @cache
    def value(self, topping_set: ToppingSet):
        """Vitality of a given topping set"""
        hp = topping_set.value(Type.HP) / Decimal("100") + self.base_hp
        dmgres = topping_set.value(Type.DMGRES) / Decimal("100") + self.base_dmgres

        return self.vitality(hp, dmgres)

    def special_upper(self, combined: Decimal, full_set: ToppingSet, combo: List[Topping]):
        """Maximum Vitality possible given combined hp/dmgres pool"""
        combo = ToppingSet(combo)
        dmgres = combo.value(Type.DMGRES) / Decimal("100")
        hp = combo.value(Type.HP) / Decimal("100")

        combined = combined / Decimal("100")

        _, bonus = full_set.set_effect(Type.DMGRES)
        obj_count = len([top for top in full_set.toppings[len(combo.toppings) :] if top.flavor == Type.DMGRES])
        max_additional_dmgres = (
            (obj_count * (Decimal("6") + Decimal("4.1"))) + (5 - obj_count - len(combo.toppings)) * Decimal("6") + bonus
        ) / Decimal("100")

        ideal_possible_dmgres = min(
            min(combined, dmgres + max_additional_dmgres), self.bounds[Type.DMGRES]["max"]
        )  # don't min check, always want to maximize
        ideal_possible_hp = max(
            min(max(hp, combined - ideal_possible_dmgres), self.bounds[Type.DMGRES]["max"]),
            self.bounds[Type.DMGRES]["min"],
        )
        ideal_possible_dmgres = combined - ideal_possible_hp

        ideal_possible_hp, ideal_possible_dmgres = (
            ideal_possible_hp + self.base_hp,
            ideal_possible_dmgres + self.base_dmgres,
        )

        return self.vitality(ideal_possible_hp, ideal_possible_dmgres)

    @cache
    def floor(self, topping_set: ToppingSet):
        """Minimum combined hp/dmgres pool needed to meet topping set Vitality"""
        obj = self.value(topping_set)
        hp = self.base_hp

        min_dmg_res = Decimal(1) - (Decimal(1) / (obj / hp))

        return (min_dmg_res - self.base_dmgres * Decimal(100)).quantize(Decimal(".1"), rounding=ROUND_UP)

    def fancy_value(self, topping_set: ToppingSet):
        return {Type.VITALITY: self.value(topping_set) * 100}
