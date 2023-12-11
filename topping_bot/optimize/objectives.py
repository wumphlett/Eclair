from abc import ABC
from decimal import Decimal, ROUND_UP
from functools import cache
from heapq import nlargest
import math
from typing import Iterable, List


from topping_bot.crk.toppings import Topping, ToppingSet, Type


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

    @staticmethod
    def init_planes():
        return float("-inf"), float("-inf"), []

    @staticmethod
    def valid_cut(valid_plane: float, topping: Topping, valid_substats: Iterable[Type]):
        return topping.value(valid_substats) <= valid_plane

    @staticmethod
    def obj_cut(obj_plane: float, topping: Topping, obj_substats: Iterable[Type]):
        return topping.value(obj_substats) <= obj_plane

    @staticmethod
    def all_cut(all_plane: List, topping: Topping, valid_substats, obj_substats, all_substats):
        return any(
            topping.value(valid_substats) <= min_val and topping.value(all_substats) <= min_all
            for min_val, min_all in all_plane
        )

    @staticmethod
    def update_valid_plane(valid_plane: float, topping: Topping, valid_substats: Iterable[Type]):
        return max(valid_plane, topping.value(valid_substats))

    @staticmethod
    def update_obj_plane(obj_plane: float, topping: Topping, obj_substats: Iterable[Type]):
        return max(obj_plane, topping.value(obj_substats))

    @staticmethod
    def update_all_plane(all_plane: List, topping: Topping, valid_substats, obj_substats, all_substats):
        all_plane.append((topping.value(valid_substats), topping.value(all_substats)))
        return all_plane


class Special(Objective, ABC):
    pass


class Combo(Special):
    def __init__(self, objectives: list):
        self.objectives = objectives
        super().__init__(substat=Type.COMBO)

    @property
    @cache
    def types(self):
        return tuple(self.objectives)

    @cache
    def value(self, topping_set: ToppingSet):
        """Combined value of valued substats"""
        # actual = np.asarray([float(topping_set.value(substat)) for substat in self.objectives])
        # if sum(actual) != 0:
        #     return sum(actual) * (1 - self.mae(self.to_probability(actual), self.target))
        # return 0.
        return sum(topping_set.value(substat) for substat in self.objectives)

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
        self.base_atk, self.base_crit = modifiers[Type.ATK], modifiers[Type.CRIT]
        self.crit_dmg = modifiers[Type.CRIT_DMG] / Decimal("100")
        self.mult = modifiers[Type.ATK_MULT]
        super().__init__(substat=Type.E_DMG)

    @property
    @cache
    def types(self):
        return tuple((Type.ATK, Type.CRIT))

    @cache
    def value(self, topping_set: ToppingSet):
        """E[DMG] of a given topping set"""
        atk = (topping_set.value(Type.ATK) + self.base_atk) / Decimal("100")
        crit = (topping_set.value(Type.CRIT) + self.base_crit) / Decimal("100")

        return self.e_dmg(atk, crit)

    def upper(self, combined: Decimal, full_set: ToppingSet, combo: List[Topping]):
        """Maximum E[DMG] possible given combined atk/crit pool"""
        combined = (combined + self.base_atk + self.base_crit) / Decimal("100")

        optimal_atk = (combined * (self.crit_dmg - 1) + (1 + self.mult)) / (2 * (self.crit_dmg - 1))

        combo = ToppingSet(combo)
        atk, crit = (combo.value(Type.ATK) + self.base_atk) / Decimal("100"), (
            combo.value(Type.CRIT) + self.base_crit
        ) / Decimal("100")

        ideal_possible_atk = max(atk, optimal_atk)
        ideal_possible_crit = combined - ideal_possible_atk

        return self.e_dmg(ideal_possible_atk, ideal_possible_crit)

    @cache
    def floor(self, topping_set: ToppingSet):
        """Minimum combined atk/crit pool needed to meet topping set E[DMG]"""
        obj = self.value(topping_set)

        minimum_atk = Decimal(math.sqrt(obj / (self.crit_dmg - 1)))
        minimum_crit = (obj - (1 + self.mult) * minimum_atk) / ((self.crit_dmg - 1) * minimum_atk)

        return ((minimum_atk + minimum_crit) * Decimal(100) - self.base_atk - self.base_crit).quantize(
            Decimal(".1"), rounding=ROUND_UP
        )

    def fancy_value(self, topping_set: ToppingSet):
        crit = min(
            Decimal(1),
            (topping_set.raw(Type.CRIT) + topping_set.set_effect(Type.CRIT)[1] + self.base_crit) / Decimal(100),
        )
        rng = math.sqrt(crit * (1 - crit))
        return {Type.E_DMG: self.value(topping_set) * 100, Type.RNG: rng * 200}

    def e_dmg(self, atk: Decimal, crit: Decimal):
        crit = min(Decimal(1), crit)
        return (self.crit_dmg - 1) * atk * crit + (1 + self.mult) * atk


class Vitality(Special):
    def __init__(self, modifiers: dict):
        self.base_hp, self.base_dmgres = modifiers[Type.HP], modifiers[Type.DMGRES]
        super().__init__(substat=Type.VITALITY)

    @property
    @cache
    def types(self):
        return tuple((Type.DMGRES, Type.HP))

    @cache
    def value(self, topping_set: ToppingSet):
        """Vitality of a given topping set"""
        hp = (topping_set.value(Type.HP) + self.base_hp) / Decimal("100")
        dmgres = (topping_set.value(Type.DMGRES) + self.base_dmgres) / Decimal("100")

        return self.vitality(hp, dmgres)

    def upper(self, combined: Decimal, full_set: ToppingSet, combo: List[Topping]):
        """Maximum Vitality possible given combined hp/dmgres pool"""
        combo = ToppingSet(combo)
        combined -= combo.value(self.types)
        dmgres, hp = combo.value(Type.DMGRES), combo.value(Type.HP)

        obj_count = len([top for top in full_set.toppings[len(combo.toppings) :] if top.flavor == Type.DMGRES])

        _, bonus = full_set.set_effect(Type.DMGRES)
        max_dmgres = (
            (obj_count * (Decimal("6") + Decimal("4.1"))) + (5 - obj_count - len(combo.toppings)) * Decimal("6") + bonus
        )

        dmgres += min(combined, max_dmgres)
        hp = (hp + combined - min(combined, max_dmgres) + self.base_hp) / Decimal("100")
        dmgres = (dmgres + self.base_dmgres) / Decimal("100")

        return self.vitality(hp, dmgres)

    @cache
    def floor(self, topping_set: ToppingSet):
        """Minimum combined hp/dmgres pool needed to meet topping set Vitality"""
        obj = self.value(topping_set)
        hp = self.base_hp / Decimal("100")

        min_dmg_res = Decimal(1) - (Decimal(1) / (obj / hp))

        return (min_dmg_res * Decimal(100) - self.base_dmgres).quantize(Decimal(".1"), rounding=ROUND_UP)

    def fancy_value(self, topping_set: ToppingSet):
        return {Type.VITALITY: self.value(topping_set) * 100}

    @staticmethod
    def vitality(hp, dmgres):
        return hp * (Decimal(1) / (Decimal(1) - dmgres))

    @staticmethod
    def init_planes():
        return float("-inf"), [], []

    @staticmethod
    def obj_cut(obj_plane: List, topping: Topping, obj_substats: Iterable[Type]):
        return any(
            topping.value(Type.DMGRES) <= min_dmgres and topping.value(Type.HP) <= min_hp
            for min_dmgres, min_hp in obj_plane
        )

    @staticmethod
    def all_cut(all_plane: List, topping: Topping, valid_substats, obj_substats, all_substats):
        return any(
            topping.value(valid_substats) <= min_val
            and topping.value(Type.DMGRES) <= min_dmgres
            and topping.value(Type.HP) <= min_hp
            for min_val, min_dmgres, min_hp in all_plane
        )

    @staticmethod
    def update_obj_plane(obj_plane: List, topping: Topping, obj_substats: Iterable[Type]):
        obj_plane.append((topping.value(Type.DMGRES), topping.value(Type.HP)))
        return obj_plane

    @staticmethod
    def update_all_plane(all_plane: List, topping: Topping, valid_substats, obj_substats, all_substats):
        all_plane.append((topping.value(valid_substats), topping.value(Type.DMGRES), topping.value(Type.HP)))
        return all_plane
