from decimal import Decimal
from difflib import SequenceMatcher
from enum import Enum
import math

import scipy.stats as st

from topping_bot.crk.common import linear
from topping_bot.util.const import INFO_PATH


class Type(Enum):
    FEATHER = "Sugar Swan's Shining Feather"
    WHISTLE = "Dream Conductor's Whistle"
    FORK = "The Order's Sacred Fork"
    CROWN = "Divine Honey Cream Crown"
    REMEDY = "Miraculous Natural Remedy"
    INSIGNIA = "Insignia of the Indomitable Knights"
    PIN_CUSHION = "Seamstress's Pin Cushion"
    FLAMINGO = "Durianeer's Squeaky Flamingo Tube"
    NECKLACE = "Hollyberrian Royal Necklace"
    ROBES = "Librarian's Enchanted Robes"
    MONOCLE = "Bookseller's Monocle"
    BRANCH = "Sacred Pomegranate Branch"
    GOO = "Jelly Worm's Sticky Goo"
    PILGRIM_TORCH = "Elder Pilgrim's Torch"
    PILGRIM_SCROLL = "Old Pilgrim's Scroll"
    STAFF = "Blind Healer's Staff"
    SLEEPYHEAD_WATCH = "Sleepyhead's Jelly Watch"
    FROZEN_TORCH = "Milk Tribe's Frozen Torch"
    ACORN = "Acorn Snowball With a Tiny Cookie"
    ACORN_BOMB = "Blossoming Acorn Bomb"
    ECHO = "Echo of the Hurricane's Song"
    SCYTHE = "Grim-looking Scythe"
    LOLLIPOP = "Bear Jelly's Lollipop"
    DISCIPLE_SCROLL = "Disciple's Magic Scroll"
    ICE_CREAM = "Miraculous Ghost Ice Cream"
    SLINGSHOT = "Pilgrim's Slingshot"
    PAPER_CHARM = "Priestess Cookie's Paper Charm"
    SQUISHY_WATCH = "Squishy Jelly Watch"
    HORN = "Gatekeeper Ghost's Horn"
    COIN_PURSE = "Cheesebird's Coin Purse"
    TROPHY_SAFE = "Ginkgoblin's Trophy Safe"


TREASURES = set(treasure.value for treasure in Type)


treasure_upgrade_cost = []
with open(INFO_PATH / "treasureupgrade.txt") as f:
    for treasure_lvl in f.readlines():
        treasure_upgrade_cost.append(int(treasure_lvl.replace(",", "")))


class Treasure:
    def __init__(self, treasure_type: Type, lvl: int = None, start_lvl: int = None, chance_up: bool = True):
        self.treasure = treasure_type
        self.lvl = lvl
        self.start_lvl = start_lvl
        self.chance_up = chance_up

    @property
    def chance(self):
        return 0.013 if self.chance_up else 0.00675

    @property
    def req_count(self):
        return sum(treasure_upgrade_cost[self.start_lvl : self.lvl])

    def upgrade(self, threshold):
        p, q, z, x = self.chance, 1 - self.chance, st.norm.ppf(threshold), self.req_count
        if (2 * p * x + z**2 * p * q) ** 2 - 4 * p**2 * x**2 < 0:
            return math.ceil((2 * p * x + z**2 * p * q) / (2 * p**2))
        else:
            return math.ceil(
                (2 * p * x + z**2 * p * q + math.sqrt((2 * p * x + z**2 * p * q) ** 2 - 4 * p**2 * x**2))
                / (2 * p**2)
            )

    @classmethod
    def get(cls, search: str):
        search = search.title()

        likely = max(
            (treasure for treasure in TREASURES),
            key=lambda x: max(match.size for match in SequenceMatcher(None, x, search).get_matching_blocks()),
        )
        return cls(Type(likely))

    @property
    def effects(self):
        if self.treasure == Type.FEATHER:
            return [
                ("Revive HP", f"{linear(20, 100, 12)(self.lvl):.1f}%"),
            ]
        elif self.treasure == Type.WHISTLE:
            return [
                ("CRIT%", f"{Decimal(15):.1f}%"),
                ("ATK", f"{linear(30, 40, 12)(self.lvl):.1f}%"),
                ("DMG Resist", f"{linear(10, 20, 12)(self.lvl):.1f}%"),
                ("Healing", f"{Decimal(30):.1f}%"),
            ]
        elif self.treasure == Type.FORK:
            return [
                ("Bonus DMG", f"{linear('2.5', '12.5', 12)(self.lvl):.1f}%"),
                ("Boss DMG", f'{linear("8.8", "30", 12)(self.lvl):.1f}%'),
            ]
        elif self.treasure == Type.CROWN:
            return [
                ("CRIT%", f"{linear(6, 40, 12)(self.lvl):.1f}%"),
                ("CRIT DMG", f'{linear("13.5", 50, 12)(self.lvl):.1f}%'),
            ]
        elif self.treasure == Type.REMEDY:
            return [
                ("Healing", f"{linear(16, 32, 12)(self.lvl):.1f}%"),
                ("ATK", f"{linear(10, 30, 12)(self.lvl):.1f}% for {linear(5, 15, 12)(self.lvl):.1f}s"),
            ]
        elif self.treasure == Type.INSIGNIA:
            return [
                ("Healing", f"{linear(20, 30, 12)(self.lvl):.1f}%"),
                ("Invincible", f"{linear(6, 9, 12)(self.lvl):.1f}s"),
            ]
        elif self.treasure == Type.PIN_CUSHION:
            return [
                ("ATK", f"{linear(30, 80, 12)(self.lvl):.1f}%"),
                ("Duration", f"{linear(10, 30, 12)(self.lvl):.1f}%"),
            ]
        elif self.treasure == Type.FLAMINGO:
            return [
                ("Max HP", f"{linear(25, 65, 12)(self.lvl):.1f}%"),
            ]
        elif self.treasure == Type.NECKLACE:
            return [
                ("HP Shield", f"{linear(15, 35, 12)(self.lvl):.1f}%"),
                ("DMG Resist", f"{linear(5, '17.5', 12)(self.lvl):.1f}%"),
            ]
        elif self.treasure == Type.ROBES:
            return [
                ("ATK SPD", f"{linear(45, 90, 12)(self.lvl):.1f}%"),
            ]
        elif self.treasure == Type.MONOCLE:
            return [
                ("Debuff Purification", f"{linear(15, 30, 12)(self.lvl):.1f}%"),
            ]
        elif self.treasure == Type.BRANCH:
            return [
                ("HP Shield", f"{linear(55, 70, 12)(self.lvl):.1f}%"),
            ]
        elif self.treasure == Type.GOO:
            return [
                ("Invulnerability", f"{linear(2, 5, 12)(self.lvl):.1f}s"),
            ]
        elif self.treasure == Type.PILGRIM_TORCH:
            return [
                ("Burn DMG%", f"{linear(20, 65, 12)(self.lvl):.1f}%"),
            ]
        elif self.treasure == Type.PILGRIM_SCROLL:
            return [
                ("ATK", f"{linear(30, 60, 12)(self.lvl):.1f}%"),
            ]
        elif self.treasure == Type.STAFF:
            return [
                ("Healing", f"{linear(55, 110, 12)(self.lvl):.1f}%"),
            ]
        elif self.treasure == Type.SLEEPYHEAD_WATCH:
            return [
                ("Cooldown", f"{linear(-15, -25, 12)(self.lvl):.1f}%"),
                ("ATK", f"{linear(1, 5, 12)(self.lvl):.1f}%"),
            ]
        elif self.treasure == Type.FROZEN_TORCH:
            return [
                ("Freeze DMG", f"{linear(15, 25, 12)(self.lvl):.1f}%"),
                ("Freeze Duration", f"{Decimal(1):.1f}s"),
                ("Frost Duration", f"{Decimal(16):.1f}s"),
            ]
        elif self.treasure == Type.ACORN:
            return [
                ("DMG Resist", f"{linear(10, 20, 12)(self.lvl):.1f}%"),
                ("CRIT Resist", f"{linear(5, 15, 12)(self.lvl):.1f}%"),
            ]
        elif self.treasure == Type.ACORN_BOMB:
            return [
                ("DMG", f"{linear(15, 35, 12)(self.lvl):.1f}%"),
                ("Target DEF", f"{linear(-10, -20, 12)(self.lvl):.1f}%"),
            ]
        elif self.treasure == Type.ECHO:
            return [
                ("DMG (Cookies)", f"{linear('217.2', '434.4', 12)(self.lvl):.1f}%"),
                ("DMG (Others)", f"{linear(724, 1448, 12)(self.lvl):.1f}%"),
            ]
        elif self.treasure == Type.SCYTHE:
            return [
                ("CRIT%", f"{linear(10, 30, 12)(self.lvl):.1f}%"),
            ]
        elif self.treasure == Type.LOLLIPOP:
            return [
                ("ATK", f"{linear(20, 40, 12)(self.lvl):.1f}%"),
                ("CRIT%", f"{linear(20, 40, 12)(self.lvl):.1f}%"),
            ]
        elif self.treasure == Type.DISCIPLE_SCROLL:
            return [
                ("ATK", f"{linear(25, 45, 12)(self.lvl):.1f}%"),
                ("DEF", f"{Decimal(30):.1f}%"),
            ]
        elif self.treasure == Type.ICE_CREAM:
            return [
                ("Enemy Def", f"{linear(-10, -50, 12)(self.lvl):.1f}%"),
            ]
        elif self.treasure == Type.SLINGSHOT:
            return [
                ("Enemy Def", f"{linear(-30, -70, 12)(self.lvl):.1f}%"),
            ]
        elif self.treasure == Type.PAPER_CHARM:
            return [
                ("Curse DMG%", f"{linear(15, 45, 12)(self.lvl):.1f}%"),
            ]
        elif self.treasure == Type.SQUISHY_WATCH:
            return [
                ("Cooldown", f"{linear(-10, -25, 12)(self.lvl):.1f}%"),
            ]
        elif self.treasure == Type.HORN:
            return [
                ("DEF", f"{linear(30, '45.4', 12)(self.lvl):.1f}%"),
            ]
        elif self.treasure == Type.COIN_PURSE:
            return [
                ("Coin Chance", f"{linear(20, '80.5', 12)(self.lvl):.1f}%"),
            ]
        elif self.treasure == Type.TROPHY_SAFE:
            return [
                ("Coin Magnet", f"lvl {self.lvl}"),
                ("Coin Bonus", f"{linear(5, 10, 12)(self.lvl):.1f}%"),
            ]
