import json
import math
from collections import defaultdict
from decimal import Decimal
from pathlib import Path

from topping_bot.optimize.requirements import Requirements


def leaderboard(requirements_fp: Path, leaderboard_fp: Path):
    cookies = Requirements.from_yaml(requirements_fp)

    with open(leaderboard_fp) as f:
        leaderboard_data = json.load(f)

    max_objectives = defaultdict(Decimal)
    for cookie in cookies:
        for team in leaderboard_data.values():
            name = "".join(char for char in cookie.name if char.isalnum())
            max_objectives[cookie.name] = max(max_objectives[cookie.name], Decimal(team[name]))

    for cookie in cookies:
        max_objectives[cookie.name] *= cookie.weight

    entries = []
    benchmark = sum(max_objectives.values())

    for member, team in leaderboard_data.items():
        score = sum(
            Decimal(team["".join(char for char in cookie.name if char.isalnum())]) * cookie.weight for cookie in cookies
        )
        score = score / benchmark * 1_000_000_000
        entries.append((member, math.ceil(score)))

    entries.sort(key=lambda x: -x[1])
    return entries
