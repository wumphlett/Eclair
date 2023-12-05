import operator
from collections import defaultdict
from copy import deepcopy
from decimal import Decimal
from enum import Flag, auto
from functools import cache
from heapq import nlargest, nsmallest
from typing import Callable, List, Tuple, Union

from tqdm import tqdm

from topping_bot.crk.toppings import INFO, Topping, ToppingSet, Type
from topping_bot.optimize.requirements import Requirements


class Prune(Flag):
    NONE = auto()
    SIMPLE_VALID_FAILURE = auto()
    SIMPLE_OBJECTIVE_FAILURE = auto()
    CONFLICTING_REQUIREMENTS_FAILURE = auto()
    COMBINED_VALID_FAILURE = auto()
    COMBINED_OBJECTIVE_FAILURE = auto()
    COMBINED_ALL_FAILURE = auto()


class Optimizer:
    """Optimizes toppings across multiple cookies"""

    def __init__(self, toppings: List[Topping]):
        self.inventory = toppings
        self.reqs = None
        self.solution = None
        self.toppings = []
        self.cookies = {}

    def select(self, name: str):
        """Select a topping set and remove it from inventory"""
        self.inventory = [topping for topping in self.inventory if topping not in self.solution.toppings]
        self.cookies[name] = self.solution

    def solve(self, reqs: Requirements):
        """Solves a cookies needed toppings given a set of requirements"""
        self.reqs = reqs
        self.reqs.realize(self.cookies)

        self.solution = None

        # filter out to handle resonant toppings
        self.toppings = [topping for topping in self.inventory if topping.resonance in reqs.resonance]

        # filter out zero req case
        self.toppings = [
            topping for topping in self.toppings if not any(topping.value(zero.substat) for zero in reqs.zero_reqs())
        ]

        # presort based on objective requirements to promote finding feasible solution sooner
        self.toppings.sort(key=self._key)

        # ensuring best dmgres is first topping has significant speedup
        if self.reqs.objective.type == Type.VITALITY:
            best_dmgres_top = max(
                self.toppings, key=lambda x: (x.flavor == Type.DMGRES, x.value(self.reqs.all_substats))
            )
            self.toppings.remove(best_dmgres_top)
            self.toppings.insert(0, best_dmgres_top)

        yield from self._dfs([], 0)

    def _key(self, topping: Topping):
        return (
            ~(topping.flavor in self.reqs.objective_substats),
            -len([substat for substat in topping.substats if substat[0] in self.reqs.valid_substats]),
            -topping.value(self.reqs.all_substats),
        )

    def _best_objective(self, candidate: ToppingSet):
        if self.solution is None or self.reqs.objective.value(candidate) > self.reqs.objective.value(self.solution):
            # tqdm.write(f":SOLUTION: {' | '.join([str(topping) for topping in candidate.toppings])}")
            # tqdm.write(str(candidate))
            # tqdm.write(str(candidate.value(self.reqs.objective_substats)))
            # tqdm.write(str(self.reqs.objective.value(candidate)))
            # tqdm.write(str(self.reqs.objective.floor(candidate)))
        if self.solution is None:
            return candidate
        return max(self.solution, candidate, key=lambda x: self.reqs.objective.value(x))

    def _dfs(self, combo: List[Topping], idx):
        """Dfs combination generator, dfs so a benchmark solution is found as soon as possible"""
        if len(combo) == 1:
            # tqdm.write(f"{idx} : {combo[0]} : {self._key(combo[0])}")
            yield combo[0]
        if (reason := self._prune(combo, self.toppings[idx:])) != Prune.NONE:
            # tqdm.write(f"PRUNE : {[str(topping) for topping in combo]}")
            return reason
        if len(combo) == 5:
            topping_set = ToppingSet(combo)
            self.solution = self._best_objective(topping_set)
            return
        if idx == len(self.toppings):
            return

        valid_plane, obj_plane, all_plane = self.reqs.objective.init_planes()

        for i in range(idx, len(self.toppings)):
            if self.reqs.cut_topping(self.toppings[i], valid_plane, obj_plane, all_plane):
                continue

            reason = yield from self._dfs(combo + [self.toppings[i]], i + 1)

            if reason is None:
                continue
            if Prune.COMBINED_VALID_FAILURE in reason:
                valid_plane = self.reqs.objective.update_valid_plane(
                    valid_plane, self.toppings[i], self.reqs.valid_substats
                )
            if Prune.COMBINED_OBJECTIVE_FAILURE in reason:
                obj_plane = self.reqs.objective.update_obj_plane(
                    obj_plane, self.toppings[i], self.reqs.objective_substats
                )
            if Prune.COMBINED_ALL_FAILURE in reason:
                all_plane = self.reqs.objective.update_all_plane(
                    all_plane,
                    self.toppings[i],
                    self.reqs.valid_substats,
                    self.reqs.objective_substats,
                    self.reqs.all_substats,
                )

    def _prune(self, combo: List[Topping], toppings: List[Topping]):
        """Prune a combination subtree from consideration if it is unfavorable"""

        overall_set_requirements = defaultdict(int)
        for req in self.reqs.floor_reqs():
            substat, compare, required = req.substat, req.op.compare, req.target

            req_count = None
            for potential_req_count, potential_set in self._floor_check(combo, toppings, substat):
                if compare(potential_set.value(substat), required):
                    req_count = potential_req_count
                    break

            if req_count is None:
                return Prune.SIMPLE_VALID_FAILURE

            overall_set_requirements[substat] = max(overall_set_requirements.get("substat", float("-inf")), req_count)

        if self.solution and len(combo) != 5:
            req_count = None
            for potential_req_count, potential_combined in self._objective_check(combo, toppings):
                if operator.gt(potential_combined, self.reqs.objective.floor(self.solution)):
                    req_count = potential_req_count
                    break

            if req_count is None:
                return Prune.SIMPLE_OBJECTIVE_FAILURE

            for substat in self.reqs.objective_substats:
                req_count -= overall_set_requirements[substat]
            overall_set_requirements[self.reqs.objective_substats] = req_count

        if sum(count for count in overall_set_requirements.values()) > 5 - len(combo):
            return Prune.CONFLICTING_REQUIREMENTS_FAILURE

        if self.solution and self.reqs.valid and len(combo) != 5:
            combined = self._best_combined_valid_case(combo, toppings, overall_set_requirements)
            if combined is None or combined < 0:
                return Prune.COMBINED_VALID_FAILURE

        # check objective requirements
        failures = Prune.NONE
        if self.solution and len(combo) != 5:
            if self.reqs.objective.type == Type.E_DMG:

                mutable_set_reqs = overall_set_requirements.copy()
                mutable_set_reqs.pop(self.reqs.objective_substats, 0)

                wildcard_count = 6 - len(combo) - sum(count for count in mutable_set_reqs.values())

                all_value_met = False
                mutable_set_reqs[Type.ATK] = mutable_set_reqs[Type.ATK] + wildcard_count - 1

                for _ in range(wildcard_count):
                    # combined = self._best_combined_all_case(combo, toppings, mutable_set_reqs)
                    # if combined is not None:
                    #     if combined > 0:
                    #         all_value_met = True
                    #         break

                    full_set = self._best_combined_case(combo, toppings, mutable_set_reqs, self.reqs.all_substats)
                    if full_set is not None:
                        combined = full_set.value(self.reqs.all_substats) - sum(
                            self.reqs.floor(substat) for substat in self.reqs.valid_substats
                        )
                        if combined > 0 and self.reqs.objective.upper(
                                combined, full_set, combo
                        ) > self.reqs.objective.value(self.solution):
                            all_value_met = True
                            break

                    mutable_set_reqs[Type.CRIT] += 1
                    mutable_set_reqs[Type.ATK] -= 1

                if not all_value_met:
                    failures |= Prune.COMBINED_ALL_FAILURE

                mutable_set_reqs = overall_set_requirements.copy()
                mutable_set_reqs.pop(self.reqs.objective_substats, 0)

                obj_value_met = False
                mutable_set_reqs[Type.ATK] = mutable_set_reqs[Type.ATK] + wildcard_count - 1

                for _ in range(wildcard_count):
                    # combined = self._best_combined_objective_case(combo, toppings, mutable_set_reqs)
                    # if combined is not None:
                    #     if combined > 0:
                    #         obj_value_met = True
                    #         break

                    full_set = self._best_combined_case(combo, toppings, mutable_set_reqs, self.reqs.objective_substats)
                    if full_set is not None:
                        combined = full_set.value(self.reqs.objective_substats)
                        if combined > 0 and self.reqs.objective.upper(
                                combined, full_set, combo
                        ) > self.reqs.objective.value(self.solution):
                            obj_value_met = True
                            break

                    mutable_set_reqs[Type.CRIT] += 1
                    mutable_set_reqs[Type.ATK] -= 1

                if not obj_value_met:
                    failures |= Prune.COMBINED_OBJECTIVE_FAILURE

            elif self.reqs.objective.type == Type.VITALITY:

                mutable_set_reqs = overall_set_requirements.copy()
                mutable_set_reqs.pop(self.reqs.objective_substats, 0)

                wildcard_count = 6 - len(combo) - sum(count for count in mutable_set_reqs.values())

                all_value_met = False
                mutable_set_reqs[Type.DMGRES] = mutable_set_reqs[Type.DMGRES] + wildcard_count - 1

                for _ in range(wildcard_count):
                    full_set = self._best_combined_case(combo, toppings, mutable_set_reqs, self.reqs.all_substats)
                    if full_set is not None:
                        combined = full_set.value(self.reqs.all_substats) - sum(
                            self.reqs.floor(substat) for substat in self.reqs.valid_substats
                        )
                        if combined > 0 and self.reqs.objective.upper(
                            combined, full_set, combo
                        ) > self.reqs.objective.value(self.solution):
                            all_value_met = True
                            break

                    mutable_set_reqs[Type.DMGRES] -= 1

                if not all_value_met:
                    failures |= Prune.COMBINED_ALL_FAILURE

                mutable_set_reqs = overall_set_requirements.copy()
                mutable_set_reqs.pop(self.reqs.objective_substats, 0)

                obj_value_met = False
                mutable_set_reqs[Type.DMGRES] = mutable_set_reqs[Type.DMGRES] + wildcard_count - 1

                for _ in range(wildcard_count):
                    full_set = self._best_combined_case(combo, toppings, mutable_set_reqs, self.reqs.objective_substats)
                    if full_set is not None:
                        combined = full_set.value(self.reqs.objective_substats)
                        if combined > 0 and self.reqs.objective.upper(
                            combined, full_set, combo
                        ) > self.reqs.objective.value(self.solution):
                            obj_value_met = True
                            break

                    mutable_set_reqs[Type.DMGRES] -= 1

                if not obj_value_met:
                    failures |= Prune.COMBINED_OBJECTIVE_FAILURE

            else:
                combined = self._best_combined_all_case(combo, toppings, overall_set_requirements)
                if combined is None or combined <= 0:
                    failures |= Prune.COMBINED_ALL_FAILURE

                combined = self._best_combined_objective_case(combo, toppings, overall_set_requirements)
                if combined is None or combined <= 0:
                    failures |= Prune.COMBINED_OBJECTIVE_FAILURE

        for req in self.reqs.ceiling_reqs():
            substat, compare, required = req.substat, req.op.compare, req.target

            potential_set = self._ceiling_check(combo, toppings, substat)
            if potential_set is None or not compare(potential_set.value(substat), required):
                failures |= Prune.SIMPLE_VALID_FAILURE

        return failures

    @staticmethod
    def _floor_check(combo: List[Topping], toppings: List[Topping], substats: Union[Type, Tuple[Type]]):
        if len(combo) == 5:
            yield 0, ToppingSet(combo)
            return

        substats = substats if type(substats) == tuple else (substats,)
        match_set = [topping for topping in toppings if topping.flavor in substats]
        wild_set = [topping for topping in toppings if topping.flavor not in substats]

        for match_count in range(6 - len(combo)):
            wild_count = 5 - len(combo) - match_count

            potential_set = ToppingSet(
                combo.copy()
                + nlargest(match_count, match_set, key=lambda x: x.value(substats))
                + nlargest(wild_count, wild_set, key=lambda x: x.value(substats))
            )

            if len(potential_set.toppings) == 5:
                yield match_count, potential_set

    @staticmethod
    def _ceiling_check(combo: List[Topping], toppings: List[Topping], substats: Union[Type, Tuple[Type]]):
        if len(combo) == 5:
            return ToppingSet(combo)

        substats = substats if type(substats) == tuple else (substats,)

        potential_set = ToppingSet(combo.copy() + nsmallest(5 - len(combo), toppings, key=lambda x: x.value(substats)))

        if len(potential_set.toppings) == 5:
            return potential_set

    def _objective_check(self, combo: List[Topping], toppings: List[Topping]):
        match_set = [topping for topping in toppings if topping.flavor in self.reqs.objective_substats]
        wild_set = [topping for topping in toppings if topping.flavor not in self.reqs.objective_substats]

        for match_count in range(6 - len(combo)):
            wild_count = 5 - len(combo) - match_count

            potential_set = ToppingSet(
                combo.copy()
                + nlargest(match_count, match_set, key=lambda x: x.value(self.reqs.objective_substats))
                + nlargest(wild_count, wild_set, key=lambda x: x.value(self.reqs.objective_substats))
            )

            if len(potential_set.toppings) == 5:
                yield match_count, sum(
                    potential_set.raw(substat) for substat in self.reqs.objective_substats
                ) + self.reqs.best_possible_set_effect(wild_count)

    @staticmethod
    def _best_combined_case(combo: List[Topping], toppings: List[Topping], set_reqs: dict, key):
        partial_set = combo.copy()

        for substats, req_count in set_reqs.items():
            if req_count:
                substats = substats if type(substats) == tuple else (substats,)
                match_set = [top for top in toppings if top.flavor in substats]
                partial_set += nlargest(req_count, match_set, key=lambda x: x.value(key))

        if len(partial_set) != 5:
            remaining_set = set(toppings).difference(set(partial_set))
            full_set = partial_set + nlargest(5 - len(partial_set), remaining_set, key=lambda x: x.value(key))
        else:
            full_set = partial_set

        if len(full_set) == 5:
            full_set = ToppingSet(full_set)

            return full_set
        return None

    def _best_combined_valid_case(self, combo: List[Topping], toppings: List[Topping], set_reqs: dict):
        full_set = self._best_combined_case(combo, toppings, set_reqs, self.reqs.valid_substats)

        if full_set is not None:
            return full_set.value(self.reqs.valid_substats) - sum(
                self.reqs.floor(substat) for substat in self.reqs.valid_substats
            )
        return None

    def _best_combined_all_case(self, combo: List[Topping], toppings: List[Topping], set_reqs: dict):
        full_set = self._best_combined_case(combo, toppings, set_reqs, self.reqs.all_substats)

        if full_set is not None:
            return (
                full_set.value(self.reqs.all_substats)
                - sum(self.reqs.floor(substat) for substat in self.reqs.valid_substats)
                - self.reqs.objective.floor(self.solution)
            )
        return None

    def _best_combined_objective_case(self, combo: List[Topping], toppings: List[Topping], set_reqs: dict):
        full_set = self._best_combined_case(combo, toppings, set_reqs, self.reqs.objective_substats)

        if full_set is not None:
            return full_set.value(self.reqs.objective_substats) - self.reqs.objective.floor(self.solution)
        return None
