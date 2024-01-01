from datetime import datetime
from heapq import nlargest, nsmallest
from typing import Iterable, List

from tqdm import tqdm

from topping_bot.optimize.toppings import Substats, Topping, ToppingSet, Type
from topping_bot.optimize.cutter import Prune, Cutter
from topping_bot.optimize.objectives import Special
from topping_bot.optimize.requirements import Requirements
from topping_bot.util.const import DEBUG


class Optimizer:
    """Optimizes toppings across multiple cookies"""

    def __init__(self, toppings: List[Topping]):
        self.inventory = toppings
        self.reqs = None
        self.solution = None
        self.cutter = None
        self.toppings = []
        self.cookies = {}

    def select(self, name: str):
        """Select a topping set and remove it from inventory"""
        self.inventory = [topping for topping in self.inventory if topping not in self.solution.toppings]
        self.cookies[name] = self.solution

    def set_solution(self, indices: List[int]):
        self.solution = ToppingSet([self.inventory[i] for i in indices])

    def solve(self, reqs: Requirements):
        """Solves a cookies needed toppings given a set of requirements"""
        self.reqs = reqs
        self.reqs.realize(self.cookies)

        self.solution = None
        self.cutter = Cutter(reqs)

        # filter out to handle resonant toppings
        self.toppings = [t for t in self.inventory if t.resonance in reqs.resonance]

        # filter out zero req case
        self.toppings = [t for t in self.toppings if not any(t.value(zero.substat) for zero in reqs.zero_reqs())]

        # presort based on objective requirements to promote finding feasible solution sooner
        self.toppings.sort(key=self.key)

        start = datetime.now()
        yield from self.dfs([], 0)
        DEBUG and tqdm.write(f"{reqs.name} : {(datetime.now() - start).total_seconds()}s")

    def key(self, topping: Topping):
        if self.reqs.objective.type == Type.VITALITY:
            return (
                ~(topping.flavor == Type.DMGRES),
                ~(topping.flavor in self.reqs.objective.types),
                -len([substat for substat in topping.substats if substat[0] in self.reqs.valid_substats]),
                -topping.value(self.reqs.all_substats),
            )
        else:
            return (
                ~(topping.flavor in self.reqs.objective.types),
                -len([substat for substat in topping.substats if substat[0] in self.reqs.valid_substats]),
                -topping.value(self.reqs.all_substats),
            )

    def best_objective(self, candidate: ToppingSet):
        # if self.solution is None or self.reqs.objective.value(candidate) > self.reqs.objective.value(self.solution):
        #     tqdm.write(f":SOLUTION: {' | '.join([str(topping) for topping in candidate.toppings])}")
        #     tqdm.write(str(candidate))
        #     tqdm.write(str(self.reqs.objective.value(candidate)))
        #     tqdm.write(str(self.reqs.objective.floor(candidate)))
        if self.solution is None:
            return candidate
        return max(self.solution, candidate, key=lambda x: self.reqs.objective.value(x))

    def dfs(self, combo: List[Topping], idx):
        """Dfs combination generator, dfs so a benchmark solution is found as soon as possible"""
        if len(combo) == 1:
            # tqdm.write(f"{idx} : {combo[0]} : {self.key(combo[0])}")
            yield combo[0]
        if (reason := self.prune(combo, self.toppings[idx:]))[0] != Prune.NONE:
            # tqdm.write(f"PRUNE : {reason} : {[str(topping) for topping in combo]}")
            return reason
        if len(combo) == 5:
            self.solution = self.best_objective(ToppingSet(combo))
            return
        if idx == len(self.toppings):
            return

        planes = self.cutter.init_planes()
        for i in range(idx, len(self.toppings)):
            if self.cutter.cut_topping(self.toppings[i], planes):
                continue

            reason = yield from self.dfs(combo + [self.toppings[i]], i + 1)

            if reason is None:
                continue

            self.cutter.update_planes(self.toppings[i], planes, *reason)

    def prune(self, combo: List[Topping], toppings: List[Topping]):
        """Prune a combination subtree from consideration if it is unfavorable"""
        failures = Prune.NONE

        floor_failures = []
        overall_set_requirements = {}
        for r in self.reqs.floor_reqs():  # valid floor check
            substat, required = r.substat, r.target

            for potential_req_count, potential_set in self.floor_case(combo, toppings, substat):
                if potential_set.value(substat) >= required:
                    overall_set_requirements[substat] = potential_req_count
                    break

            if overall_set_requirements.get(substat) is None:
                failures |= Prune.FLOOR_FAILURE
                floor_failures.append(substat)

        ceil_failures = []
        for r in self.reqs.ceiling_reqs():  # valid ceiling check
            substat, compare, required = r.substat, r.op.compare, r.target

            potential_set = self.ceiling_case(combo, toppings, substat)
            if potential_set is None or not compare(potential_set.value(substat), required):
                failures |= Prune.CEILING_FAILURE
                ceil_failures.append(substat)

        if self.solution and len(combo) != 5:  # objective floor check
            for potential_req_count, potential_combined, _ in self.objective_case(combo, toppings):
                if potential_combined > self.reqs.objective.floor(self.solution):
                    existing_req = sum(overall_set_requirements.get(s, 0) for s in self.reqs.objective.types)
                    overall_set_requirements[self.reqs.objective.types] = max(potential_req_count - existing_req, 0)
                    break

            if overall_set_requirements.get(self.reqs.objective.types) is None:
                failures |= Prune.FLOOR_FAILURE
                floor_failures.append(self.reqs.objective.types)

        if sum(overall_set_requirements.values()) > 5 - len(combo):  # combined topping req count check
            failures |= Prune.CONFLICTING_REQS_FAILURE

        if self.solution and len(combo) != 5:
            combined = self.combined_valid_case(combo, toppings, overall_set_requirements)
            if combined is None or combined < 0:  # partial informed combined valid check
                failures |= Prune.COMBINED_VALID_FAILURE

            combined = self.combined_obj_case(combo, toppings, overall_set_requirements)
            if combined is None or combined < 0:  # partial informed combined obj check
                failures |= Prune.COMBINED_OBJ_FAILURE

            combined = self.combined_all_case(combo, toppings, overall_set_requirements)
            if combined is None or combined < 0:  # partial informed combined all check
                failures |= Prune.COMBINED_ALL_FAILURE

            if isinstance(self.reqs.objective, Special):
                overall_set_requirements.pop(self.reqs.objective.types, None)

                obj_value_met = False
                for full_set in self.obj_special_case(combo, toppings, overall_set_requirements):
                    combined = full_set.value(self.reqs.objective.types)  # partial informed special obj check
                    if combined > 0 and self.reqs.objective.special_upper(
                        combined, full_set, combo
                    ) > self.reqs.objective.value(self.solution):
                        obj_value_met = True
                        break

                if not obj_value_met:
                    failures |= Prune.COMBINED_SPECIAL_OBJ_FAILURE

                all_value_met = False
                for full_set in self.all_special_case(combo, toppings, overall_set_requirements):
                    combined = full_set.value(self.reqs.all_substats) - sum(  # partial informed special all check
                        self.reqs.floor(s) for s in self.reqs.valid_substats
                    )
                    if combined > 0 and self.reqs.objective.special_upper(
                        combined, full_set, combo
                    ) > self.reqs.objective.value(self.solution):
                        all_value_met = True
                        break

                if not all_value_met:
                    failures |= Prune.COMBINED_SPECIAL_ALL_FAILURE

        return failures, floor_failures, ceil_failures

    def floor_pool(self, n: int, pool: Iterable[Topping], substats):
        return nlargest(n, pool, key=lambda x: x.value(substats))

    def fill_out_combo(self, combo: List[Topping], toppings: List[Topping], substats: Substats, set_reqs: dict):
        base_n = len(combo)
        combo = combo.copy()
        for req_substats, req_count in set_reqs.items():
            if req_count:
                req_substats = req_substats if type(req_substats) is tuple else (req_substats,)
                match_set = (topping for topping in toppings if topping.flavor in req_substats)
                combo += self.floor_pool(req_count, match_set, substats)

        if len(combo) == base_n + sum(set_reqs.values()):
            return combo

    def floor_case(self, combo: List[Topping], toppings: List[Topping], substats: Substats):
        if len(combo) == 5:
            yield 0, ToppingSet(combo)
            return

        n = 5 - len(combo)
        substats = substats if type(substats) is tuple else (substats,)
        match_pool = self.floor_pool(n, (topping for topping in toppings if topping.flavor in substats), substats)
        wild_pool = self.floor_pool(n, (topping for topping in toppings if topping.flavor not in substats), substats)

        for match_count in range(n + 1):
            wild_count = n - match_count

            potential_set = combo + match_pool[:match_count] + wild_pool[:wild_count]
            if len(potential_set) == 5:
                yield match_count, ToppingSet(potential_set)

    def ceiling_case(self, combo: List[Topping], toppings: List[Topping], substats: Substats):
        if len(combo) == 5:
            return ToppingSet(combo)

        substats = substats if type(substats) is tuple else (substats,)

        potential_set = combo + nsmallest(5 - len(combo), toppings, key=lambda x: x.value(substats))
        if len(potential_set) == 5:
            return ToppingSet(potential_set)

    def objective_case(self, combo: List[Topping], toppings: List[Topping]):
        for potential_req_count, potential_set in self.floor_case(combo, toppings, self.reqs.objective.types):
            unmatched_count = 5 - potential_req_count
            potential_value = sum(potential_set.raw(s) for s in self.reqs.objective.types)
            potential_value += self.reqs.best_possible_set_effect(combo, self.reqs.objective.types, 5 - unmatched_count)
            yield potential_req_count, potential_value, potential_set

    def combined_case(self, combo: List[Topping], toppings: List[Topping], substats: Substats, set_reqs: dict = None):
        if set_reqs is not None:
            combo = self.fill_out_combo(combo, toppings, substats, set_reqs)

            if combo is None:
                return None

        if len(combo) != 5:
            remaining_set = set(toppings).difference(set(combo))
            full_set = combo + self.floor_pool(5 - len(combo), remaining_set, substats)
        else:
            full_set = combo

        if len(full_set) == 5:
            return ToppingSet(full_set)

    def combined_value(self, combo: List[Topping], toppings: List[Topping], substats: Substats, set_reqs: dict = None):
        full_set = self.combined_case(combo, toppings, substats, set_reqs)
        if full_set is None:
            return

        full_value = sum(full_set.raw(s) for s in substats)
        full_value += self.reqs.best_possible_set_effect(combo, substats, 0)
        return full_value

    def combined_valid_case(self, combo: List[Topping], toppings: List[Topping], set_reqs: dict):
        full_value = self.combined_value(combo, toppings, self.reqs.valid_substats, set_reqs)

        if full_value is not None:
            return full_value - sum(self.reqs.floor(s) for s in self.reqs.valid_substats)

    def combined_obj_case(self, combo: List[Topping], toppings: List[Topping], set_reqs: dict):
        full_value = self.combined_value(combo, toppings, self.reqs.objective.types, set_reqs)

        if full_value is not None:
            return full_value - self.reqs.objective.floor(self.solution)

    def combined_all_case(self, combo: List[Topping], toppings: List[Topping], set_reqs: dict):
        full_value = self.combined_value(combo, toppings, self.reqs.all_substats, set_reqs)

        if full_value is not None:
            return (
                full_value
                - sum(self.reqs.floor(s) for s in self.reqs.valid_substats)
                - self.reqs.objective.floor(self.solution)
            )

    def sum_to_n(self, n, size):
        if size == 1:
            yield [n]
            return

        for i in range(0, n + 1):
            for tail in self.sum_to_n(n - i, size - 1):
                yield [i] + tail

    def special_case(self, combo: List[Topping], toppings: List[Topping], substats: Substats, set_reqs: dict = None):
        if set_reqs is not None:
            combo = self.fill_out_combo(combo, toppings, substats, set_reqs)
            if combo is None:
                return

        if len(combo) != 5:
            remaining_set = set(toppings).difference(set(combo))

            n = 5 - len(combo)
            pools = [
                self.floor_pool(n, (topping for topping in remaining_set if topping.flavor == s), substats)
                for s in self.reqs.objective.types
            ]

            for partitions in self.sum_to_n(n, len(pools)):
                potential_set = combo.copy()
                for i, partition in enumerate(partitions):
                    potential_set += pools[i][:partition]

                if len(potential_set) == 5:
                    yield ToppingSet(potential_set)
        else:
            yield ToppingSet(combo)

    def obj_special_case(self, combo: List[Topping], toppings: List[Topping], set_reqs: dict):
        yield from self.special_case(combo, toppings, self.reqs.objective.types, set_reqs)

    def all_special_case(self, combo: List[Topping], toppings: List[Topping], set_reqs: dict):
        yield from self.special_case(combo, toppings, self.reqs.all_substats, set_reqs)
