from difflib import SequenceMatcher
from enum import Enum
from functools import cache
from typing import Tuple

import yaml

from topping_bot.util.const import INFO_PATH, STATIC_PATH


class Rarity(Enum):
    ANCIENT = "Ancient"
    DRAGON = "Dragon"
    LEGENDARY = "Legendary"
    SUPER_EPIC = "Super Epic"
    EPIC = "Epic"
    SPECIAL = "Special"
    RARE = "Rare"
    COMMON = "Common"


class Type(Enum):
    CHARGE = "Charge"
    DEFENSE = "Defense"
    MAGIC = "Magic"
    AMBUSH = "Ambush"
    HEALING = "Healing"
    BOMBER = "Bomber"
    SUPPORT = "Support"
    RANGED = "Ranged"
    BTS = "BTS"


class Position(Enum):
    FRONT = "Front"
    MIDDLE = "Middle"
    REAR = "Rear"


class Filter(Enum):
    EPIC_PLUS = "epic+"
    FULL = "full"


cookie_powders = []
with open(INFO_PATH / "cookiepowder.txt") as f:
    for cookie_powder in f.readlines():
        powder_type, powder_value = cookie_powder.split(",")
        cookie_powders.append((f"{powder_type.title()} Powder", int(powder_value)))


def cookie_data():
    with open(INFO_PATH / "cookies.yaml", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    aliases = {}
    cookies = data["cookies"]
    featured = data.get("featured", [])
    legendary = data.get("legendary", None)

    for cookie, data in list(cookies.items()):
        data["id"] = int(data["id"])
        data["name"] = cookie
        data["rarity"] = Rarity(data["rarity"])
        data["type"] = Type(data["type"])
        data["position"] = Position(data["position"])

        for alias in data["aliases"]:
            aliases[alias.lower()] = data

    cookies = {k.lower(): v for k, v in cookies.items()}

    return cookies, aliases


def cookie_order():
    with open(INFO_PATH / "cookies.yaml", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    return data["order"]


def cookie_map():
    cookies, _ = cookie_data()
    return {cookie["id"]: cookie for cookie in cookies.values()}


class Cookie:
    _data = cookie_data()
    _map = cookie_map()

    def __init__(self, **kwargs):
        self.id = kwargs["id"]
        self.name = kwargs["name"]
        self.rarity = kwargs["rarity"]
        self.type = kwargs["type"]
        self.position = kwargs["position"]
        self.cooldown = kwargs["cd"]
        self.start_cd_override = kwargs.get("special_start")
        self.is_duration_skill = kwargs.get("duration_skill", False)

    def __str__(self):
        return self.name

    def __repr__(self):
        return self.name

    def __eq__(self, other):
        return self.name == other.name

    @classmethod
    def names(cls):
        return [cookie["name"] for cookie in cls._data[0].values()]

    @classmethod
    @cache
    def all(cls):
        cookies, aliases = cls._data
        return [cls(**cookie) for cookie in cookies.values()]

    @classmethod
    @cache
    def filter(cls, rarities: Tuple[Rarity]):
        cookies, aliases = cls._data
        return [cls(**cookie) for cookie in cookies.values() if cookie["rarity"] in rarities]

    @classmethod
    def pk(cls, pk: int):
        return cls(**cls._map.get(pk))

    @classmethod
    def get(cls, search: str):
        search = search.lower()
        cookies, aliases = cls._data

        if cookie := cookies.get(search):
            return cls(**cookie)
        if cookie := aliases.get(search):
            return cls(**cookie)

        likely = max((cookie for cookie in cookies), key=lambda x: SequenceMatcher(None, x, search).ratio())

        if SequenceMatcher(None, likely, search).ratio() > 0.5:
            return cls(**cookies.get(likely))
        return None

    @staticmethod
    def powder(lvl):
        return cookie_powders[lvl - 1]

    @property
    def dir(self):
        return STATIC_PATH / "cookies" / str(self.id).zfill(4)

    @property
    def card(self):
        return self.dir / f"cookie{str(self.id).zfill(4)}_card.png"

    @property
    def head(self):
        return self.dir / f"cookie{str(self.id).zfill(4)}_head.png"

    @property
    def stand(self):
        return self.dir / f"cookie{str(self.id).zfill(4)}_stand.png"

    @property
    def skill(self):
        return self.dir / f"cookie{str(self.id).zfill(4)}_skill.png"

    def stone(self, ascended=False):
        if ascended:
            return self.dir / f"cookie{str(self.id).zfill(4)}_beyond_stone.png"
        else:
            return self.dir / f"cookie{str(self.id).zfill(4)}_stone.png"

    @property
    def banner(self):
        return STATIC_PATH / "misc" / f"banner" / f"{self.rarity.value.lower().replace(' ', '')}.png"

    @property
    def frame(self):
        return STATIC_PATH / "misc" / f"frame" / f"{self.rarity.value.lower().replace(' ', '')}.png"

    @property
    def role_icon(self):
        return STATIC_PATH / "misc" / f"role" / f"{self.type.value.lower().replace(' ', '')}.png"

    @property
    def position_icon(self):
        return STATIC_PATH / "misc" / f"{self.position.value.lower()}_pos.png"

    @property
    def lobby(self):
        if self.rarity in (Rarity.ANCIENT, Rarity.LEGENDARY) or self.type == Type.BTS:
            return self.dir / f"cookie{str(self.id).zfill(4)}_lobby.png"
        elif self.rarity == Rarity.SPECIAL:
            return STATIC_PATH / "misc" / "lobby" / "epic.png"
        else:
            return STATIC_PATH / "misc" / "lobby" / f"{self.rarity.value.lower().replace(' ', '')}.png"

    @property
    def essence(self):
        if self.rarity == Rarity.COMMON:
            return STATIC_PATH / "misc" / "essence" / "common.png"
        elif self.rarity == Rarity.RARE:
            return STATIC_PATH / "misc" / "essence" / "rare.png"
        elif self.rarity in (Rarity.EPIC, Rarity.SUPER_EPIC):
            return STATIC_PATH / "misc" / "essence" / "epic.png"
        else:
            return STATIC_PATH / "misc" / "essence" / "legendary.png"


class Order:
    _data = cookie_data()
    _order = cookie_order()

    def __init__(self, cookie_filter: Filter):
        cookies, aliases = self._data
        order = self._order

        if cookie_filter == cookie_filter.EPIC_PLUS:
            self.cookies = [
                cookie
                for cookie in order
                if cookies[cookie.lower()]["rarity"]
                in (Rarity.ANCIENT, Rarity.DRAGON, Rarity.LEGENDARY, Rarity.SUPER_EPIC, Rarity.EPIC, Rarity.SPECIAL)
            ]
        elif cookie_filter == cookie_filter.FULL:
            self.cookies = order

        self.cookies = [Cookie(**cookies[cookie.lower()]) for cookie in self.cookies]
        self.filter = cookie_filter

    @classmethod
    def refresh(cls):
        cls._data = cookie_data()

    def solve(self, *args):
        full = []
        known = []
        legendary_plus = 0

        for cookie in args:
            if cookie != "*":
                cookie = Cookie.get(cookie)

                if cookie not in self.cookies:
                    raise Exception(f"{cookie.name} not in filtered list")

                if cookie.rarity in (Rarity.ANCIENT, Rarity.LEGENDARY):
                    legendary_plus += 1

                known.append(cookie)
            else:
                cookie = None
            full.append(cookie)

        if known != sorted(known, key=lambda x: self.cookies.index(x)):
            raise Exception(f"Known cookies are not in a valid order")

        if legendary_plus > 3:
            raise Exception(f"Number of legendary+ cookies exceeds arena rules")
        elif legendary_plus == 3:
            self.cookies = [
                cookie
                for cookie in self.cookies
                if not (cookie.rarity in (Rarity.LEGENDARY, Rarity.ANCIENT) and cookie not in known)
            ]

        final = []
        for i, cookie in enumerate(full):
            if cookie is not None:
                final.append(cookie)
            else:
                left, right = 0, len(self.cookies)
                left_mod = right_mod = 0

                for neighbor in full[:i][::-1]:
                    if neighbor is not None:
                        left = self.cookies.index(neighbor)
                        break
                    left_mod += 1

                for neighbor in full[i + 1 :]:
                    if neighbor is not None:
                        right = self.cookies.index(neighbor)
                        break
                    right_mod += 1

                left += left_mod
                right -= right_mod

                final.append(self.cookies[left + 1 : right])

        return final
