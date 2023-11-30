from decimal import Decimal
from difflib import SequenceMatcher
from enum import Enum


class Type(Enum):
    HISTORY_1 = "Hall of History 1"
    HISTORY_2 = "Hall of History 2"
    HISTORY_3 = "Hall of History 3"
    HISTORY_4 = "Hall of History 4"
    HISTORY_5 = "Hall of History 5"
    HISTORY_6 = "Hall of History 6"
    NATURE_1 = "Hall of Nature 1"
    NATURE_2 = "Hall of Nature 2"
    NATURE_3 = "Hall of Nature 3"
    NATURE_4 = "Hall of Nature 4"
    NATURE_5 = "Hall of Nature 5"
    NATURE_6 = "Hall of Nature 6"
    NATURE_7 = "Hall of Nature 7"
    MAGIC_1 = "Hall of Magic 1"
    MAGIC_2 = "Hall of Magic 2"
    MAGIC_3 = "Hall of Magic 3"
    MAGIC_4 = "Hall of Magic 4"
    MAGIC_5 = "Hall of Magic 5"
    HOLLYBERRY_STATUE = "Hollyberry Cookie Statue"
    GOLEM = "Waffle Cone Magic Golem"
    THRONE = "Throne of Unity"
    TREE = "Millennial Tree's Sapling"
    JELLY_WORM = "Jelly Worm's Underground Habitat"
    DRAGON_SKULL = "Dragon's Skull"
    HOT_POT = "Rainbow Jellyragora Hot Pot"
    GRIMOIRE = "Giant Grimoire"
    MOONSTONE = "Moonstone"


RELICS = set(relic.value for relic in Type)


class Relic:
    def __init__(self, relic_type: Type, lvl: int = None):
        self.relic = relic_type
        self.lvl = lvl

    @classmethod
    def get(cls, search: str):
        search = search.title()

        likely = max(
            (relic for relic in RELICS),
            key=lambda x: max(match.size for match in SequenceMatcher(None, x, search).get_matching_blocks()),
        )
        return cls(Type(likely))

    @property
    def effects(self):
        if self.relic == Type.HISTORY_1:
            return [
                ("Coins", f"{self.lvl}%"),
            ]
        elif self.relic == Type.HISTORY_2:
            return [
                ("ATK for Ambush & Ranged", f"{Decimal(100) + (self.lvl - 1) * (Decimal(1900) / Decimal(19)):,}"),
            ]
        elif self.relic == Type.HISTORY_3:
            return [
                ("HP Shield for GB", f"{Decimal(10_000) + (self.lvl - 1) * (Decimal(40_000) / Decimal(19)):.1f}"),
            ]
        elif self.relic == Type.HISTORY_4:
            if self.lvl <= 9:
                return [
                    ("Check-in Rewards", f"{Decimal(5) + (self.lvl - 1) * (Decimal('.5')):.1f}%"),
                ]
            else:
                return [
                    ("Check-in Rewards", f"{Decimal(15) + (self.lvl - 10) * (Decimal(3)):.1f}%"),
                ]
        elif self.relic == Type.HISTORY_5:
            return [
                ("ATK for Defense & Charge", f"{Decimal(50) + (self.lvl - 1) * (Decimal(950) / Decimal(19)):,}"),
            ]
        elif self.relic == Type.HISTORY_6:
            return [
                ("Alliance Revive", f"{Decimal(40) + (self.lvl - 1) * (Decimal(60) / Decimal(19)):.1f}%"),
            ]
        elif self.relic == Type.NATURE_1:
            return [
                ("Research Speed", f"{self.lvl}%"),
            ]
        elif self.relic == Type.NATURE_2:
            return [
                ("Searing Key Max", f"{self.lvl}"),
            ]
        elif self.relic == Type.NATURE_3:
            return [
                ("Domain Expansion Rate", f"{self.lvl}%"),
            ]
        elif self.relic == Type.NATURE_4:
            return [
                ("Trading Time", f"{-Decimal('.97') - (self.lvl - 1) * (Decimal('7.7') / Decimal(19)):.1f}%"),
            ]
        elif self.relic == Type.NATURE_5:
            return [
                ("ATK for Support & Healing", f"{Decimal(50) + (self.lvl - 1) * (Decimal(950) / Decimal(19)):,}"),
            ]
        elif self.relic == Type.NATURE_6:
            return [
                ("ATK for Magic & Bomber", f"{Decimal(100) + (self.lvl - 1) * (Decimal(1900) / Decimal(19)):,}"),
            ]
        elif self.relic == Type.NATURE_7:
            return [
                ("Creature ATK", f"{Decimal('25.83') + (self.lvl - 1) * (Decimal('22.57') / Decimal(19)):.1f}%"),
                ("Creature DEF", f"{Decimal('32.55') + (self.lvl - 1) * (Decimal('12.93') / Decimal(19)):.1f}%"),
                ("Creature HP", f"{Decimal(50) + (self.lvl - 1) * (Decimal(20) / Decimal(19)):.1f}%"),
            ]
        elif self.relic == Type.MAGIC_1:
            if self.lvl <= 10:
                return [
                    ("Stamina Jelly Max", f"{self.lvl}"),
                ]
            else:
                return [
                    ("Stamina Jelly Max", f"{10 + (10 - self.lvl) * 2}"),
                ]
        elif self.relic == Type.MAGIC_2:
            return [
                ("Tree of Wishes Coins", f"{Decimal('.88') + (self.lvl - 1) * (Decimal('8.12') / Decimal(19)):.1f}%"),
            ]
        elif self.relic == Type.MAGIC_3:
            return [
                ("Alliance Healing", f"{Decimal(4) + (self.lvl - 1) * (Decimal(6) / Decimal(19)):.1f}%"),
            ]
        elif self.relic == Type.MAGIC_4:
            return [
                ("Alliance CRIT DMG", f"{Decimal(5) + (self.lvl - 1) * (Decimal(25) / Decimal(19)):.1f}%"),
            ]
        elif self.relic == Type.MAGIC_5:
            return [
                ("Guild Battle Meteor", f"{Decimal(450) + (self.lvl - 1) * (Decimal(1350) / Decimal(19)):.1f}%"),
            ]
        elif self.relic == Type.HOLLYBERRY_STATUE:
            return [
                ("Blast Mode", f"{Decimal(2) + (self.lvl - 1) * (Decimal(20) / Decimal(19)):.1f}s"),
            ]
        elif self.relic == Type.GOLEM:
            return [
                ("Cookies' DEF", f"{Decimal('.75') + (self.lvl - 1) * (Decimal('14.25') / Decimal(19)):.1f}%"),
            ]
        elif self.relic == Type.THRONE:
            return [
                ("Cookies' ATK", f"{Decimal('.4') + (self.lvl - 1) * (Decimal('7.6') / Decimal(19)):.1f}%"),
            ]
        elif self.relic == Type.TREE:
            return [
                ("Cookies' HP", f"{Decimal('.6') + (self.lvl - 1) * (Decimal('11.4') / Decimal(19)):.1f}%"),
            ]
        elif self.relic == Type.JELLY_WORM:
            return [
                ("Alliance ATK", f"{Decimal(1) + (self.lvl - 1) * (Decimal(5) / Decimal(19)):.1f}%"),
                ("Alliance DEF", f"{Decimal('1.5') + (self.lvl - 1) * (Decimal('7.5') / Decimal(19)):.1f}%"),
                ("Alliance HP", f"{Decimal(2) + (self.lvl - 1) * (Decimal(10) / Decimal(19)):.1f}%"),
            ]
        elif self.relic == Type.DRAGON_SKULL:
            return [
                ("Alliance Boss DMG", f"{Decimal(4) + (self.lvl - 1) * (Decimal(16) / Decimal(19)):.1f}%"),
            ]
        elif self.relic == Type.HOT_POT:
            return [
                ("Cookie House Speed", f"{self.lvl}%"),
            ]
        elif self.relic == Type.GRIMOIRE:
            return [
                ("Guild Battle ATK", f"{Decimal(1) + (self.lvl - 1) * (Decimal(5) / Decimal(19)):.1f}%"),
                ("Guild Battle DEF", f"{Decimal('1.5') + (self.lvl - 1) * (Decimal('7.5') / Decimal(19)):.1f}%"),
                ("Guild Battle HP", f"{Decimal(2) + (self.lvl - 1) * (Decimal(10) / Decimal(19)):.1f}%"),
            ]
        elif self.relic == Type.MOONSTONE:
            return [
                ("Guild Battle CRIT DMG", f"{Decimal(5) + (self.lvl - 1) * (Decimal(25) / Decimal(19)):.1f}%"),
            ]
