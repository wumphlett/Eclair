import os
from pathlib import Path

import yaml
from dotenv import load_dotenv

load_dotenv()

STATIC_PATH = Path("./static")
DEBUG_PATH = Path("./debug")
TMP_PATH = Path("./tmp")
DATA_PATH = Path("./data")
INFO_PATH = Path("./info")
GUILD_PATH = Path("./guilds")
REQS_PATH = Path("./reqs")
LEADERBOARD_PATH = Path("./leaderboard")

TMP_PATH.mkdir(exist_ok=True)
DATA_PATH.mkdir(exist_ok=True)
DEBUG_PATH.mkdir(exist_ok=True)
LEADERBOARD_PATH.mkdir(exist_ok=True)

DEBUG = os.getenv("DEBUG_BOT")

CONFIG_FILE = Path("./config.yaml")
with open(CONFIG_FILE, encoding="utf-8") as f:
    CONFIG = yaml.safe_load(f)

ECLAIR_GREEN = (132, 182, 119)
