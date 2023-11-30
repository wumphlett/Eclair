import shutil

from topping_bot.optimize.requirements import sanitize
from topping_bot.util.const import REQS_PATH, STATIC_PATH


def req_convert():
    for fp in REQS_PATH.iterdir():
        tmp = sanitize(fp)
        shutil.copy(tmp, fp)


def cookie_dump():
    for fp in (STATIC_PATH / "cookies").iterdir():
        if not fp.is_dir():
            cookie_id = fp.stem.split("_")[0].replace("cookie", "")
            cookie_dir = STATIC_PATH / "cookies" / cookie_id
            if cookie_dir.exists():
                shutil.move(fp, cookie_dir)
            else:
                fp.unlink()
