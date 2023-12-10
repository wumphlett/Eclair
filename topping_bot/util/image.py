from collections import defaultdict
from datetime import datetime
from typing import List
from zoneinfo import ZoneInfo

import numpy as np
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont

from topping_bot.crk.cookies import Cookie, Position
from topping_bot.crk.toppings import INFO, Resonance, Topping, ToppingSet, Type
from topping_bot.util.const import TMP_PATH, STATIC_PATH
from topping_bot.util.utility import order_path

TOPPING_PATH = STATIC_PATH / "topping"
TOPPINGS = {
    Resonance.NORMAL: {
        Type.DMGRES: Image.open(TOPPING_PATH / f"{INFO[Type.DMGRES]['filename']}.png").resize((101, 148)),
        Type.ATK: Image.open(TOPPING_PATH / f"{INFO[Type.ATK]['filename']}.png").resize((101, 148)),
        Type.CD: Image.open(TOPPING_PATH / f"{INFO[Type.CD]['filename']}.png").resize((101, 148)),
        Type.ATKSPD: Image.open(TOPPING_PATH / f"{INFO[Type.ATKSPD]['filename']}.png").resize((101, 148)),
        Type.CRIT: Image.open(TOPPING_PATH / f"{INFO[Type.CRIT]['filename']}.png").resize((101, 148)),
        Type.HP: Image.open(TOPPING_PATH / f"{INFO[Type.HP]['filename']}.png").resize((101, 148)),
        Type.BUFF: Image.open(TOPPING_PATH / f"{INFO[Type.BUFF]['filename']}.png").resize((101, 148)),
        Type.DEF: Image.open(TOPPING_PATH / f"{INFO[Type.DEF]['filename']}.png").resize((101, 148)),
        Type.BUFFRES: Image.open(TOPPING_PATH / f"{INFO[Type.BUFFRES]['filename']}.png").resize((101, 148)),
        Type.CRITRES: Image.open(TOPPING_PATH / f"{INFO[Type.CRITRES]['filename']}.png").resize((101, 148)),
    },
    Resonance.MOONKISSED: {
        Type.DMGRES: Image.open(TOPPING_PATH / "moonkissed" / f"{INFO[Type.DMGRES]['filename']}.png").resize(
            (101, 148)
        ),
        Type.ATK: Image.open(TOPPING_PATH / "moonkissed" / f"{INFO[Type.ATK]['filename']}.png").resize((101, 148)),
        Type.CD: Image.open(TOPPING_PATH / "moonkissed" / f"{INFO[Type.CD]['filename']}.png").resize((101, 148)),
        Type.ATKSPD: Image.open(TOPPING_PATH / "moonkissed" / f"{INFO[Type.ATKSPD]['filename']}.png").resize(
            (101, 148)
        ),
        Type.CRIT: Image.open(TOPPING_PATH / "moonkissed" / f"{INFO[Type.CRIT]['filename']}.png").resize((101, 148)),
    },
    Resonance.TRIO: {
        Type.DMGRES: Image.open(TOPPING_PATH / "trio" / f"{INFO[Type.DMGRES]['filename']}.png").resize((101, 148)),
        Type.ATK: Image.open(TOPPING_PATH / "trio" / f"{INFO[Type.ATK]['filename']}.png").resize((101, 148)),
        Type.CD: Image.open(TOPPING_PATH / "trio" / f"{INFO[Type.CD]['filename']}.png").resize((101, 148)),
        Type.ATKSPD: Image.open(TOPPING_PATH / "trio" / f"{INFO[Type.ATKSPD]['filename']}.png").resize((101, 148)),
        Type.CRIT: Image.open(TOPPING_PATH / "trio" / f"{INFO[Type.CRIT]['filename']}.png").resize((101, 148)),
    },
    Resonance.DRACONIC: {
        Type.DMGRES: Image.open(TOPPING_PATH / "draconic" / f"{INFO[Type.DMGRES]['filename']}.png").resize((101, 148)),
        Type.ATK: Image.open(TOPPING_PATH / "draconic" / f"{INFO[Type.ATK]['filename']}.png").resize((101, 148)),
        Type.CD: Image.open(TOPPING_PATH / "draconic" / f"{INFO[Type.CD]['filename']}.png").resize((101, 148)),
        Type.ATKSPD: Image.open(TOPPING_PATH / "draconic" / f"{INFO[Type.ATKSPD]['filename']}.png").resize((101, 148)),
        Type.CRIT: Image.open(TOPPING_PATH / "draconic" / f"{INFO[Type.CRIT]['filename']}.png").resize((101, 148)),
    },
    Resonance.TROPICAL_ROCK: {
        Type.DMGRES: Image.open(TOPPING_PATH / "tropical" / f"{INFO[Type.DMGRES]['filename']}.png").resize((101, 148)),
        Type.ATK: Image.open(TOPPING_PATH / "tropical" / f"{INFO[Type.ATK]['filename']}.png").resize((101, 148)),
        Type.CD: Image.open(TOPPING_PATH / "tropical" / f"{INFO[Type.CD]['filename']}.png").resize((101, 148)),
        Type.ATKSPD: Image.open(TOPPING_PATH / "tropical" / f"{INFO[Type.ATKSPD]['filename']}.png").resize((101, 148)),
        Type.CRIT: Image.open(TOPPING_PATH / "tropical" / f"{INFO[Type.CRIT]['filename']}.png").resize((101, 148)),
    },
    Resonance.SEA_SALT: {
        Type.DMGRES: Image.open(TOPPING_PATH / "sea" / f"{INFO[Type.DMGRES]['filename']}.png").resize((101, 148)),
        Type.ATK: Image.open(TOPPING_PATH / "sea" / f"{INFO[Type.ATK]['filename']}.png").resize((101, 148)),
        Type.CD: Image.open(TOPPING_PATH / "sea" / f"{INFO[Type.CD]['filename']}.png").resize((101, 148)),
        Type.ATKSPD: Image.open(TOPPING_PATH / "sea" / f"{INFO[Type.ATKSPD]['filename']}.png").resize((101, 148)),
        Type.CRIT: Image.open(TOPPING_PATH / "sea" / f"{INFO[Type.CRIT]['filename']}.png").resize((101, 148)),
    },
    Resonance.RADIANT_CHEESE: {
        Type.DMGRES: Image.open(TOPPING_PATH / "cheese" / f"{INFO[Type.DMGRES]['filename']}.png").resize((101, 148)),
        Type.ATK: Image.open(TOPPING_PATH / "cheese" / f"{INFO[Type.ATK]['filename']}.png").resize((101, 148)),
        Type.CD: Image.open(TOPPING_PATH / "cheese" / f"{INFO[Type.CD]['filename']}.png").resize((101, 148)),
        Type.ATKSPD: Image.open(TOPPING_PATH / "cheese" / f"{INFO[Type.ATKSPD]['filename']}.png").resize((101, 148)),
        Type.CRIT: Image.open(TOPPING_PATH / "cheese" / f"{INFO[Type.CRIT]['filename']}.png").resize((101, 148)),
    },
    Resonance.FROSTED_CRYSTAL: {
        Type.DMGRES: Image.open(TOPPING_PATH / "crystal" / f"{INFO[Type.DMGRES]['filename']}.png").resize((101, 148)),
        Type.ATK: Image.open(TOPPING_PATH / "crystal" / f"{INFO[Type.ATK]['filename']}.png").resize((101, 148)),
        Type.CD: Image.open(TOPPING_PATH / "crystal" / f"{INFO[Type.CD]['filename']}.png").resize((101, 148)),
        Type.ATKSPD: Image.open(TOPPING_PATH / "crystal" / f"{INFO[Type.ATKSPD]['filename']}.png").resize((101, 148)),
        Type.CRIT: Image.open(TOPPING_PATH / "crystal" / f"{INFO[Type.CRIT]['filename']}.png").resize((101, 148)),
    },
}
STATIC = {
    "font": ImageFont.truetype(str(TOPPING_PATH / "font.otf"), size=38),
    "button": ImageEnhance.Brightness(Image.open(TOPPING_PATH / "button.png").resize((196, 196))).enhance(5),
    "blank": Image.open(TOPPING_PATH / "blank.png").resize((51, 80)),
    "holder": Image.open(TOPPING_PATH / "holder.png").resize((479, 490)),
}

MISC_PATH = STATIC_PATH / "misc"
POSITION = (
    (Position.FRONT, Image.open(MISC_PATH / "front_pos.png").resize((64, 43))),
    (Position.MIDDLE, Image.open(MISC_PATH / "middle_pos.png").resize((64, 43))),
    (Position.REAR, Image.open(MISC_PATH / "rear_pos.png").resize((64, 43))),
)

GACHA_BACKGROUND = Image.open(MISC_PATH / "cookie_get.png").resize((1920, 1040)).filter(ImageFilter.GaussianBlur(3))
SHINE_PATH = MISC_PATH / "shine"

TOPPING_BACKGROUND = Image.open(MISC_PATH / "loading.png").resize((1080, 1080))
SLOT = Image.open(MISC_PATH / "slot.png").resize((196, 196))

NEW = Image.open(MISC_PATH / "new.png").resize((90, 97))
LOCK = Image.open(MISC_PATH / "lock.png").resize((37, 45))
ARROW = Image.open(MISC_PATH / "up_arrow.png").resize((50, 54))
GUAGE = {
    "back": Image.open(MISC_PATH / "gauge" / "old-back.png").convert("RGBA"),
    "green": Image.open(MISC_PATH / "gauge" / "old-green.png").convert("RGBA"),
    "yellow": Image.open(MISC_PATH / "gauge" / "old-yellow.png").convert("RGBA"),
}

GACHA_INV_BACKGROUND = Image.open(MISC_PATH / "inv_background.png").resize((1200, 1120))
LOCK_INV = Image.open(MISC_PATH / "lock.png").resize((50, 61)).convert("LA").convert("RGBA")
GUAGE_INV = {
    "back": Image.open(MISC_PATH / "gauge" / "old-back.png").resize((32, 27)).convert("RGBA"),
    "green": Image.open(MISC_PATH / "gauge" / "old-green.png").resize((32, 24)).convert("RGBA"),
    "yellow": Image.open(MISC_PATH / "gauge" / "old-yellow.png").resize((32, 24)).convert("RGBA"),
}
MILEAGE = Image.open(MISC_PATH / "mileage.png").resize((35, 37))

GUAGE_COOKIE = {
    "back": Image.open(MISC_PATH / "gauge" / "old-back.png").resize((48, 42)).convert("RGBA"),
    "green": Image.open(MISC_PATH / "gauge" / "old-green.png").resize((48, 39)).convert("RGBA"),
    "yellow": Image.open(MISC_PATH / "gauge" / "old-yellow.png").resize((48, 39)).convert("RGBA"),
}


def image_midline(image):
    matrix = image.load()
    (X, Y) = image.size
    m = np.zeros((X, Y))

    for x in range(X):
        for y in range(Y):
            m[x, y] = matrix[(x, y)] != (0, 0, 0, 0)
    m = m / np.sum(np.sum(m))

    dx = np.sum(m, 1)
    return round(np.sum(dx * np.arange(X)))


def toppings_to_images(toppings: List[Topping], user_id, show_index=False):
    images = []

    for i, subset in enumerate(toppings[i : i + 25] for i in range(0, len(toppings), 25)):
        fp = TMP_PATH / f"{user_id}-{i}.png"

        image = TOPPING_BACKGROUND.copy()
        draw = ImageDraw.Draw(image)

        for y_mult in range(5):
            for x_mult in range(5):
                if y_mult * 5 + x_mult >= len(subset):
                    break
                else:
                    topping = subset[y_mult * 5 + x_mult]

                x, y = 10 + x_mult * 216, 10 + y_mult * 216

                image.paste(SLOT, (x, y), SLOT)
                image.paste(
                    TOPPINGS[topping.resonance][topping.flavor],
                    (x + 47, y + 21),
                    TOPPINGS[topping.resonance][topping.flavor],
                )
                sub_left = "\n".join(INFO[sub[0]]["short"] for sub in topping.substats[1:])
                sub_right = "\n".join(str(sub[1]) for sub in topping.substats[1:])
                draw.multiline_text(
                    (x + 28, y + 22),
                    sub_left,
                    font=STATIC["font"],
                    fill="rgb(255, 255, 255)",
                    stroke_fill="rgb(0, 0, 0)",
                    stroke_width=2,
                )
                draw.multiline_text(
                    (x + 118, y + 22),
                    sub_right,
                    font=STATIC["font"],
                    fill="rgb(255, 255, 255)",
                    stroke_fill="rgb(0, 0, 0)",
                    stroke_width=2,
                    align="right",
                )
                show_index and draw.text(
                    (x - 10, y + 160),
                    str(i * 25 + y_mult * 5 + x_mult),
                    font=STATIC["font"],
                    fill="rgb(255, 255, 0)",
                    stroke_fill="rgb(0, 0, 0)",
                    stroke_width=2,
                )

        image.save(fp)
        images.append(fp)
    return images


def topping_set_to_image(topping_set: ToppingSet, user_id):
    fp = TMP_PATH / f"{user_id}.png"

    image = Image.new("RGBA", (1080, 1080), "rgb(3, 5, 9)")
    draw = ImageDraw.Draw(image)

    draw.rounded_rectangle(
        ((10, 10), (1070, 530)),
        fill="rgb(44, 49, 65)",
        outline="rgb(74, 93, 180)",
        width=5,
        radius=30,
    )
    draw.rounded_rectangle(
        ((10, 550), (1070, 935)),
        fill="rgb(35, 35, 37)",
        outline="rgb(50, 51, 53)",
        width=2,
        radius=30,
    )
    draw.rounded_rectangle(
        ((10, 955), (530, 1070)),
        fill="rgb(35, 35, 37)",
        outline="rgb(50, 51, 53)",
        width=2,
        radius=30,
    )
    draw.rounded_rectangle(
        ((550, 955), (1070, 1070)),
        fill="rgb(35, 35, 37)",
        outline="rgb(50, 51, 53)",
        width=2,
        radius=30,
    )

    coords = [(195, 64), (255, 142), (215, 243), (82, 243), (38, 142)]
    font = ImageFont.truetype(str(TOPPING_PATH / "font.otf"), size=54)
    image.paste(STATIC["holder"], (25, 25), STATIC["holder"])

    def topping_text_sort(x: Topping):
        temp_subs = " : ".join(f"{INFO[sub[0]]['short']} {sub[1]}" for sub in x.substats[1:])
        return draw.textlength(temp_subs, font=font)

    topping_set.toppings.sort(key=topping_text_sort)
    toppings = topping_set.toppings
    toppings = [toppings[3], toppings[1], toppings[0], toppings[2], toppings[4]]

    for i, topping in enumerate(toppings):
        topping_img = TOPPINGS[topping.resonance][topping.flavor].resize((135, 198)).rotate(i * -72, expand=True)
        image.paste(topping_img, coords[i], topping_img)
        image.paste(STATIC["blank"], (1004, 100 * i + 34), STATIC["blank"])
        topping_img = TOPPINGS[topping.resonance][topping.flavor].resize((46, 67))
        image.paste(topping_img, (1007, 100 * i + 39), topping_img)
        subs = " : ".join(f"{INFO[sub[0]]['short']} {sub[1]}" for sub in topping.substats[1:])
        draw.text(
            (990, 100 * i + 36),
            subs,
            font=font,
            fill="rgb(255, 255, 255)",
            stroke_fill="rgb(0, 0, 0)",
            stroke_width=5,
            anchor="ra",
        )

    font = ImageFont.truetype(str(TOPPING_PATH / "font.otf"), size=48)

    for i, (left, right) in enumerate(
        [
            (Type.ATK, Type.DEF),
            (Type.HP, Type.ATKSPD),
            (Type.CRIT, Type.CD),
            (Type.DMGRES, Type.CRITRES),
            (Type.BUFF, Type.BUFFRES),
        ]
    ):
        draw.text(
            (30, 75 * i + 560),
            left.value,
            font=font,
            fill="rgb(140, 140, 140)",
            stroke_fill="rgb(0, 0, 0)",
            stroke_width=2,
        )
        left_percent = topping_set.raw(left)
        draw.text(
            (520, 75 * i + 560),
            f"{str(left_percent) + '%' if left_percent else '-'}",
            font=font,
            fill="rgb(255, 255, 255)",
            stroke_fill="rgb(0, 0, 0)",
            stroke_width=2,
            anchor="ra",
        )
        draw.text(
            (560, 75 * i + 560),
            right.value,
            font=font,
            fill="rgb(140, 140, 140)",
            stroke_fill="rgb(0, 0, 0)",
            stroke_width=2,
        )
        right_percent = topping_set.raw(right)
        draw.text(
            (1050, 75 * i + 560),
            f"{str(right_percent) + '%' if right_percent else '-'}",
            font=font,
            fill="rgb(255, 255, 255)",
            stroke_fill="rgb(0, 0, 0)",
            stroke_width=2,
            anchor="ra",
        )

    set_bonuses = []
    for substat in INFO.keys():
        possible_set_bonuses = INFO[substat]["view_combos"]
        for count, bonus in possible_set_bonuses:
            if count <= len([topping for topping in topping_set.toppings if topping.flavor == substat]):
                set_bonuses.append((count, substat, bonus))

    font = ImageFont.truetype(str(TOPPING_PATH / "font.otf"), size=38)

    set_bonuses.sort()
    for i, (_, substat, bonus) in enumerate(set_bonuses):
        draw.text(
            (540 * i + 270, 959),
            f"{' '.join(INFO[substat]['name'].split()[1:])} Set Effect",
            font=font,
            fill="rgb(194, 251, 92)",
            stroke_fill="rgb(0, 0, 0)",
            stroke_width=2,
            anchor="ma",
        )
        draw.text(
            (540 * i + 270, 1017),
            f"{substat.value} {bonus}%",
            font=font,
            fill="rgb(194, 251, 92)",
            stroke_fill="rgb(0, 0, 0)",
            stroke_width=2,
            anchor="ma",
        )

    image.save(fp)
    return fp


def gacha_pull_to_image(pull: List, gacha, user_id):
    fp = TMP_PATH / f"gacha-{user_id}.png"

    image = GACHA_BACKGROUND.copy()
    draw = ImageDraw.Draw(image)

    font = ImageFont.truetype(str(TOPPING_PATH / "old_font.otf"), size=96)
    draw.text(
        (960, 80),
        "Results",
        font=font,
        fill="rgb(255, 255, 255)",
        stroke_fill="rgb(0, 0, 0)",
        stroke_width=2,
        anchor="mt",
    )

    mods = defaultdict(int)

    stone_font = ImageFont.truetype(str(TOPPING_PATH / "old_font.otf"), size=46)
    twenty_stone_font = ImageFont.truetype(str(TOPPING_PATH / "old_font.otf"), size=44)
    banner_stone_font = ImageFont.truetype(str(TOPPING_PATH / "old_font.otf"), size=28)
    fraction_font = ImageFont.truetype(str(TOPPING_PATH / "old_font.otf"), size=28)
    for row, y in ((pull[:5], 360), (pull[5:], 720)):
        for (cookie, amount, stored), x in zip(row, (400, 680, 960, 1240, 1520)):
            if amount == 20:
                stand = Image.open(cookie.stand)
                stand = stand.resize((int(stand.width / 1.15), int(stand.height / 1.15)))
                stand_midline = image_midline(stand)

                shine = Image.open(SHINE_PATH / f"{cookie.rarity.value.lower().replace(' ', '')}.png")
                shine = shine.crop(shine.getbbox())
                shine = shine.resize((int(shine.width * 1.15), int(shine.height * 1.15)))

                image.alpha_composite(shine, (x - (shine.width // 2), y + 165 - shine.height))
                image.alpha_composite(stand, (x - stand_midline, y + 115 - stand.height))

                if not gacha.is_unlock(inv=stored, amount=amount):
                    stone = Image.open(cookie.stone(ascended=gacha.is_ascended(pk=str(cookie.id))))
                    stone = stone.resize((60, 60)) if gacha.is_ascended(pk=str(cookie.id)) else stone.resize((58, 58))
                    image.alpha_composite(stone, (x - 68, y + 44 + (1 if gacha.is_ascended(pk=str(cookie.id)) else 0)))
                    draw.text(
                        (x + 22, y + 60),
                        f"x{amount}",
                        font=twenty_stone_font,
                        fill="rgb(255, 255, 255)",
                        stroke_fill="rgb(0, 0, 0)",
                        stroke_width=3,
                        anchor="mt",
                    )
                else:
                    image.alpha_composite(NEW, (x - 140, y - 140))

                banner = Image.open(cookie.banner)
                banner = banner.resize((int(banner.width / 1.5), int(banner.height / 1.5)))
                image.alpha_composite(banner, (x - (banner.width // 2), y + 107))

                draw.text(
                    (x, y + 116),
                    f"{cookie.rarity.value.upper()}",
                    font=banner_stone_font,
                    fill="rgb(247,245,254)",
                    stroke_fill="rgb(38, 34, 30)",
                    stroke_width=1,
                    anchor="mt",
                )
            else:
                stone = Image.open(cookie.stone(ascended=gacha.is_ascended(pk=str(cookie.id))))

                if gacha.is_ascended(pk=str(cookie.id)):
                    stone = stone.crop((0, 0, stone.width - 2, stone.height - 2))

                benchmark = 160 if gacha.is_ascended(pk=str(cookie.id)) else 154
                stone = stone.crop(stone.getbbox())
                stone = stone.resize((int(stone.width / (stone.height / benchmark)), benchmark))
                image.alpha_composite(
                    stone, (x - (stone.width // 2), y - 90 + (2 if gacha.is_ascended(pk=str(cookie.id)) else 0))
                )
                draw.text(
                    (x - 16, y + 50),
                    f"x",
                    font=stone_font,
                    fill="rgb(255, 255, 255)",
                    stroke_fill="rgb(0, 0, 0)",
                    stroke_width=3,
                    anchor="mt",
                )
                draw.text(
                    (x + 15, y + 39),
                    f"{amount}",
                    font=stone_font,
                    fill="rgb(255, 255, 255)",
                    stroke_fill="rgb(0, 0, 0)",
                    stroke_width=3,
                    anchor="mt",
                )

            if not (amount == 20 and gacha.is_unlock(inv=stored + mods.get(cookie.id, 0), amount=amount)):
                num, denom = gacha.fraction(stored)
                upper = min(denom, num + amount + mods[cookie.id])

                left = GUAGE["back"].crop((0, 0, 25, GUAGE["back"].height))
                middle = GUAGE["back"].crop((25, 0, 35, GUAGE["back"].height))
                right = GUAGE["back"].crop((35, 0, GUAGE["back"].width, GUAGE["back"].height))

                image.alpha_composite(left, (x - 115, y + 103))
                for offset in range(0, 180, 10):
                    image.alpha_composite(middle, (x - 90 + offset, y + 103))
                image.alpha_composite(right, (x + 90, y + 103))

                thresh = 0.2
                if upper / denom >= thresh * 0.75:
                    prog = GUAGE["green"] if upper == denom and denom != 1 else GUAGE["yellow"]

                    left = prog.crop((0, 0, 25, prog.height))
                    middle = prog.crop((29, 0, 30, prog.height))
                    right = prog.crop((35, 0, prog.width, prog.height))

                    image.alpha_composite(left, (x - 114, y + 104))
                    offset = 0
                    for pixel in range(int(178 * ((upper / denom) * (1 + thresh) - thresh))):
                        image.alpha_composite(middle, (x - 89 + offset, y + 104))
                        offset += 1
                    image.alpha_composite(right, (x - 89 + offset, y + 104))

                if denom == 1:
                    bar_msg = "MAX"
                elif gacha.is_unlock(inv=stored, amount=amount):
                    bar_msg = "Meet now!"
                else:
                    bar_msg = f"{num + amount + mods[cookie.id]}/{denom}"

                draw.text(
                    (x, y + 114),
                    bar_msg,
                    font=fraction_font,
                    fill="rgb(255, 255, 255)",
                    stroke_fill="rgb(0, 0, 0)",
                    stroke_width=2,
                    anchor="mt",
                )

                if upper == denom and denom != 1:
                    image.alpha_composite(ARROW, (x + 90, y + 92))
                elif not gacha.is_unlocked(pk=str(cookie.id)):
                    image.alpha_composite(LOCK, (x + 90, y + 106))

            # MILEAGE
            if gacha.inventory[str(cookie.id)] > 490:
                mileage_msg = f"x{gacha.single_mileage(cookie, amount, gacha.inventory[str(cookie.id)])}"
                essence_msg = f"x{min(gacha.inventory[str(cookie.id)] - 490, amount)}"
                mileage_font = ImageFont.truetype(str(TOPPING_PATH / "old_font.otf"), size=26)
                length = (
                    40
                    + 2
                    + draw.textlength(essence_msg, font=mileage_font)
                    + 10
                    + 35
                    + 3
                    + draw.textlength(mileage_msg, font=mileage_font)
                )

                soul_essence = Image.open(cookie.essence).resize((40, 40))
                image.alpha_composite(soul_essence, (x - int(length / 2) - 2, y + 161))
                draw.text(
                    (x - int(length / 2) + 40 + 2 - 2, y + 170),
                    essence_msg,
                    font=mileage_font,
                    fill="rgb(255, 255, 255)",
                    stroke_fill="rgb(0, 0, 0)",
                    stroke_width=2,
                    anchor="lt",
                )

                image.alpha_composite(
                    MILEAGE,
                    (
                        x - int(length / 2) + 40 + 2 + int(draw.textlength(essence_msg, font=mileage_font)) + 10 - 2,
                        y + 163,
                    ),
                )
                draw.text(
                    (
                        x
                        - int(length / 2)
                        + 40
                        + 2
                        + int(draw.textlength(essence_msg, font=mileage_font))
                        + 10
                        + 35
                        + 3
                        - 2,
                        y + 170,
                    ),
                    f"x{gacha.single_mileage(cookie, amount, gacha.inventory[str(cookie.id)])}",
                    font=mileage_font,
                    fill="rgb(255, 255, 255)",
                    stroke_fill="rgb(0, 0, 0)",
                    stroke_width=2,
                    anchor="lt",
                )
            else:
                mileage_msg = f"x{gacha.single_mileage(cookie, amount, gacha.inventory[str(cookie.id)])}"
                mileage_font = ImageFont.truetype(str(TOPPING_PATH / "old_font.otf"), size=26)
                length = 35 + 3 + draw.textlength(mileage_msg, font=mileage_font)
                image.alpha_composite(MILEAGE, (x - int(length / 2) - 2, y + 163))
                draw.text(
                    (x - int(length / 2) + 35 + 3 - 2, y + 170),
                    f"x{gacha.single_mileage(cookie, amount, gacha.inventory[str(cookie.id)])}",
                    font=mileage_font,
                    fill="rgb(255, 255, 255)",
                    stroke_fill="rgb(0, 0, 0)",
                    stroke_width=2,
                    anchor="lt",
                )

            mods[cookie.id] += amount

    draw.text(
        (960, 986),
        "Tap to continue",
        font=fraction_font,
        fill="rgb(255, 255, 255)",
        stroke_fill="rgb(0, 0, 0)",
        stroke_width=2,
        anchor="mt",
    )

    image.save(fp)
    return fp


def gacha_inv_to_image(gacha, user_id):
    images = []
    fraction_font = ImageFont.truetype(str(TOPPING_PATH / "old_font.otf"), size=15)
    highest_font = ImageFont.truetype(str(TOPPING_PATH / "old_font.otf"), size=19)

    cookies = Cookie.all()
    for i, subset in enumerate(cookies[i : i + 25] for i in range(0, len(cookies), 25)):
        fp = TMP_PATH / f"gacha-inv-{user_id}-{i}.png"

        image = GACHA_INV_BACKGROUND.copy()
        draw = ImageDraw.Draw(image)

        x_base, y_base = 216, 220
        left_line, top_line = 70, 15
        for y_mult, row in enumerate(subset[i : i + 5] for i in range(0, len(subset), 5)):
            for x_mult, cookie in enumerate(row):
                card = Image.open(cookie.card).resize((196, 196))

                frame = Image.open(cookie.frame).resize((196, 220))
                frame_top = frame.crop((0, 0, 196, 170))
                frame_bottom = frame.crop((0, 180, 196, 220))

                role = Image.open(cookie.role_icon)
                role = role.resize((int(role.width / 2.5), int(role.height / 2.5)))

                if not gacha.is_unlocked(pk=str(cookie.id)):
                    card = card.convert("LA").convert("RGBA")
                    frame_top = frame_top.convert("LA").convert("RGBA")
                    frame_bottom = frame_bottom.convert("LA").convert("RGBA")

                image.alpha_composite(card, (left_line + x_base * x_mult, top_line + 220 * y_mult))
                image.alpha_composite(frame_top, (left_line + x_base * x_mult, top_line + y_base * y_mult))
                image.alpha_composite(frame_bottom, (left_line + x_base * x_mult, top_line + 170 + y_base * y_mult))
                image.alpha_composite(role, (left_line + x_base * x_mult + 145, top_line + y_base * y_mult + 15))

                if gacha.is_unlocked(pk=str(cookie.id)):
                    if gacha.inventory[str(cookie.id)] >= 40:
                        grade = Image.open(gacha.grade(pk=str(cookie.id)))
                        grade = grade.resize((int(grade.width / 1.5), int(grade.height / 1.5)))
                        image.alpha_composite(
                            grade,
                            (
                                left_line + x_base * x_mult - (grade.width // 2) + 100,
                                top_line + y_base * y_mult - (grade.height // 2) + 138,
                            ),
                        )
                else:
                    image.alpha_composite(LOCK_INV, (left_line + x_base * x_mult + 10, top_line + y_base * y_mult + 10))

                num, denom = gacha.fraction(gacha.inventory[str(cookie.id)])

                if denom != 1:
                    middle = GUAGE_INV["back"].crop((16, 0, 17, GUAGE_INV["back"].height))
                    right = GUAGE_INV["back"].crop((18, 0, GUAGE_INV["back"].width, GUAGE_INV["back"].height))

                    for offset in range(0, 136):
                        image.alpha_composite(
                            middle,
                            (left_line + x_base * x_mult + 10 + 19 + offset, top_line + y_base * y_mult + 169),
                        )
                    image.alpha_composite(
                        right, (left_line + x_base * x_mult + 10 + 155, top_line + y_base * y_mult + 169)
                    )

                    yellow = GUAGE_INV["yellow"]
                    if not gacha.is_unlocked(pk=str(cookie.id)):
                        yellow = ImageEnhance.Brightness(yellow.convert("LA")).enhance(0.45).convert("RGBA")

                    middle = yellow.crop((16, 0, 17, yellow.height))
                    right = yellow.crop((18, 0, yellow.width, yellow.height))

                    offset = 0
                    for pixel in range(int(136 * (num / denom))):
                        image.alpha_composite(
                            middle,
                            (left_line + x_base * x_mult + 10 + 19 + offset, top_line + y_base * y_mult + 170),
                        )
                        offset += 1
                    image.alpha_composite(
                        right, (left_line + x_base * x_mult + 10 + 19 + offset, top_line + y_base * y_mult + 170)
                    )

                    draw.text(
                        (left_line + x_base * x_mult + 112, top_line + y_base * y_mult + 175),
                        f"{num}/{denom}" if denom != 1 else "MAX",
                        font=fraction_font,
                        fill="rgb(255, 255, 255)",
                        stroke_fill="rgb(0, 0, 0)",
                        stroke_width=1,
                        anchor="mt",
                    )

                    stone = Image.open(cookie.stone(ascended=gacha.is_ascended(pk=str(cookie.id))))
                    stone = stone.resize((34, 34))

                    if gacha.is_ascended(pk=str(cookie.id)):
                        stone = stone.crop((0, 0, stone.width - 1, stone.height - 1))

                    alpha = stone.getchannel("A")

                    background = Image.new("RGBA", stone.size, color="rgb(0, 0, 0)")
                    background.putalpha(alpha)

                    border_size = 4
                    background = background.resize((background.size[0] + border_size, background.size[1] + border_size))
                    background.alpha_composite(stone, (int(border_size / 2), int(border_size / 2)))

                    image.alpha_composite(
                        background, (left_line + x_base * x_mult + 16, top_line + y_base * y_mult + 163)
                    )
                else:
                    draw.text(
                        (left_line + x_base * x_mult + 98, top_line + y_base * y_mult + 174),
                        "Highest Grade!",
                        font=highest_font,
                        fill="rgb(255, 224, 69)",
                        stroke_fill="rgb(0, 0, 0)",
                        stroke_width=1,
                        anchor="mt",
                    )

        image.save(fp)
        images.append(fp)

    return images


def cookie_to_image(cookie, gacha, user_id):
    fp = TMP_PATH / f"cookie-{user_id}.png"

    image = Image.open(cookie.lobby).crop((0, 35, 1200, 685)).resize((1920, 1040))
    draw = ImageDraw.Draw(image)

    # Cookie Sprite
    cookie_stand = Image.open(cookie.stand)
    cookie_stand = cookie_stand.resize((int(cookie_stand.width * 1.2), int(cookie_stand.height * 1.2)))
    cookie_stand_midline = image_midline(cookie_stand)

    if not gacha.is_unlocked(pk=str(cookie.id)):
        cookie_stand = ImageEnhance.Brightness(cookie_stand).enhance(0.72)

    image.alpha_composite(cookie_stand, (686 - cookie_stand_midline, 680 - cookie_stand.height))

    # Grade
    if gacha.is_unlocked(pk=str(cookie.id)):
        grade_fp = gacha.fancy_grade(pk=str(cookie.id))
        grade = Image.open(grade_fp)
        if "fancy" in grade_fp.stem:
            grade = ImageEnhance.Sharpness(grade.resize((int(grade.width / 1.25), int(grade.height / 1.25)))).enhance(
                1.2
            )
        else:
            grade = grade.resize((int(grade.width * 1.4), int(grade.height * 1.4)))
        image.alpha_composite(grade, (682 - (grade.width // 2), 708 if "fancy" in grade_fp.stem else 694))

    # Progress Bar
    num, denom = gacha.fraction(gacha.inventory[str(cookie.id)])

    middle = GUAGE_COOKIE["back"].crop((16, 0, 17, GUAGE_COOKIE["back"].height))
    right = GUAGE_COOKIE["back"].crop((18, 0, GUAGE_COOKIE["back"].width, GUAGE_COOKIE["back"].height))

    for offset in range(261):
        image.alpha_composite(middle, (555 + offset, 791))
    image.alpha_composite(right, (816, 791))

    progress = GUAGE_COOKIE["yellow"] if denom != 1 else GUAGE_COOKIE["green"]

    middle = progress.crop((16, 0, 17, progress.height))
    right = progress.crop((18, 0, progress.width, progress.height))

    offset = 0
    for pixel in range(int(261 * (num / denom))):
        image.alpha_composite(middle, (555 + offset, 792))
        offset += 1
    image.alpha_composite(right, (555 + offset, 792))

    fraction_font = ImageFont.truetype(str(TOPPING_PATH / "old_font.otf"), size=24)
    draw.text(
        (705, 801),
        f"{num}/{denom}" if denom != 1 else "MAX",
        font=fraction_font,
        fill="rgb(255, 255, 255)",
        stroke_fill="rgb(0, 0, 0)",
        stroke_width=2,
        anchor="mt",
    )

    if not gacha.is_unlocked(pk=str(cookie.id)):
        lock = Image.open(MISC_PATH / "lock.png").resize((61, 74))
        image.alpha_composite(lock, (802, 772))

    # Soulstone
    stone = Image.open(cookie.stone(ascended=gacha.is_ascended(pk=str(cookie.id))))
    stone = stone.resize((66, 66))

    alpha = stone.getchannel("A")
    background = Image.new("RGBA", stone.size, color="rgb(0, 0, 0)")
    background.putalpha(alpha)

    border_size = 4
    background = background.resize((background.size[0] + border_size, background.size[1] + border_size))
    background.alpha_composite(stone, (int(border_size / 2), int(border_size / 2)))

    image.alpha_composite(background, (520, 776))

    # Bounding Rectangles
    rectangle_canvas = Image.new("RGBA", image.size, (255, 255, 255, 0))
    rectangle_draw = ImageDraw.Draw(rectangle_canvas)

    # rectangle_draw.rounded_rectangle(
    #     ((170, 710), (400, 940)),
    #     fill=(0, 0, 0, 0),
    #     outline=(0, 0, 0, 190),
    #     width=2,
    #     radius=32,
    # )
    rectangle_draw.rounded_rectangle(  # Skill Box
        ((170, 710), (400, 940)),
        fill=(30, 30, 30, 190),
        outline=(45, 45, 45, 190),
        width=2,
        radius=32,
    )
    rectangle_draw.rounded_rectangle(  # ID Box
        ((170, 252), (400, 298)),
        fill=(30, 30, 30, 190),
        outline=(45, 45, 45, 190),
        width=2,
        radius=24,
    )
    rectangle_draw.rounded_rectangle(  # Role Box
        ((170, 308), (400, 354)),
        fill=(30, 30, 30, 190),
        outline=(45, 45, 45, 190),
        width=2,
        radius=24,
    )
    rectangle_draw.rounded_rectangle(  # Position Box
        ((170, 364), (400, 410)),
        fill=(30, 30, 30, 190),
        outline=(45, 45, 45, 190),
        width=2,
        radius=24,
    )

    image.alpha_composite(rectangle_canvas)

    # Skill
    skill = Image.open(cookie.skill).resize((170, 170))
    image.alpha_composite(skill, (200, 740))

    # Rarity Banner
    banner = Image.open(cookie.banner)
    banner = banner.resize((int(banner.width / 1.6), int(banner.height / 1.6)))
    image.alpha_composite(banner, (170, 130))

    banner_stone_font = ImageFont.truetype(str(TOPPING_PATH / "old_font.otf"), size=26)

    draw.text(
        (170 + banner.width // 2, 139),
        f"{cookie.rarity.value.upper()}",
        font=banner_stone_font,
        fill="rgb(230, 230, 230)",
        stroke_fill="rgb(38, 34, 30)",
        stroke_width=1,
        anchor="mt",
    )

    # Cookie Name
    banner_stone_font = ImageFont.truetype(str(TOPPING_PATH / "old_font.otf"), size=40)
    draw.text(
        (184, 190),
        f"{cookie.name} Cookie",
        font=banner_stone_font,
        fill="rgb(255, 255, 255)",
        stroke_fill="rgb(0, 0, 0)",
        stroke_width=2,
        anchor="lt",
    )

    # Information
    info_font = ImageFont.truetype(str(TOPPING_PATH / "old_font.otf"), size=22)
    draw.text(
        (192, 266),
        f"ID",
        font=info_font,
        fill="rgb(255, 255, 255)",
        stroke_fill="rgb(0, 0, 0)",
        stroke_width=2,
        anchor="lt",
    )
    draw.text(
        (235, 266),
        f"{str(cookie.id).zfill(4)}",
        font=info_font,
        fill="rgb(244, 253, 139)",
        stroke_fill="rgb(0, 0, 0)",
        stroke_width=2,
        anchor="lt",
    )

    role_icon = Image.open(cookie.role_icon)
    role_icon = role_icon.resize((int(role_icon.width / 3), int(role_icon.height / 3)))
    image.alpha_composite(role_icon, (192, 318))
    draw.text(
        (235, 322),
        f"{cookie.type.value}",
        font=info_font,
        fill="rgb(255, 255, 255)",
        stroke_fill="rgb(0, 0, 0)",
        stroke_width=2,
        anchor="lt",
    )

    position = Image.open(cookie.position_icon)
    position = position.resize((int(position.width / 1.5), int(position.height / 1.5)))
    image.alpha_composite(position, (192, 376))
    position_color = {
        Position.FRONT: "rgb(205, 46, 49)",
        Position.MIDDLE: "rgb(236, 200, 54)",
        Position.REAR: "rgb(106, 204, 253)",
    }[cookie.position]
    draw.text(
        (235, 378),
        f"{cookie.position.value}",
        font=info_font,
        fill=position_color,
        stroke_fill="rgb(0, 0, 0)",
        stroke_width=2,
        anchor="lt",
    )

    image.save(fp)
    return fp


def order_to_image(order, bot_name):
    fp = order_path(order.cookies)

    if fp.exists():
        return fp

    front = [cookie for cookie in order.cookies if cookie.position == Position.FRONT]
    middle = [cookie for cookie in order.cookies if cookie.position == Position.MIDDLE]
    rear = [cookie for cookie in order.cookies if cookie.position == Position.REAR]

    front = [front[i : i + 10] for i in range(0, len(front), 10)]
    middle = [middle[i : i + 10] for i in range(0, len(middle), 10)]
    rear = [rear[i : i + 10] for i in range(0, len(rear), 10)]

    height = 125
    max_height = height
    for subset in (front, middle, rear):
        needed_height = len(subset) * 95 + (len(subset) + 1) * 10
        max_height += 100 + needed_height + 25
    max_height -= 15

    image = Image.new("RGBA", (1080, max_height), "rgb(3, 5, 9)")
    draw = ImageDraw.Draw(image)

    cloud = Image.open(MISC_PATH / "arena_cloud.png").resize((1096, 234)).rotate(180)
    image.paste(cloud, (-16, 0), cloud)

    trophy = Image.open(MISC_PATH / "trophy.png").resize((80, 80)).rotate(-20, expand=True)
    image.paste(trophy, (970, 5), trophy)

    font = ImageFont.truetype(str(TOPPING_PATH / "font.otf"), size=64)
    draw.text(
        (20, 10),
        "Cookie Comp Order:",
        font=font,
        fill="rgb(255, 255, 255)",
        stroke_fill="rgb(0, 0, 0)",
        stroke_width=3,
    )
    draw.text(
        (970, 10),
        f"[{order.filter.value.title()}]",
        font=font,
        fill="rgb(255, 255, 255)",
        stroke_fill="rgb(0, 0, 0)",
        stroke_width=3,
        anchor="ra",
    )

    signature = ImageFont.truetype(str(TOPPING_PATH / "font.otf"), size=18)
    now = datetime.now(tz=ZoneInfo("Asia/Seoul"))
    draw.text(
        (1060, 100),
        f"{now.strftime('%Y/%m/%d %X')} KST",
        font=signature,
        fill="rgb(255, 255, 255)",
        stroke_fill="rgb(0, 0, 0)",
        stroke_width=2,
        anchor="ra",
    )
    draw.text(
        (1060, 125),
        f"{bot_name}  [BOT]",
        font=signature,
        fill="rgb(255, 255, 255)",
        stroke_fill="rgb(0, 0, 0)",
        stroke_width=2,
        anchor="ra",
    )

    font = ImageFont.truetype(str(TOPPING_PATH / "font.otf"), size=48)

    for i, subset in enumerate((front, middle, rear)):
        needed_height = len(subset) * 95 + (len(subset) + 1) * 10

        # Tab
        draw.rounded_rectangle(
            ((10, height), (275, height + 100)),
            fill="rgb(35, 35, 37)",
            outline="rgb(50, 51, 53)",
            width=2,
            radius=20,
        )

        # Body
        draw.rounded_rectangle(
            ((10, height + 70), (1070, height + 100 + needed_height)),
            fill="rgb(35, 35, 37)",
            outline="rgb(50, 51, 53)",
            width=2,
            radius=10,
        )

        # Connection
        draw.rectangle(
            ((12, height + 50), (295, height + 130)),
            fill="rgb(35, 35, 37)",
        )

        # Gray outer line
        draw.chord(
            ((275, height + 30), (315, height + 70)),
            start=90,
            end=180,
            fill="rgb(3, 5, 9)",
            outline="rgb(50, 51, 53)",
            width=2,
        )

        # Arc cover fill
        draw.ellipse(
            ((277, height + 32), (313, height + 68)),
            fill="rgb(3, 5, 9)",
        )

        position, icon = POSITION[i]

        # Position label
        image.paste(icon, (22, height + 15), icon)
        draw.text(
            (178, height + 4),
            f"{position.value.title()}",
            font=font,
            fill="rgb(255, 255, 255)",
            stroke_fill="rgb(0, 0, 0)",
            stroke_width=2,
            anchor="ma",
        )

        line_height = height + 80
        for line in subset:
            for j, cookie in enumerate(line):
                icon = Image.open(cookie.card).resize((95, 95))
                image.paste(icon, (20 + 105 * j, line_height + 15), icon)
            line_height += 105

        height += 100 + needed_height + 25

    image.save(fp)
    return fp
