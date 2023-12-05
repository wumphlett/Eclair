from collections import defaultdict

import yaml

from discord import Color

from topping_bot.util.const import CONFIG, GUILD_PATH


GUILD_INFO = GUILD_PATH / "guilds.yaml"
SUBSCRIBED_SERVERS = GUILD_PATH / "servers.txt"
COLORS = {
    "pure-vanilla": Color.from_str("#f1efbe"),
    "hollyberry": Color.magenta(),
    "dark-cacao": Color.purple(),
    "arena": Color.blue(),
    "special": Color.orange(),
}


class Guild:
    supported = []
    optimizers = []
    subscribed_servers = []
    tracked_servers = defaultdict(set)

    def __init__(self, group, **kwargs):
        self.name = kwargs["name"]
        self.server = kwargs["server"]
        self.role = kwargs["role"]
        self.channels = kwargs.get("channels", [])
        self.mod = kwargs.get("mod", CONFIG["optimizer"]["default-mod"])
        self.emoji = kwargs["emoji"]
        self.icon = kwargs.get("icon")
        self.rank = kwargs.get("rank")
        self.is_optimizer = kwargs["optimizer"]
        self.is_special = group == "special"
        self.group = group
        self.color = COLORS.get(group)

    def __repr__(self):
        return self.name

    def __hash__(self):
        return hash(self.name)

    @property
    def fp(self):
        return self.name.lower()

    def sanitize(self, title, author_id):
        for target, sub in [(f"{self.fp}-", ""), (f"{author_id}-", ""), ("-", " "), ("_", " ")]:
            title = title.replace(target, sub)
        return title.title()

    def choose_emoji(self, fp: str):
        return self.emoji if fp.startswith(f"{self.fp}-") else "👀"

    @classmethod
    def update(cls):
        Guild.supported = Guild.load_supported()
        Guild.optimizers = Guild.load_optimizers()
        Guild.subscribed_servers = Guild.load_subscribed_servers()

        new_tracked_servers = defaultdict(set)
        for guild in Guild.supported:
            if not guild.is_special:
                new_tracked_servers[guild.server].add(guild)
        Guild.tracked_servers = new_tracked_servers

    @classmethod
    def load_supported(cls):
        with open(GUILD_INFO, encoding="utf-8") as f:
            guild_info = yaml.safe_load(f)

        guilds = []
        for group_name, guild_group in guild_info.items():
            for guild in guild_group:
                guilds.append(cls(group_name, **guild))

        return guilds

    @classmethod
    def load_optimizers(cls):
        return [guild for guild in cls.supported if guild.is_optimizer]

    @classmethod
    def load_subscribed_servers(cls):
        if not SUBSCRIBED_SERVERS.exists():
            return []
        with open(SUBSCRIBED_SERVERS) as f:
            return [int(server.strip()) for server in f.readlines() if server.strip()]

    @classmethod
    def load_subscribed_server_info(cls, server: int):
        server_fp = GUILD_PATH / f"{server}.yaml"
        with open(server_fp) as f:
            return yaml.safe_load(f)

    @classmethod
    def dump_subscribed_servers(cls):
        with open(SUBSCRIBED_SERVERS, "w") as f:
            f.writelines((f"{server}\n" for server in cls.subscribed_servers))
