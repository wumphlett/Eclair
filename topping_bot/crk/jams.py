from decimal import Decimal
from enum import Enum

from topping_bot.crk.cookies import Cookie
from topping_bot.crk.common import linear
from topping_bot.util.const import INFO_PATH


cj_souls = []
with open(INFO_PATH / "mcsoul.txt") as f:
    for cj_soul in f.readlines():
        soul_type, soul_value = cj_soul.split(",")
        cj_souls.append((f"{soul_type.title()} Soul Ess.", int(soul_value)))

cj_crystals = []
with open(INFO_PATH / "mccrystal.txt") as f:
    for cj_crystal in f.readlines():
        cj_crystals.append(int(cj_crystal.replace(",", "")))

cj_ingredients = []
with open(INFO_PATH / "mcingredient.txt") as f:
    for cj_ingredient in f.readlines():
        cj_ingredients.append(int(cj_ingredient.replace(",", "")))


class Type(Enum):
    BLACK_PEARL = "Black Pearl"
    SEA_FAIRY = "Sea Fairy"
    FROST_QUEEN = "Frost Queen"


JAMS = set(jam.value for jam in Type)


class Jam:
    def __init__(self, cookie: Cookie, lvl: int):
        self.jam = Type(cookie.name)
        self.lvl = lvl

    def soul(self, lvl=None):
        lvl = lvl if lvl is not None else self.lvl
        return cj_souls[lvl - 1]

    def crystal(self, lvl=None):
        lvl = lvl if lvl is not None else self.lvl
        return cj_crystals[lvl - 1]

    def ingredient(self, lvl=None):
        lvl = lvl if lvl is not None else self.lvl
        return cj_ingredients[lvl - 1]

    @property
    def effects(self):
        if self.jam == Type.BLACK_PEARL:
            return [
                ("(Rally) Ally DMG Resist", f"{linear(15, 25, 30)(self.lvl):.1f}%"),
                ("ATK", f"{-Decimal(15):.1f}%"),
                ("Hatred to Trigger", "x50" if self.lvl < 20 else "x35"),
                ("Water Cage Duration", f"{Decimal(2 if self.lvl < 10 else '2.5'):.1f}s"),
                ("Water Cage DMG", f"{Decimal(85):.1f}%"),
                ("Tornado Extra DMG", f"{linear(9, 15, 30)(self.lvl):.1f}%"),
                ("Hatred", "+1/s"),
                ("Lividness", "+1/Ally Defeated"),
            ]
        elif self.jam == Type.SEA_FAIRY:
            return [
                ("(Rally) Team Water DMG", f"{linear(30, 40, 30)(self.lvl):.1f}%"),
                ("Tidal Wave DMG", f"{linear('198.7', '200.7', 30)(self.lvl):.1f}%"),
                ("Single Wave DMG", f"{linear('135.6', '167.2', 30)(self.lvl):.1f}%"),
                ("Tidal Wave Stun", f"3s"),
                ("Water Type CRIT DMG", f"+{Decimal('17.5'):.1f}%"),
            ]
        elif self.jam == Type.FROST_QUEEN:
            return [
                ("(Rally) Team Ice DMG", f"{linear(30, 40, 30)(self.lvl):.1f}%"),
                ("Blizzard DMG", f"{linear('29.3', '48.8', 30)(self.lvl):.1f}%"),
                ("Eternal Frost DMG", f"{linear('306.5', '510.8', 30)(self.lvl):.1f}%"),
                ("Freeze", f"2.5s"),
                ("Chill", f"DEF {-Decimal(65):.1f}% & MOV SPD {-Decimal(50):.1f}%"),
                ("DMG After Freeze", f"{Decimal('213.2'):.1f}%"),
                ("Blizzard Targets Frost", f"ATK SPD {-Decimal(10):.1f}% & Freeze DMG +{Decimal(150):.1f}%"),
            ]

    @property
    def enchantments(self):
        enchants = []
        if self.jam == Type.BLACK_PEARL:
            if self.lvl >= 10:
                enchants.extend(
                    [
                        ("Water Cage Duration", f"{Decimal('2.5'):.1f}s"),
                    ]
                )
            elif self.lvl >= 20:
                enchants.extend(
                    [
                        ("Hatred to Trigger", "x50" if self.lvl < 20 else "x35"),
                        ("ATK at Max Hatred", f"+{Decimal(5):.1f}%"),
                    ]
                )
            elif self.lvl >= 30:
                enchants.extend(
                    [
                        ("Lightning & Whirlpool DMG Resist Bypass", f"{Decimal(45):.1f}%"),
                        ("CRIT% at Max Hatred", f"+{Decimal(3):.1f}%"),
                        ("CRIT DMG at Max Hatred", f"+{Decimal(5):.1f}%"),
                    ]
                )
        elif self.jam == Type.SEA_FAIRY:
            if self.lvl >= 10:
                enchants.extend(
                    [
                        ("Soaring Compassion DMG Resist Bypass", f"{Decimal(35):.1f}%"),
                        ("Tidal Wave DMG Resist Bypass", f"{Decimal(35):.1f}%"),
                        ("Silence from Tidal Wave", f"{Decimal('1.5'):.1f}s"),
                    ]
                )
            elif self.lvl >= 20:
                enchants.extend(
                    [
                        ("Extra DMG (Stun Immune)", f"{Decimal(185):.1f}%"),
                    ]
                )
            elif self.lvl >= 30:
                enchants.extend(
                    [
                        ("Single Wave True DMG", f"{Decimal(4):.1f}%"),
                        ("DMG (Others)", f"{Decimal('63.5'):.1f}%"),
                    ]
                )
        elif self.jam == Type.FROST_QUEEN:
            if self.lvl >= 10:
                enchants.extend(
                    [
                        ("Area DMG after Freeze", f"{Decimal('354.4'):.1f}%"),
                    ]
                )
            elif self.lvl >= 20:
                enchants.extend(
                    [
                        ("Ice-type DMG Received", "+25.0%"),
                        ("Blizzard Targets Amplify Debuff", f"+{Decimal('12.5'):.1f}%"),
                    ]
                )
            elif self.lvl >= 30:
                enchants.extend(
                    [
                        ("Blizzard DMG Resist Bypass", f"{Decimal(40):.1f}%"),
                    ]
                )
        return enchants

    @property
    def ascension_buffs(self):
        if self.jam == Type.BLACK_PEARL:
            return [
                ("1A", "Whirlpool to Center Faster"),
                ("2A", "HP: +5.0%"),
                ("3A", "Whirlpool Hits: +4"),
                ("4A", "ATK: +5.0%"),
                ("5A", "CRIT DMG +7.0%"),
            ]
        elif self.jam == Type.SEA_FAIRY:
            return [
                ("1A", "CRIT DMG +7.0%"),
                ("2A", "DMG Resist: +5.0%"),
                ("3A", "Stream DMG: 150.0% & Pillar DMG: 330.3% & Stun: 3.0s"),
                ("4A", "HP: +5.0%"),
                ("5A", "ATK: +5.0%"),
            ]
        elif self.jam == Type.FROST_QUEEN:
            return [
                ("1A", "HP: +5.0%"),
                ("2A", "DEF: +7.0%"),
                ("3A", "ATK: +5.0%"),
                ("4A", "DMG Resist: +5.0%"),
                ("5A", "Curse Protection"),
            ]
