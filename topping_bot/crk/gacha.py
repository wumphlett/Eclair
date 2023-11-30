from collections import defaultdict
from itertools import accumulate
import random

import json
import yaml

from topping_bot.crk.cookies import Cookie, Rarity
from topping_bot.util.const import DATA_PATH, INFO_PATH, STATIC_PATH


TIERS = [20, 20, 30, 50, 70, 100, 20, 30, 40, 50, 60]
GRADES = [None, "1", "2", "3", "4", "5", "a1", "a2", "a3", "a4", "a5"]
FANCY_GRADES = ["fancy_0", "fancy_1", "fancy_2", "fancy_3", "fancy_4", "fancy_5", "a1", "a2", "a3", "a4", "a5"]
MILAGE = {
    Rarity.COMMON: {"base": 1, "ascend": 2, "duplicate": 6},
    Rarity.RARE: {"base": 2, "ascend": 4, "duplicate": 15},
    Rarity.EPIC: {"base": 5, "ascend": 10, "duplicate": 40},
    Rarity.SUPER_EPIC: {"base": 7, "ascend": 14, "duplicate": 50},
    Rarity.SPECIAL: {"base": 10, "ascend": 20, "duplicate": 60},
    Rarity.LEGENDARY: {"base": 10, "ascend": 20, "duplicate": 60},
    Rarity.DRAGON: {"base": 10, "ascend": 20, "duplicate": 60},
    Rarity.ANCIENT: {"base": 10, "ascend": 20, "duplicate": 60},
}

random.seed()


class Gacha:
    def __init__(self, pulls, last_cookie, last_epic, inventory):
        self.pulls = pulls
        self.since_last_cookie = last_cookie
        self.since_last_epic = last_epic
        self.inventory = defaultdict(int, inventory)

    def is_unlocked(self, pk: str):
        return self.inventory[pk] >= 20

    def is_unlock(self, inv, amount):
        return inv < 20 <= inv + amount

    def is_ascended(self, pk: str):
        return self.inventory[pk] >= 290

    def is_maxed(self, pk: str):
        return self.inventory[pk] >= 490

    def fraction(self, stored: int):
        cumulative = 0
        for tier in TIERS:
            cumulative += tier

            if stored < cumulative:
                return stored - cumulative + tier, tier

        return 1, 1

    def grade(self, pk: str):
        grades = list(accumulate(TIERS))
        for i, grade in enumerate(grades[1:]):
            if self.inventory[pk] < grade:
                return STATIC_PATH / "misc" / "grade" / f"{GRADES[i]}.png"
        return STATIC_PATH / "misc" / "grade" / "a5.png"

    def fancy_grade(self, pk: str):
        grades = list(accumulate(TIERS))
        for i, grade in enumerate(grades[1:]):
            if self.inventory[pk] < grade:
                return STATIC_PATH / "misc" / "grade" / f"{FANCY_GRADES[i]}.png"
        return STATIC_PATH / "misc" / "grade" / "a5.png"

    @classmethod
    def load_history(cls, user_id):
        data_fp = DATA_PATH / f"{user_id}.json"

        if data_fp.exists():
            with open(data_fp) as f:
                data = json.load(f)
            gacha = Gacha(**data)
        else:
            gacha = Gacha(0, 0, 0, {})

        return gacha

    def save_history(self, user_id):
        data_fp = DATA_PATH / f"{user_id}.json"

        with open(data_fp, "w") as f:
            data = {
                "pulls": self.pulls,
                "last_cookie": self.since_last_cookie,
                "last_epic": self.since_last_epic,
                "inventory": self.inventory,
            }
            json.dump(data, f)

    def simulate(self):
        if self.since_last_epic == 99:
            selected_rarity = (Rarity.EPIC,)
        elif self.since_last_cookie == 9:
            if random.randint(1, 10) == 1:
                selected_rarity = (Rarity.EPIC,)
            else:
                selected_rarity = (Rarity.RARE,)
        else:
            roll = random.randint(1, 100_000)
            if roll <= 2536:
                selected_rarity = (Rarity.ANCIENT, Rarity.LEGENDARY, Rarity.DRAGON)
            elif roll <= 21_816:
                selected_rarity = (Rarity.SUPER_EPIC, Rarity.EPIC)
            elif roll <= 58_748:
                selected_rarity = (Rarity.RARE,)
            elif roll <= 99_500:
                selected_rarity = (Rarity.COMMON,)
            else:
                selected_rarity = (Rarity.SPECIAL,)

        is_cookie_pull = self.since_last_epic == 99 or self.since_last_cookie == 9 or random.randint(1, 7) == 1

        if Rarity.EPIC in selected_rarity and is_cookie_pull:
            self.since_last_epic = 0
        else:
            self.since_last_epic += 1

        if is_cookie_pull and Rarity.COMMON not in selected_rarity:
            self.since_last_cookie = 0
        else:
            self.since_last_cookie += 1

        soulstones = 20 if is_cookie_pull else random.randint(1, 3)

        if Rarity.EPIC in selected_rarity and random.randint(1, 8) <= len(Cookie.featured()):
            cookie = random.choice(Cookie.featured())
        elif selected_rarity == (Rarity.ANCIENT, Rarity.LEGENDARY, Rarity.DRAGON) and random.randint(1, 4) == 1:
            cookie = Cookie.legendary()
        else:
            cookie = random.choice(Cookie.filter(selected_rarity))

        self.pulls += 1

        return cookie, soulstones

    def single_pull(self):
        cookie, soulstones = self.simulate()

        pre_inv = self.inventory[str(cookie.id)]
        self.inventory[str(cookie.id)] += soulstones

        return cookie, soulstones, pre_inv

    def ten_pull(self):
        result = [self.simulate() for _ in range(10)]

        result_inv = [(cookie, soulstones, self.inventory[str(cookie.id)]) for cookie, soulstones in result]
        for cookie, soulstones in result:
            self.inventory[str(cookie.id)] += soulstones

        return result_inv

    def mileage(self):
        total_milage = 0
        for cookie in Cookie.all():
            amount = self.inventory.get(str(cookie.id), 0)
            total_milage += min(amount, 290) * MILAGE[cookie.rarity]["base"]
            total_milage += min(max(amount - 290, 0), 200) * MILAGE[cookie.rarity]["ascend"]
            total_milage += max(amount - 490, 0) * MILAGE[cookie.rarity]["duplicate"]
        return total_milage

    @staticmethod
    def single_mileage(cookie, added: int, total: int):
        mileage = 0
        base = total - added

        mileage += min(total, 290) * MILAGE[cookie.rarity]["base"] - min(base, 290) * MILAGE[cookie.rarity]["base"]
        mileage += (
            min(max(total - 290, 0), 200) * MILAGE[cookie.rarity]["ascend"]
            - min(max(base - 290, 0), 200) * MILAGE[cookie.rarity]["ascend"]
        )
        mileage += (
            max(total - 490, 0) * MILAGE[cookie.rarity]["duplicate"]
            - max(base - 490, 0) * MILAGE[cookie.rarity]["duplicate"]
        )

        return mileage
