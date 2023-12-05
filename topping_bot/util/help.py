import inspect
from enum import Enum
from typing import Union

from discord.ext import commands
from discord.ext.commands import Cog, Group, HelpCommand, Range

from topping_bot.util.common import new_embed

ORDERING = {
    "Community": [
        "help",
        "about",
        "cd",
        "startcd",
        "gb",
        "gb hp",
        "gb trophy",
        "gb eff",
        "gb stats",
        "gb c",
        "gb c hp",
        "gb c trophy",
        "gb c eff",
        "mc",
        "treasure",
        "statue",
        "beacon",
        "relic",
        "powder",
        "meta",
        "arena",
        "order",
        "cookie",
        "cpuff",
        "prophet",
        "gacha",
        "gacha info",
        "gacha stats",
        "gacha pull",
        "gacha lb",
        "source",
        "coupons",
        "claim",
        "stopcoupons",
        "wipedata",
    ],
    "Cookies": [
        "tutorial",
        "optimize",
        "stop",
    ],
    "Inventory": [
        "inv",
        "inv add",
        "inv delete",
        "inv deletetopping",
        "updateinv",
        "appendinv",
        "count",
        "debug",
    ],
    "RequirementFiles": [
        "req",
        "req help",
        "req view",
        "req copy",
        "req upload",
        "req download",
        "req delete",
        "req def",
        "req def upload",
        "req def download",
        "req def delete",
    ],
    "Stats": [
        "combo",
        "basestat",
        "leaderboard",
    ],
    "Utility": [
        "status",
        "info",
        "todo",
        "ping",
        "kill",
        "restart",
        "commit",
        "resetcd",
        "nick",
        "test",
        "sync",
        "clear",
        "ann",
        "ann update",
        "ann secret",
        "vote",
        "status_msg",
        "rules",
    ],
    "Guilds": [
        "guilds",
    ],
    "COGS": ["Cookies", "Inventory", "RequirementFiles", "Stats", "Community", "Utility", "Guilds"],
}

PARAM_NAMES = {"cookie_filter": "filter"}

EXTRA_INFO = {
    "order": [
        "Arena View:",
        "[1][2][3][4][5]",
        "",
        "Layout View:",
        "[5][3][1]",
        "[4][2]",
    ],
    "arena": [
        "Enter the name of known cookies, else enter a '*'",
        "",
        "e.g. !arena hb ww * bbp *",
    ],
}


def command_signature(command):
    signature = f"!{command.qualified_name} "
    for param, info in command.params.items():
        name = display_name(info)
        if info.default is info.empty:
            signature += f"<{name}> "
        else:
            signature += f"[{name}] "
    return signature.strip()


def display_name(param):
    return PARAM_NAMES.get(param.name, param.name)


def sanitize_error(msg):
    for param, replacment in PARAM_NAMES.items():
        msg = msg.replace(param, replacment)
    msg = msg.replace('"', "'")
    return msg


def cog_order(cog):
    if cog is None:
        return float("inf")
    return ORDERING["COGS"].index(cog.qualified_name)


def command_order(cog: Union[Cog, str], command):
    if type(cog) == str:
        return ORDERING[cog].index(command.qualified_name)
    return ORDERING[cog.qualified_name].index(command.qualified_name)


def prefix(cmd):
    return "/" if cmd.qualified_name in ORDERING["Community"] else "!"


class BotHelpCommand(HelpCommand):
    def __init__(self, **options):
        self.brief = "Help info"
        super().__init__(**options)

    async def leaf_commands(self, cog, command):
        if isinstance(command, Group):
            for subcommand in await self.filter_commands(
                command.commands, sort=True, key=lambda x: command_order(cog, x)
            ):
                if command.name == "inv": # !inv is a valid command as well as group
                    yield command
                async for command in self.leaf_commands(cog, subcommand):
                    yield command
        else:
            yield command

    def command_not_found(self, string) -> str:
        return f"Command /{string} does not exist"

    def subcommand_not_found(self, command, string) -> str:
        return f"Command {prefix(command)}{command.qualified_name} {string} does not exist"

    async def send_bot_help(self, mapping):
        description = []
        mapping = sorted(list(mapping.items()), key=lambda x: cog_order(x[0]))

        for cog, commands in mapping:
            if not cog:
                continue

            commands = await self.filter_commands(commands, sort=True, key=lambda x: command_order(cog, x))
            if not commands:
                continue

            description += [f"{cog.qualified_name}:"]
            for command in commands:
                description += [
                    f"├ {command.qualified_name.ljust(12)} - {command.brief or 'View help'}"
                    async for command in self.leaf_commands(cog, command)
                ]
            description += [""]

        description += ["Use /help <command/group> for more info"]

        await self.context.reply(
            embed=await new_embed(title="Full Command Guide", description=description, thumbnail=False)
        )

    async def send_cog_help(self, cog):
        commands = await self.filter_commands(cog.get_commands(), sort=True, key=lambda x: command_order(cog, x))
        if not commands:
            return

        description = [f"{cog.description}", ""]
        description += [f"{cog.qualified_name}:"]
        for command in commands:
            description += [
                f"├ {command.qualified_name.ljust(12)} - {command.brief or 'View help'}"
                async for command in self.leaf_commands(cog, command)
            ]
        description += [""]
        description += ["Use /help <command> for more info"]

        await self.context.reply(
            embed=await new_embed(title=f"{cog.qualified_name} Command Guide", description=description, thumbnail=False)
        )

    async def send_group_help(self, group):
        commands = await self.filter_commands(group.commands, sort=True, key=lambda x: command_order(group.cog_name, x))
        if not commands:
            return

        description = [f"{group.description}", ""]
        description += [f"{prefix(group)}{group.qualified_name}:"]
        for command in commands:
            description += [
                f"├ {command.qualified_name.ljust(12)} - {command.brief or 'View help'}"
                async for command in self.leaf_commands(group.cog_name, command)
            ]
        description += [""]
        description += ["Use /help <command> for more info"]

        await self.context.reply(
            embed=await new_embed(
                title=f"{prefix(group)}{group.qualified_name} Command Guide", description=description, thumbnail=False
            )
        )

    async def send_command_help(self, command):
        for check in command.checks:
            if not await check(self.context):
                return

        description = [command.description, ""]

        if EXTRA_INFO.get(command.qualified_name):
            description += EXTRA_INFO[command.qualified_name] + [""]

        description += [command_signature(command), ""]

        if command.params:
            description += ["Params:"]

        for param, info in command.params.items():
            name = PARAM_NAMES.get(info.name, info.name)

            if type(info.converter) == Range:
                param_str = f"├ {name} ({info.converter.min} < {info.converter.annotation.__name__} < {info.converter.max}) - {info.description}"
            else:
                param_str = f"├ {name} ({info.converter.__name__}) - {info.description}"

            if inspect.isclass(info.converter) and issubclass(info.converter, Enum):
                param_str += f" [{','.join(option.value for option in info.converter)}]"
            elif info.default is not info.empty:
                param_str += f" [def: {info.default}]"
            description += [param_str]

        await self.context.reply(
            embed=await new_embed(
                title=f"{prefix(command)}{command.qualified_name} Command Guide",
                description=description,
                thumbnail=False,
            )
        )

    async def send_error_message(self, error):
        await self.context.reply(embed=await new_embed(title=f"Err: Help Command", description=error, thumbnail=False))
