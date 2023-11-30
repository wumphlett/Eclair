import hashlib
from pathlib import Path
from typing import List

from topping_bot.util.const import LEADERBOARD_PATH, TMP_PATH


def leaderboard_path(requirements_fp: Path):
    file_hash = hashlib.sha1()
    with open(requirements_fp, "rb") as f:
        fb = f.read(1024)
        while len(fb) > 0:
            file_hash.update(fb)
            fb = f.read(1024)

    return LEADERBOARD_PATH / f"{file_hash.hexdigest()}.json"


def order_path(order: List):
    digest = "".join(cookie.name for cookie in order)
    str_hash = hashlib.sha1()
    str_hash.update(digest.encode("utf-8"))
    return TMP_PATH / f"{str_hash.hexdigest()}.png"


def camel_case_split(string):
    words = [[string[0]]]

    for c in string[1:]:
        if words[-1][-1].islower() and c.isupper():
            words.append(list(c))
        else:
            words[-1].append(c)

    return " ".join(["".join(word) for word in words])
