from decimal import Decimal
from enum import Enum

from topping_bot.crk.cookies import Cookie
from topping_bot.crk.common import linear
from topping_bot.util.const import INFO_PATH


mc_souls = []
with open(INFO_PATH / "mcsoul.txt") as f:
    for mc_soul in f.readlines():
        soul_type, soul_value = mc_soul.split(",")
        mc_souls.append((f"{soul_type.title()} Soul Ess.", int(soul_value)))

mc_crystals = []
with open(INFO_PATH / "mccrystal.txt") as f:
    for mc_crystal in f.readlines():
        mc_crystals.append(int(mc_crystal.replace(",", "")))

mc_ingredients = []
with open(INFO_PATH / "mcingredient.txt") as f:
    for mc_ingredient in f.readlines():
        mc_ingredients.append(int(mc_ingredient.replace(",", "")))


class Type(Enum):
    ESPRESSO = "Espresso"
    PURPLE_YAM = "Purple Yam"
    VAMPIRE = "Vampire"
    MILK = "Milk"
    RYE = "Rye"
    SQUID_INK = "Squid Ink"
    WEREWOLF = "Werewolf"
    LICORICE = "Licorice"
    CREAM_PUFF = "Cream Puff"
    MALA_SAUCE = "Mala Sauce"
    MADELEINE = "Madeleine"
    LATTE = "Latte"
    TEA_KNIGHT = "Tea Knight"
    WILDBERRY = "Wildberry"
    MANGO = "Mango"
    PARFAIT = "Parfait"
    SORBET_SHARK = "Sorbet Shark"
    BLACK_RAISIN = "Black Raisin"
    SNOW_SUGAR = "Snow Sugar"


CANDIES = set(candy.value for candy in Type)


class Candy:
    def __init__(self, cookie: Cookie, lvl: int):
        self.candy = Type(cookie.name)
        self.lvl = lvl

    def soul(self, lvl=None):
        lvl = lvl if lvl is not None else self.lvl
        return mc_souls[lvl - 1]

    def crystal(self, lvl=None):
        lvl = lvl if lvl is not None else self.lvl
        return mc_crystals[lvl - 1]

    def ingredient(self, lvl=None):
        lvl = lvl if lvl is not None else self.lvl
        return mc_ingredients[lvl - 1]

    @property
    def effects(self):
        if self.candy == Type.ESPRESSO:
            return [
                ("Extra DMG on final hit", ""),
                ("DMG (Cookies)", f'{Decimal("261.8") + (self.lvl - 1) * (Decimal(55) / Decimal(29)):.1f}%'),
                ("DMG (Others)", f'{Decimal("198.4") + (self.lvl - 1) * (Decimal("99.2") / Decimal(29)):.1f}%'),
                ("Injury Max HP", f"{-Decimal(8) - (self.lvl - 1) * (Decimal(2) / Decimal(29)):.1f}%"),
            ]
        elif self.candy == Type.PURPLE_YAM:
            return [
                ("Fury ATK", f"{Decimal(20) + (self.lvl - 1) * (Decimal(25) / Decimal(29)):.1f}%"),
                ("Fury CRIT%", f"{Decimal(20):.1f}%"),
                ("Fury DMG Resist", f"{Decimal(8) + (self.lvl - 1) * (Decimal(2) / Decimal(29)):.1f}%"),
                ("Fury ATK SPD", f"{Decimal(10):.1f}%"),
                ("Fury Cooldown", f"{-Decimal(20):.1f}%"),
                ("Restore HP", f"{Decimal(15):.1f}%"),
            ]
        elif self.candy == Type.VAMPIRE:
            return [
                ("Single DMG", f'{Decimal("44.5"):.1f}%'),
                ("Bite DMG (Cookies)", f'{Decimal("55.4") + (self.lvl - 1) * (Decimal("16.7") / Decimal(29)):.1f}%'),
                ("Bite DMG (Others)", f'{Decimal("32.9") + (self.lvl - 1) * (Decimal("9.9") / Decimal(29)):.1f}%'),
                ("Bleeding Extra DMG", ""),
                ("Bleed DMG (Cookies)", f'{Decimal("83.3") + (self.lvl - 1) * (Decimal("16.7") / Decimal(29)):.1f}%'),
                ("Bleed DMG (Others)", f'{Decimal("20.8") + (self.lvl - 1) * (Decimal("4.2") / Decimal(29)):.1f}%'),
            ]
        elif self.candy == Type.MILK:
            return [
                ("Healing", f"{Decimal(30) + (self.lvl - 1) * (Decimal(20) / Decimal(29)):.1f}%"),
                ("Skill DMG", f'{Decimal("77.5") + (self.lvl - 1) * (Decimal("23.2") / Decimal(29)):.1f}%'),
                ("Debuff Resist", f"{Decimal(8) + (self.lvl - 1) * (Decimal(7) / Decimal(29)):.1f}%"),
                ("Purify", "All Debuff Effects"),
            ]
        elif self.candy == Type.RYE:
            return [
                ("Pistol Shots", "+2 Bonus (12 Total)"),
                ("Skill DMG", f"{Decimal(10) + (self.lvl - 1) * (Decimal(21) / Decimal(29)):.1f}%"),
                ("Burn Chance", f"{Decimal(50):.1f}%"),
                ("Reg Burn DMG", f'{Decimal("47.4") + (self.lvl - 1) * (Decimal("31.6") / Decimal(29)):.1f}%'),
                ("Skill Burn DMG", f'{Decimal("61.6") + (self.lvl - 1) * (Decimal("41.1") / Decimal(29)):.1f}%'),
            ]
        elif self.candy == Type.SQUID_INK:
            return [
                ("Ink Tentacle Slap", "+3 Bonus (10 Total)"),
                ("DMG (Cookies)", f"{Decimal(5) + (self.lvl - 1) * (Decimal(8) / Decimal(29)):.1f}%"),
                ("DMG (Others)", f'{Decimal("16.6") + (self.lvl - 1) * (Decimal("4.4") / Decimal(29)):.1f}%'),
                ("DEF Reduction", f"{Decimal(20):.1f}%"),
                ("Extra DMG", f'{-Decimal(15) - (self.lvl - 1) * (Decimal("22.5") / Decimal(29)):.1f}%'),
            ]
        elif self.candy == Type.WEREWOLF:
            return [
                ("Debuff Resist", f"{Decimal(40):.1f}%"),
                ("Injury Max HP", f'{-Decimal("1.2"):.1f}%'),
                ("Injury Cap", f"{Decimal(40):.1f}%"),
                ("Final hit DMG", f'{Decimal(30) + (self.lvl - 1) * (Decimal("41.5") / Decimal(29)):.1f}%'),
            ]
        elif self.candy == Type.LICORICE:
            return [
                ("Servants", f"{Decimal(10):.1f}% ATK, {Decimal(180):.1f}% DEF, {Decimal(50):.1f}% HP"),
                ("Servants", "Extra DMG"),
                ("DMG (Cookies)", f"{Decimal(15):.1f}%"),
                ("DMG (Others)", f"{Decimal(155):.1f}%"),
                ("Curse DMG", f'{Decimal("234.1") + (self.lvl - 1) * (Decimal("49.6") / Decimal(29)):.1f}%'),
                ("Poison (Cookies)", f"{Decimal('15.5'):.1f}%"),
                ("Poison (Others)", f"{Decimal('126.8'):.1f}%"),
                ("Silence", f"3.0s"),
                ("DEF Reduction", f"{-Decimal(40):.1f}%"),
                ("Healing Reduction", f"{-Decimal(60):.1f}%"),
            ]
        elif self.candy == Type.CREAM_PUFF:
            return [
                ("Passive CRIT%", f"{Decimal(10) + (self.lvl - 1) * (Decimal(15) / Decimal(29)):.1f}%"),
                ("ATK Up", f'{Decimal("0.5") + (self.lvl - 1) * (Decimal("0.5") / Decimal(29)):.1f}%'),
                ("Stun Immunity", f"15.0s"),
                ("Skill DMG", f"{Decimal(3) + (self.lvl - 1) * (Decimal(12) / Decimal(29)):.1f}%"),
                ("Succ Spell DMG", f"{Decimal(6) + (self.lvl - 1) * (Decimal(24) / Decimal(29)):.1f}%"),
                ("DMG Resist", f"{Decimal('18.5'):.1f}%"),
            ]
        elif self.candy == Type.MALA_SAUCE:
            return [
                ("Fire DMG", f"{Decimal('379.8') + (self.lvl - 1) * (Decimal(76) / Decimal(29)):.1f}%"),
                ("Extra Burn DMG", f'{Decimal("26.8") + (self.lvl - 1) * (Decimal("13.3") / Decimal(29)):.1f}%'),
                ("Ally CRIT%", f"{Decimal(25):.1f}%"),
            ]
        elif self.candy == Type.MADELEINE:
            return [
                ("Skill Extra DMG", f"{Decimal(76) + (self.lvl - 1) * (Decimal('64.4') / Decimal(29)):.1f}%"),
                ("Unleashed Light", f'{Decimal("267.0") + (self.lvl - 1) * (Decimal("53.4") / Decimal(29)):.1f}%'),
                ("Unleashed Light", f"Extra DMG"),
                ("True DMG", f"{Decimal(3):.1f}%"),
                ("Single Hit DMG (Others)", f"{Decimal('280.7'):.1f}%"),
                ("Light Healing", f"{Decimal('149.6'):.1f}%"),
                ("HP Shield", f"{Decimal('13.5'):.1f}%"),
            ]
        elif self.candy == Type.LATTE:
            return [
                ("Debuff Resist", f"{Decimal(20):.1f}%"),
                ("Amplified Debuffs", f"{Decimal(20):.1f}%"),
                ("Extra DMG", f'{Decimal("272.2") + (self.lvl - 1) * (Decimal("47.8") / Decimal(29)):.1f}%'),
                ("Healing Poisoned", f"{-Decimal(40):.1f}%"),
            ]
        elif self.candy == Type.TEA_KNIGHT:
            return [
                ("Skill Targets", "Extra DMG"),
                ("True DMG", f"{Decimal(10):.1f}%"),
                ("DMG (Others)", f"{linear(125, 200, 30)(self.lvl):.1f}%"),
                ("Skill Target Stun", f"2.0s"),
                ("Extra DMG (Stun Immune)", f"{Decimal(300):.1f}%"),
                ("Cooldown", f"-3.5s"),
                ("Healing", f"{Decimal('36.1'):.1f}%"),
                ("Passive ATK", f"{Decimal('1.5'):.1f}% per {Decimal(5):.1f}% Team's Total HP Lost"),
            ]
        elif self.candy == Type.WILDBERRY:
            return [
                ("HP Shield", f"{linear(3, 10, 30)(self.lvl):.1f}%"),
                ("Final Blow Extra DMG", f"{Decimal(175):.1f}%"),
            ]
        elif self.candy == Type.MANGO:
            return [
                ("HP Shield", f"{Decimal(20):.1f}%"),
                ("Extra DMG (Debuff Targets)", f"{linear(136, '163.2', 30)(self.lvl):.1f}%"),
                ("Great Wave", f"{Decimal(60):.1f}%"),
                ("Great Wave DMG", f"{Decimal('196.6'):.1f}%"),
            ]
        elif self.candy == Type.PARFAIT:
            return [
                ("HP Shield Convert", f"13.0s"),
                ("HP Shield", f"{linear('125.5', 178, 30)(self.lvl):.1f}%"),
                ("Debuff Immunity", f"4.0s"),
                ("Healing Received", f"{Decimal(6):.1f}%"),
            ]
        elif self.candy == Type.SORBET_SHARK:
            return [
                ("Extra Area DMG", f"{linear('670.3', '804.4', 30)(self.lvl):.1f}%"),
                ("Extra DMG", f"{Decimal(400):.1f}%"),
                ("Injury Max HP", f"{-Decimal('12.5'):.1f}%"),
            ]
        elif self.candy == Type.BLACK_RAISIN:
            return [
                ("Area DMG Hits", "+3 Times (8 Total)"),
                ("Area DMG After CRIT", f"{linear('162.5', 195, 30)(self.lvl):.1f}%"),
                ("Skill CRIT DMG", f"{Decimal(170):.1f}%"),
                ("Amplify Debuff", f"{Decimal(5):.1f}%"),
            ]
        elif self.candy == Type.SNOW_SUGAR:
            return [
                (
                    "Snow King",
                    f"{linear(74, '86.5', 30)(self.lvl):.1f}% ATK, {linear('195.5', '243.1', 30)(self.lvl):.1f}% DEF, {linear(339, 465, 30)(self.lvl):.1f}% HP",
                ),
                ("Snow King DMG", f"{Decimal('151.6'):.1f}%"),
                ("ATK (Others)", f"{Decimal('45.5'):.1f}%"),
                ("Additional DMG to Frozen", f"{Decimal('242.8'):.1f}%"),
                ("Snow King DMG Focus", f"{Decimal(50):.1f}%"),
            ]

    @property
    def enchantments(self):
        if self.candy == Type.ESPRESSO:
            base = [("Final Stun", "1.25s")]
            if self.lvl >= 30:
                return base + [("Extra DMG", "390.0%")]
            elif self.lvl >= 20:
                return base + [("Extra DMG", "357.5%")]
            elif self.lvl >= 10:
                return base + [("Extra DMG", "325.0%")]
        elif self.candy == Type.PURPLE_YAM:
            if self.lvl >= 30:
                return [
                    ("Fury Debuff Resist", f"{Decimal(40):.1f}%"),
                    ("Spirit DMG Resist", f"{Decimal(50):.1f}%"),
                ]
            elif self.lvl >= 20:
                return [
                    ("Fury Debuff Resist", f"{Decimal(30):.1f}%"),
                    ("Spirit DMG Resist", f"{Decimal(40):.1f}%"),
                ]
            elif self.lvl >= 10:
                return [
                    ("Fury Debuff Resist", f"{Decimal(20):.1f}%"),
                    ("Spirit DMG Resist", f"{Decimal(30):.1f}%"),
                ]
        elif self.candy == Type.VAMPIRE:
            base = [("Invulnerable", "1.0s")]
            if self.lvl >= 30:
                return base + [("Revive HP", "20.0%")]
            elif self.lvl >= 20:
                return base + [("Revive HP", "15.0%")]
            elif self.lvl >= 10:
                return base + [("Revive HP", "10.0%")]
        elif self.candy == Type.MILK:
            base = [("Noble Resolution", "Stack x3")]
            if self.lvl >= 30:
                return base + [
                    ("True DMG", f'{Decimal("1.50"):.2f}%'),
                    ("Single hit DMG", f"{Decimal(30):.1f}%"),
                ]
            elif self.lvl >= 20:
                return base + [
                    ("True DMG", f'{Decimal("1.25"):.2f}%'),
                    ("Single hit DMG", f"{Decimal(25):.1f}%"),
                ]
            elif self.lvl >= 10:
                return base + [
                    ("True DMG", f'{Decimal("1.00"):.2f}%'),
                    ("Single hit DMG", f"{Decimal(20):.1f}%"),
                ]
        elif self.candy == Type.RYE:
            if self.lvl >= 30:
                return [("Allies' ATK SPD", "25.0%")]
            elif self.lvl >= 20:
                return [("Allies' ATK SPD", "22.5%")]
            elif self.lvl >= 10:
                return [("Allies' ATK SPD", "20.0%")]
        elif self.candy == Type.SQUID_INK:
            if self.lvl >= 30:
                return [("DMG Reduction", "-1.2%")]
            elif self.lvl >= 20:
                return [("DMG Reduction", "-1.1%")]
            elif self.lvl >= 10:
                return [("DMG Reduction", "-1.0%")]
        elif self.candy == Type.WEREWOLF:
            base = [("Torn Scar", "17.0s")]
            if self.lvl >= 30:
                return base + [("Torn Scar", "40.0%")]
            elif self.lvl >= 20:
                return base + [("Torn Scar", "35.0%")]
            elif self.lvl >= 10:
                return base + [("Torn Scar", "30.0%")]
        elif self.candy == Type.LICORICE:
            if self.lvl >= 30:
                return [("HP Shield", "40.0%")]
            elif self.lvl >= 20:
                return [("HP Shield", "35.0%")]
            elif self.lvl >= 10:
                return [("HP Shield", "30.0%")]
        elif self.candy == Type.CREAM_PUFF:
            if self.lvl >= 30:
                return [
                    ("CRIT DMG", f'{Decimal("0.50"):.2f}%'),
                ]
            elif self.lvl >= 20:
                return [
                    ("CRIT DMG", f'{Decimal("0.35"):.2f}%'),
                ]
            elif self.lvl >= 10:
                return [
                    ("CRIT DMG", f'{Decimal("0.30"):.2f}%'),
                ]
        elif self.candy == Type.MALA_SAUCE:
            if self.lvl >= 30:
                return [("DMG Resist", "2.0%"), ("Fire CRIT DMG", "15.0%")]
            elif self.lvl >= 20:
                return [("DMG Resist", "1.5%")]
            elif self.lvl >= 10:
                return [("DMG Resist", "1.0%")]
        elif self.candy == Type.MADELEINE:
            if self.lvl >= 30:
                return [("Team Light DMG", "30.0%")]
            elif self.lvl >= 20:
                return [("Team Light DMG", "25.0%")]
            elif self.lvl >= 10:
                return [("Team Light DMG", "20.0%")]
        elif self.candy == Type.LATTE:
            if self.lvl >= 30:
                return [
                    ("Silence Duration", f"{Decimal('1.7'):.1f}s"),
                    ("Restore Ally HP", f"{Decimal(30):.1f}%"),
                    ("Outer Latte", f"Equal to Inner Latte"),
                ]
            elif self.lvl >= 20:
                return [
                    ("Silence Duration", f"{Decimal('1.6'):.1f}s"),
                    ("Restore Ally HP", f"{Decimal(25):.1f}%"),
                ]
            elif self.lvl >= 10:
                return [
                    ("Silence Duration", f"{Decimal('1.5'):.1f}s"),
                    ("Restore Ally HP", f"{Decimal(20):.1f}%"),
                ]
        elif self.candy == Type.TEA_KNIGHT:
            if self.lvl >= 30:
                return [
                    ("Regular Targets", "Extra DMG"),
                    ("True DMG", f"{Decimal(3):.1f}%"),
                    ("DMG (Others)", f"{Decimal(175):.1f}%"),
                ]
            elif self.lvl >= 20:
                return [
                    ("Regular Targets", "Extra DMG"),
                    ("True DMG", f"{Decimal(2):.1f}%"),
                    ("DMG (Others)", f"{Decimal(150):.1f}%"),
                ]
            elif self.lvl >= 10:
                return [
                    ("Regular Targets", "Extra DMG"),
                    ("True DMG", f"{Decimal(1):.1f}%"),
                    ("DMG (Others)", f"{Decimal(125):.1f}%"),
                ]
        elif self.candy == Type.WILDBERRY:
            if self.lvl >= 30:
                return [("Ally CRIT Resist", "20.0%")]
            elif self.lvl >= 20:
                return [("Ally CRIT Resist", "15.0%")]
            elif self.lvl >= 10:
                return [("Ally CRIT Resist", "10.0%")]
        elif self.candy == Type.MANGO:
            if self.lvl >= 30:
                return [("Giant Wave DMG", "30.0%")]
            elif self.lvl >= 20:
                return [("Giant Wave DMG", "25.0%")]
            elif self.lvl >= 10:
                return [("Giant Wave DMG", "20.0%")]
        elif self.candy == Type.PARFAIT:
            if self.lvl >= 30:
                return [("Team Healing", "138.6%")]
            elif self.lvl >= 20:
                return [("Team Healing", "133.9%")]
            elif self.lvl >= 10:
                return [("Team Healing", "123.8%")]
        elif self.candy == Type.SORBET_SHARK:
            if self.lvl >= 30:
                return [("Healing Debuff", "-50.0%")]
            elif self.lvl >= 20:
                return [("Healing Debuff", "-45.0%")]
            elif self.lvl >= 10:
                return [("Healing Debuff", "-40.0%")]
        elif self.candy == Type.BLACK_RAISIN:
            if self.lvl >= 30:
                return [("Received DMG", "5.0%")]
            elif self.lvl >= 20:
                return [("Received DMG", "4.4%")]
            elif self.lvl >= 10:
                return [("Received DMG", "3.8%")]
        elif self.candy == Type.SNOW_SUGAR:
            if self.lvl >= 30:
                return [("Snow King HP Shield", "100.0%")]
            elif self.lvl >= 20:
                return [("Snow King HP Shield", "90.0%")]
            elif self.lvl >= 10:
                return [("Snow King HP Shield", "80.0%")]
