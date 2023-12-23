from decimal import Decimal, ROUND_HALF_UP, ROUND_UP

import numpy as np

from topping_bot.util.const import INFO_PATH

gbhps = []
with open(INFO_PATH / "gbhp.txt") as f:
    for gbhp in f.readlines():
        gbhps.append(int(gbhp.replace(",", "")))

adjusted_gbhps = [hp / 5600 for hp in gbhps[30:]]
lvls = list(range(30, len(gbhps)))
EXP, BASE = np.exp(np.polyfit(lvls, np.log(adjusted_gbhps), 1))


gbatks = []
with open(INFO_PATH / "gbatk.txt") as f:
    for gbatk in f.readlines():
        gbatks.append(int(gbatk.replace(",", "")))


def cookie_base_atk(before: int, after: int, diff: Decimal):
    return ((diff * before) / Decimal(after - before)) - 1


def cookie_cd(skill_cd: int, topping_cd: float, watch_buff: float):
    return skill_cd * (1 - topping_cd) * (1 - watch_buff)


def starting_cookie_cd(skill_cd: int, override=False):
    upper_bound = int((Decimal(skill_cd) * (1 if override else Decimal("0.3"))).quantize(0, rounding=ROUND_HALF_UP))
    lower_bound = int(
        (Decimal(skill_cd) * (1 if override else Decimal("0.3")) * (1 - Decimal("0.3"))).quantize(
            0, rounding=ROUND_HALF_UP
        )
    )

    benchmarks = [(Decimal(0), upper_bound)]

    for i in range(lower_bound, upper_bound)[::-1]:
        minimum = Decimal(1) - (Decimal(f"{i}.5") / (Decimal(skill_cd) * (1 if override else Decimal("0.3"))))
        if minimum == 0:
            benchmarks = []
        benchmarks.append(((minimum * 100).quantize(Decimal("0.1"), rounding=ROUND_UP), i))

    return benchmarks


def guild_battle_boss_hp(lvl: int):
    if lvl <= len(gbhps):
        return gbhps[lvl - 1]
    hp = Decimal(BASE) * Decimal(EXP) ** lvl
    return hp.quantize(0, rounding=ROUND_HALF_UP) * 5600


def guild_battle_boss_atk(lvl: int):
    if lvl <= len(gbatks):
        return gbatks[lvl - 1]


def guild_battle_boss_trophies(lvl: int):
    return int(Decimal("2.5") * (lvl**2) + Decimal("42.5") * lvl + 255)


def cpuff_needed_crit(lvl: int, combined: Decimal):
    added = Decimal(".517") * (lvl - 1) + Decimal("10")
    guaranteed_success = Decimal("100") - combined - Decimal("13") - added

    if lvl >= 30:
        divisor = Decimal(".5")
    elif lvl >= 20:
        divisor = Decimal(".35")
    elif lvl >= 10:
        divisor = Decimal(".3")
    else:
        return guaranteed_success, None, added

    capped_cdmg_buff = (Decimal("25") / divisor).quantize(Decimal(1), rounding=ROUND_UP) - Decimal("13")
    return guaranteed_success, capped_cdmg_buff, added
