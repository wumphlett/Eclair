import asyncio
import traceback
from collections import defaultdict
from datetime import date, datetime, timedelta
import pytz
from decimal import Decimal
from enum import Enum
import math
from zoneinfo import ZoneInfo

from tqdm import tqdm

import discord
from discord import app_commands
from discord.ext import commands, tasks
from discord.ext.commands import Cog, CommandOnCooldown, cooldown, parameter
from discord.ext.commands import Range
from discord.ext.commands.cooldowns import BucketType
from discord.ext.commands.errors import BadArgument, RangeError, MissingRequiredArgument

from topping_bot.crk.candies import CANDIES, Candy, Type as CandyType
from topping_bot.crk.cookies import Cookie, Filter, Order, Position
from topping_bot.crk.gacha import Gacha
from topping_bot.crk.jams import JAMS, Jam, Type as JamType
from topping_bot.crk.stats import (
    cpuff_needed_crit,
    cookie_cd,
    guild_battle_boss_hp,
    guild_battle_boss_atk,
    guild_battle_boss_trophies,
    starting_cookie_cd,
)
from topping_bot.crk.relics import Relic, Type as RelicType
from topping_bot.crk.treasures import Treasure, Type as TreasureType
from topping_bot.util.autocomplete import Autocomplete
from topping_bot.util.chart import plot_eff, plot_hp, plot_trophy
from topping_bot.util.common import guild_only, new_embed, send_msg
from topping_bot.util.const import CONFIG, DATA_PATH, DEBUG, TMP_PATH
from topping_bot.util.cooldown import PULL_USER_1_PER_3S, PULL_MEMBER_5_PER_DAY, PULL_USER_50_PER_DAY
from topping_bot.util.help import command_signature, display_name, sanitize_error
from topping_bot.util.image import cookie_to_image, gacha_inv_to_image, gacha_pull_to_image, order_to_image
from topping_bot.ui.common import Paginator
from topping_bot.util.utility import camel_case_split


class Community(Cog, description="Helper commands available to all!"):
    def __init__(self, bot):
        self.bot = bot

    @Cog.listener()
    async def on_ready(self):
        self.save_cooldowns.start()
        self.reset_cooldowns.start()
        if not DEBUG:
            self.autoredeem.start()

    @Cog.listener()
    async def on_command_error(self, ctx, error):
        if type(error) in (BadArgument, RangeError, MissingRequiredArgument):
            signature = command_signature(ctx.command)
            description = [signature]

            param = display_name(ctx.current_parameter)
            start = signature.rfind(param) - 1
            end = start + len(param) + 1
            highlight = "".join("^" if start <= i <= end else " " for i in range(len(signature)))
            description.extend([highlight, "", sanitize_error(str(error))])

            if type(error) == BadArgument and issubclass(ctx.current_parameter.converter, Enum):
                description.append(
                    f"Must be one of [{','.join(option.value for option in ctx.current_parameter.converter)}]"
                )

            description.extend(["", f"Use '!help {ctx.command.qualified_name}' for more info"])

            await ctx.reply(
                embed=await new_embed(
                    title=f"/{ctx.command.qualified_name.upper()} Err: {camel_case_split(type(error).__name__)}",
                    description=description,
                    thumbnail=False,
                )
            )

    @cooldown(1, 1, BucketType.user)
    @commands.hybrid_command(brief="View about", description="View information about the bot")
    async def about(self, ctx):
        await send_msg(
            ctx,
            title=f"About the Bot",
            description=[
                "```",
                "This bot is meant to ease many aspects of CRK",
                f"\nFor issues or enhancements, please contact the admin",
                "```",
                "https://discord.gg/r6ZQFcRUK7",
                "https://eclair.community/add-bot",
            ],
            wrap=False,
            footer=f"admin: @{(await ctx.bot.application_info()).owner}",
        )

    @cooldown(1, 1, BucketType.user)
    @commands.hybrid_command(brief="Skill CD", description="Determine the cooldown length of a cookie's skill")
    @app_commands.describe(cookie="Name", topping="Cooldown Buff (%)", watch="Cooldown Buff (%)")
    @app_commands.autocomplete(cookie=Autocomplete(Cookie.names()).call)
    async def cd(
        self,
        ctx,
        cookie=parameter(description="name", converter=str),
        topping=parameter(description="cd buff", converter=Range[float, 0, 30]),
        watch=parameter(description="cd buff", converter=Range[float, 0, 25], default=25.0),
    ):
        search = cookie
        cookie = Cookie.get(cookie)

        if not cookie:
            await send_msg(
                ctx,
                title=f"Err: Cookie Not Found",
                description=f"Unable to find a cookie with the search string '{search}'",
            )
            return

        if cookie.name == "Oyster":
            num_soldiers = int((Decimal(topping + watch) / Decimal("18.1")).quantize(Decimal("0.01")) + 1)
            await send_msg(
                ctx,
                title=f"Your {cookie.name} Skill CD",
                description=[
                    "Number of Soldiers:",
                    f"├ {num_soldiers} Soldiers\n",
                    f"Skill: {cookie.cd}s | Topping: {topping}%* | Watch: {watch}%",
                    "*This includes the set bonus",
                ],
                thumbnail=False,
            )
        else:
            cd = cookie.cooldown
            adjusted_skill_cd = cookie_cd(cd, topping / 100, watch / 100)

            await send_msg(
                ctx,
                title=f"Your {cookie.name} Skill CD",
                description=[
                    "Time Between Skills:",
                    f"├ {adjusted_skill_cd:.2f}s\n",
                    f"Base: {cd}s | Topping: {topping}%* | Watch: {watch}%",
                    "*This includes the set bonus",
                ],
                thumbnail=False,
            )

    @cooldown(1, 1, BucketType.user)
    @commands.hybrid_command(brief="Start CD", description="Determine the starting cooldown of a cookie")
    @app_commands.describe(cookie="Name")
    @app_commands.autocomplete(cookie=Autocomplete(Cookie.names()).call)
    async def startcd(self, ctx, cookie=parameter(description="name", converter=str)):
        search = cookie
        cookie = Cookie.get(cookie)

        if not cookie:
            await send_msg(
                ctx,
                title=f"Err: Cookie Not Found",
                description=f"Unable to find a cookie with the search string '{search}'",
            )
            return

        base_cd = cookie.start_cd_override if cookie.start_cd_override is not None else cookie.cooldown
        description = []
        for skill_cd, start in starting_cookie_cd(base_cd, cookie.start_cd_override is not None):
            description += [f"{start}s Start:", f"├ CD >= {float(skill_cd):g}%*"]

        await send_msg(
            ctx,
            title=f"Your Needed CD Buff ({cookie.name})",
            description=description + ["", "*This includes the set bonus"],
            thumbnail=False,
        )

    @commands.hybrid_group(brief="GB commands", description="Commands for guild battle related info")
    async def gb(self, ctx):
        pass

    @gb.group(aliases=["chart"], brief="GB charts", description="Charts for guild battle related info")
    async def c(self, ctx):
        pass

    @cooldown(1, 1, BucketType.user)
    @gb.command(brief="GB HP", description="Determine the guild battle boss hp at a given lvl")
    @app_commands.describe(lvl="Guild Boss lvl (#)", lookahead="How many lvls ahead to include")
    async def hp(
        self,
        ctx,
        lvl=parameter(description="guild boss lvl", converter=Range[int, 1, 1000]),
        lookahead=parameter(description="size", converter=Range[int, 1, 40], default=10),
    ):
        hps = [guild_battle_boss_hp(lvl + inc) for inc in range(lookahead + 1)]

        await send_msg(
            ctx,
            title=f"GB Boss Health {lvl}-{lvl + lookahead}",
            description=["Boss Health:"] + [f"├ {lvl + inc} - {hp:,}" for inc, hp in enumerate(hps)],
        )

    @cooldown(1, 1, BucketType.user)
    @c.command(name="hp", brief="GB chart HP", description="Chart the guild battle boss hp")
    @app_commands.describe(lvl="Guild Boss lvl (#)", lookahead="How many lvls ahead to include")
    async def chart_hp(
        self,
        ctx,
        lvl=parameter(description="guild boss lvl", converter=Range[int, 1, 1000]),
        lookahead=parameter(description="size", converter=Range[int, 1, 200], default=100),
    ):
        hps = [(lvl + inc, guild_battle_boss_hp(lvl + inc)) for inc in range(lookahead + 1)]

        tmp = TMP_PATH / f"{ctx.message.author.id}.png"
        plot_hp(tmp, hps)

        await ctx.reply(
            embed=await new_embed(
                title=f"GB Boss Health {lvl}-{lvl + lookahead}",
                image=f"attachment://gb_chart.png",
                thumbnail=False,
            ),
            file=discord.File(tmp, filename="gb_chart.png"),
        )

        tmp.unlink(missing_ok=True)

    @cooldown(1, 1, BucketType.user)
    @gb.command(brief="GB trophies", description="Determine the guild battle trophies at a given lvl")
    @app_commands.describe(lvl="Guild Boss lvl (#)", lookahead="How many lvls ahead to include")
    async def trophy(
        self,
        ctx,
        lvl=parameter(description="guild boss lvl", converter=Range[int, 1, 1000]),
        lookahead=parameter(description="size", converter=Range[int, 1, 40], default=10),
    ):
        trophies = [guild_battle_boss_trophies(lvl + inc) for inc in range(lookahead + 1)]

        await send_msg(
            ctx,
            title=f"GB Boss Trophies {lvl}-{lvl + lookahead}",
            description=["Trophy Rewards:"] + [f"├ {lvl + inc} - {trophy:,}" for inc, trophy in enumerate(trophies)],
        )

    @cooldown(1, 1, BucketType.user)
    @c.command(name="trophy", brief="GB chart troph", description="Chart the guild battle boss trophies")
    @app_commands.describe(lvl="Guild Boss lvl (#)", lookahead="How many lvls ahead to include")
    async def chart_trophy(
        self,
        ctx,
        lvl=parameter(description="guild boss lvl", converter=Range[int, 1, 1000]),
        lookahead=parameter(description="size", converter=Range[int, 1, 200], default=100),
    ):
        trophies = [(lvl + inc, guild_battle_boss_trophies(lvl + inc)) for inc in range(lookahead + 1)]

        tmp = TMP_PATH / f"{ctx.message.author.id}.png"
        plot_trophy(tmp, trophies)

        await ctx.reply(
            embed=await new_embed(
                title=f"GB Boss Trophies {lvl}-{lvl + lookahead}",
                image=f"attachment://gb_chart.png",
                thumbnail=False,
            ),
            file=discord.File(tmp, filename="gb_chart.png"),
        )

        tmp.unlink(missing_ok=True)

    @cooldown(1, 1, BucketType.user)
    @gb.command(brief="GB efficiency", description="Determine the guild battle trophy/hp at a given lvl")
    @app_commands.describe(lvl="Guild Boss lvl (#)", lookahead="How many lvls ahead to include")
    async def eff(
        self,
        ctx,
        lvl=parameter(description="guild boss lvl", converter=Range[int, 1, 1000]),
        lookahead=parameter(description="size", converter=Range[int, 1, 40], default=10),
    ):
        efficiencies = [
            guild_battle_boss_trophies(lvl + inc) / guild_battle_boss_hp(lvl + inc) for inc in range(lookahead + 1)
        ]

        await send_msg(
            ctx,
            title=f"GB Boss Efficiency {lvl}-{lvl + lookahead}",
            description=["Trophy Per 1 HP (x 1mil):"]
            + [f"├ {lvl + inc} - {eff * 1_000_000:,.6f}" for inc, eff in enumerate(efficiencies)],
        )

    @cooldown(1, 1, BucketType.user)
    @c.command(name="eff", brief="GB chart eff", description="Chart the guild battle trophy/hp")
    @app_commands.describe(lvl="Guild Boss lvl (#)", lookahead="How many lvls ahead to include")
    async def chart_eff(
        self,
        ctx,
        lvl=parameter(description="guild boss lvl", converter=Range[int, 1, 1000]),
        lookahead=parameter(description="size", converter=Range[int, 1, 200], default=100),
    ):
        efficiencies = [
            (lvl + inc, guild_battle_boss_trophies(lvl + inc) / guild_battle_boss_hp(lvl + inc))
            for inc in range(lookahead + 1)
        ]

        tmp = TMP_PATH / f"{ctx.message.author.id}.png"
        plot_eff(tmp, efficiencies)

        await ctx.reply(
            embed=await new_embed(
                title=f"GB Boss Efficiency {lvl}-{lvl + lookahead}",
                image=f"attachment://gb_chart.png",
                thumbnail=False,
            ),
            file=discord.File(tmp, filename="gb_chart.png"),
        )

        tmp.unlink(missing_ok=True)

    @cooldown(1, 1, BucketType.user)
    @gb.command(brief="GB stats", description="Determine the guild battle stats at a given lvl")
    @app_commands.describe(lvl="Guild Boss lvl (#)", lookahead="How many lvls ahead to include")
    async def stats(
        self,
        ctx,
        lvl=parameter(description="guild boss lvl", converter=Range[int, 1, 34]),
        lookahead=parameter(description="size", converter=Range[int, 1, 40], default=10),
    ):
        atks = [guild_battle_boss_atk(lvl + inc) for inc in range(lookahead + 1)]

        description = [
            "Boss DEF:",
            "├ RVD - 78,000",
            "├ AoD - 1,500",
            "├ TLA - 1,500",
            "",
            "Boss ATK:",
        ]

        for inc, atk in enumerate(atks):
            if atk is None:
                continue
            description.append(f"├ lvl {lvl + inc}{'+' if lvl + inc == 34 else ''} - {atk:,}")

        await send_msg(
            ctx,
            title=f"GB Boss Stats {lvl}-{lvl + lookahead if lvl + lookahead < 34 else '34+'}",
            description=description,
        )

    @cooldown(1, 1, BucketType.user)
    @commands.hybrid_command(brief="Statue buff", description="Determine the statue buff at a given lvl")
    @app_commands.describe(lvl="Statue lvl (#)")
    async def statue(self, ctx, lvl=parameter(description="statue lvl", converter=Range[int, 1, 80])):
        await send_msg(
            ctx,
            title=f"Statue Buffs (lvl {lvl})",
            description=[
                "All Buffs:",
                f"├ ATK: {1 + (lvl - 1) * (8 / 79):.2f}%",
                f"├ DEF: {2.5 + (lvl - 1) * (5 / 79):.2f}%",
                f"├ HP:  {2 + (lvl - 1) * (6 / 79):.2f}%",
                f"├ Fountain: {1 + (lvl - 1) * (19 / 79):.1f}%",
                f"├ House: {1.5 + (lvl - 1) * (28.5 / 79):.1f}%",
                f"├ Tree Coins: {1 + (lvl - 1) * (19 / 79):.1f}%",
            ],
        )

    @cooldown(1, 1, BucketType.user)
    @commands.hybrid_command(brief="Beacon buff", description="Determine the beacon buff at a given lvl")
    @app_commands.describe(lvl="Beacon lvl (#)")
    async def beacon(self, ctx, lvl=parameter(description="beacon lvl", converter=Range[int, 1, 100])):
        await send_msg(
            ctx,
            title=f"Beacon Buffs (lvl {lvl})",
            description=[
                "All Buffs:",
                f"├ Cookies' ATK: {Decimal(3) + (lvl - 1) * Decimal('.1'):.1f}%",
                f"├ Cookies' DEF: {Decimal('8.7') + (lvl - 1) * Decimal('.1'):.1f}%",
                f"├ Cookies' HP:  {Decimal('8.4') + (lvl - 1) * Decimal('.1'):.1f}%",
            ],
        )

    @cooldown(1, 1, BucketType.user)
    @commands.hybrid_command(brief="Cookie info", description="View cookie info")
    @app_commands.describe(cookie="Name")
    @app_commands.autocomplete(cookie=Autocomplete(Cookie.names()).call)
    async def cookie(self, ctx, cookie=parameter(description="name", converter=str)):
        search = cookie
        cookie = Cookie.get(cookie)

        if not cookie:
            await send_msg(
                ctx,
                title=f"Err: Cookie Not Found",
                description=f"Unable to find a cookie with the search string '{search}'",
            )
            return

        gacha = Gacha.load_history(ctx.message.author.id)
        fp = cookie_to_image(cookie, gacha, ctx.message.author.id)

        image = discord.File(fp, filename=f"{cookie.name.lower().replace(' ', '')}.png")
        embed = await new_embed(
            image=f"attachment://{cookie.name.lower().replace(' ', '')}.png",
            footer=None if gacha.is_unlocked(pk=str(cookie.id)) else "Unlock with /gacha pull",
            thumbnail=False,
        )

        await ctx.reply(embed=embed, file=image)
        fp.unlink(missing_ok=True)

        # await send_msg(
        #     ctx,
        #     title=f"{cookie.name} Cookie",
        #     description=[
        #         f"rarity: {cookie.rarity.value}",
        #         f"type: {cookie.type.value}",
        #         f"position: {cookie.position.value}",
        #     ],
        #     thumbnail=cookie.card,
        # )

    @cooldown(1, 1, BucketType.user)
    @commands.hybrid_command(aliases=["t"], brief="Treasure info", description="View treasure info at a given lvl")
    @app_commands.describe(
        treasure="Name",
        lvl="Treasure lvl (#)",
        chance_up="If treasure is on Chance Up",
        start="Starting Treasure lvl (#)",
    )
    @app_commands.autocomplete(treasure=Autocomplete(TreasureType).call)
    async def treasure(
        self,
        ctx,
        treasure=parameter(description="name", converter=str),
        lvl=parameter(description="lvl", converter=Range[int, 1, 12]),
        chance_up=parameter(description="chance up", converter=bool, default=True),
        start=parameter(description="starting_lvl", converter=Range[int, 0, 11], default=0),
    ):
        treasure = Treasure.get(treasure)
        treasure.start_lvl = start
        treasure.lvl = lvl
        treasure.chance_up = chance_up

        description = ["Effects:"] + [f"├ {txt}: {value}" for txt, value in treasure.effects]

        description += [
            "",
            f"Pulls to lvl {lvl} ({treasure.req_count} cop{'y' if treasure.req_count == 1 else 'ies'})*:",
            f"├ 50% of ppl need <= {treasure.upgrade(0.5)} pulls",
            f"├ 90% of ppl need <= {treasure.upgrade(0.9)} pulls",
            f"├ 95% of ppl need <= {treasure.upgrade(0.95)} pulls",
            "",
            f"*Assumes {treasure.chance * 100:.3f}% chance",
        ]

        await send_msg(ctx, title=f"{treasure.treasure.value} (lvl {lvl})", description=description, thumbnail=False)

    @cooldown(1, 1, BucketType.user)
    @commands.hybrid_command(brief="Relic info", description="View relic info at a given lvl")
    @app_commands.describe(relic="Name", lvl="Relic lvl (#)")
    @app_commands.autocomplete(relic=Autocomplete(RelicType).call)
    async def relic(
        self,
        ctx,
        relic=parameter(description="name", converter=str),
        lvl=parameter(description="lvl", converter=Range[int, 1, 20]),
    ):
        relic = Relic.get(relic)
        relic.lvl = lvl

        description = ["Effects:"] + [f"├ {txt}: {value}" for txt, value in relic.effects]

        await send_msg(ctx, title=f"{relic.relic.value} (lvl {lvl})", description=description, thumbnail=False)

    @cooldown(1, 1, BucketType.user)
    @commands.hybrid_command(brief="Candy info", description="View magic candy info at a given lvl")
    @app_commands.describe(cookie="Name", lvl="Magic Candy lvl (#)", start="Starting Magic Candy lvl (#)")
    @app_commands.autocomplete(cookie=Autocomplete(CandyType).call)
    async def mc(
        self,
        ctx,
        cookie=parameter(description="name", converter=str),
        lvl=parameter(description="lvl", converter=Range[int, 1, 30]),
        start=parameter(description="starting_lvl", converter=Range[int, 0, 29], default=0),
    ):
        if lvl <= start:
            return

        search = cookie
        cookie = Cookie.get(cookie)
        if not cookie or cookie.name not in CANDIES:
            await send_msg(
                ctx,
                title=f"Err: Magic Candy Not Found",
                description=f"Unable to find a magic candy with the search string '{search}'",
            )
            return

        candy = Candy(cookie, lvl)
        description = ["Effects:"] + [f"├ {txt}: {value}" for txt, value in candy.effects]

        if candy.enchantments:
            description += ["", "Enchantments:"] + [f"├ {txt}: {value}" for txt, value in candy.enchantments]

        description += [
            "",
            f"Upgrade Costs ({lvl-1} -> {lvl}):",
            f"├ {candy.soul()[1]} {candy.soul()[0]}",
            f"├ {candy.crystal()} Sugar Crystals",
            f"├ {candy.ingredient()} Resonant Ing.",
        ]

        description += [
            "",
            f"Upgrade Costs ({start} -> {lvl}):",
        ]

        soul_cost = defaultdict(int)
        for lvl in range(start + 1, lvl + 1):
            soul_cost[candy.soul(lvl)[0]] += candy.soul(lvl)[1]

        for soul_type in ("Common", "Rare", "Epic", "Legendary"):
            if soul_cost[f"{soul_type} Soul Ess."]:
                description += [f"├ {soul_cost[f'{soul_type} Soul Ess.']} {soul_type} Soul Ess."]

        description += [
            f"├ {sum(candy.crystal(lvl) for lvl in range(start + 1, lvl+1))} Sugar Crystals",
            f"├ {sum(candy.ingredient(lvl) for lvl in range(start + 1, lvl+1))} Resonant Ing.",
        ]

        await send_msg(
            ctx, title=f"{candy.candy.value} Magic Candy (lvl {lvl})", description=description, thumbnail=False
        )

    @cooldown(1, 1, BucketType.user)
    @commands.hybrid_command(brief="Jam info", description="View crystal jam info at a given lvl")
    @app_commands.describe(cookie="Name", lvl="Crystal Jam lvl (#)", start="Starting Crystal Jam lvl (#)")
    @app_commands.autocomplete(cookie=Autocomplete(JamType).call)
    async def cj(
        self,
        ctx,
        cookie=parameter(description="name", converter=str),
        lvl=parameter(description="lvl", converter=Range[int, 1, 30]),
        start=parameter(description="starting_lvl", converter=Range[int, 0, 29], default=0),
    ):
        if lvl <= start:
            return

        search = cookie
        cookie = Cookie.get(cookie)
        if not cookie or cookie.name not in JAMS:
            await send_msg(
                ctx,
                title=f"Err: Crystal Jam Not Found",
                description=f"Unable to find a crystal jam with the search string '{search}'",
            )
            return

        jam = Jam(cookie, lvl)
        description = ["Effects:"] + [f"├ {txt}: {value}" for txt, value in jam.effects]

        if jam.enchantments:
            description += ["", "Enchantments:"] + [f"├ {txt}: {value}" for txt, value in jam.enchantments]

        description += ["", "Ascension Buffs:"] + [f"├ {txt}: {value}" for txt, value in jam.ascension_buffs]

        description += [
            "",
            f"Upgrade Costs ({lvl - 1} -> {lvl}):",
            f"├ {jam.soul()[1]} {jam.soul()[0]}",
            f"├ {jam.crystal()} Sugar Crystals",
            f"├ {jam.ingredient()} Resonant Ing.",
        ]

        description += [
            "",
            f"Upgrade Costs ({start} -> {lvl}):",
        ]

        soul_cost = defaultdict(int)
        for lvl in range(start + 1, lvl + 1):
            soul_cost[jam.soul(lvl)[0]] += jam.soul(lvl)[1]

        for soul_type in ("Common", "Rare", "Epic", "Legendary"):
            if soul_cost[f"{soul_type} Soul Ess."]:
                description += [f"├ {soul_cost[f'{soul_type} Soul Ess.']} {soul_type} Soul Ess."]

        description += [
            f"├ {sum(jam.crystal(lvl) for lvl in range(start + 1, lvl + 1))} Sugar Crystals",
            f"├ {sum(jam.ingredient(lvl) for lvl in range(start + 1, lvl + 1))} Resonant Ing.",
        ]

        await send_msg(ctx, title=f"{jam.jam.value} Crystal Jam (lvl {lvl})", description=description, thumbnail=False)

    @cooldown(1, 1, BucketType.user)
    @commands.hybrid_command(brief="Powder cost", description="View powder cost to upgrade a cookie")
    @app_commands.describe(start="Starting Cookie lvl (#)", end="Ending Cookie lvl (#)")
    async def powder(
        self,
        ctx,
        start=parameter(description="starting_lvl", converter=Range[int, 1, 75], default=1),
        end=parameter(description="ending_lvl", converter=Range[int, 1, 75], default=75),
    ):
        if end <= start:
            return

        description = [
            f"Upgrade Costs:",
        ]

        powder_cost = defaultdict(int)
        for lvl in range(start + 1, end + 1):
            powder_cost[Cookie.powder(lvl)[0]] += Cookie.powder(lvl)[1]

        for powder_type in ("", "Refined", "Pristine"):
            if powder_cost[f"{powder_type} Powder"]:
                description += [
                    f"├ {powder_cost[f'{powder_type} Powder']} {powder_type}{' ' if powder_type else ''}Powder"
                ]

        await send_msg(
            ctx, title=f"Cookie Powder Upgrade Costs ({start} -> {end})", description=description, thumbnail=False
        )

    @cooldown(1, 1, BucketType.user)
    @commands.hybrid_command(brief="Cookie order", description="View the current cookie order")
    @app_commands.describe(cookie_filter="List Filter")
    @app_commands.rename(cookie_filter="filter")
    async def order(
        self, ctx, cookie_filter=parameter(converter=Filter, default=Filter.EPIC_PLUS, description="list filter")
    ):
        order = Order(cookie_filter)
        image = order_to_image(order, self.bot.user)

        image = discord.File(image, filename=f"{order.filter.value.replace('+', '')}.png")
        embed = await new_embed(
            title=f"__**{order.filter.value.title()} Cookie Order**__",
            image=f"attachment://{order.filter.value.replace('+', '')}.png",
            thumbnail=False,
        )

        await ctx.reply(embed=embed, file=image)

    @cooldown(1, 1, BucketType.user)
    @commands.hybrid_command(brief="Arena order", description="Determine the hidden arena cookies")
    @app_commands.describe(
        c1="Name of Cookie in Position #1",
        c2="Name of Cookie in Position #2",
        c3="Name of Cookie in Position #3",
        c4="Name of Cookie in Position #4",
        c5="Name of Cookie in Position #5",
        cookie_filter="List Filter",
    )
    @app_commands.rename(cookie_filter="filter")
    @app_commands.autocomplete(
        c1=Autocomplete(Cookie.names() + ["*"]).call,
        c2=Autocomplete(Cookie.names() + ["*"]).call,
        c3=Autocomplete(Cookie.names() + ["*"]).call,
        c4=Autocomplete(Cookie.names() + ["*"]).call,
        c5=Autocomplete(Cookie.names() + ["*"]).call,
    )
    async def arena(
        self,
        ctx,
        c1=parameter(description="cookie #1"),
        c2=parameter(description="cookie #2"),
        c3=parameter(description="cookie #3"),
        c4=parameter(description="cookie #4"),
        c5=parameter(description="cookie #5"),
        cookie_filter=parameter(converter=Filter, default=Filter.EPIC_PLUS, description="list filter"),
    ):
        order = Order(cookie_filter)

        try:
            solution = order.solve(c1, c2, c3, c4, c5)
        except Exception as exc:
            await send_msg(ctx, title="Err: Improper Order", description=[f"{exc}"])
            return

        description = [""]
        for i, cookie in enumerate(solution):
            if type(cookie) != list:
                description.append(f"**{i + 1}. {cookie.name.upper()}**")
            elif len(cookie) == 1:
                description.append(f"**{i + 1}. ☆ {cookie[0].name.upper()}**")
            else:
                description.extend([f"**{i + 1}. ☆ WILDCARD**", "```"])

                for position in (Position.FRONT, Position.MIDDLE, Position.REAR):
                    cookies = [option for option in cookie if option.position == position]

                    if not cookies:
                        continue

                    description.append(f"{position.value}:")
                    for option in cookies:
                        description.append(f"├ {option.name}")

                description.append("```")

        await send_msg(
            ctx,
            title=f"__**Cookie Arena Order [{cookie_filter.value.title()}]**__",
            description=description,
            wrap=False,
        )

    @cooldown(1, 1, BucketType.user)
    @commands.hybrid_command(brief="CPuff CRIT%", description="Determine the needed CRIT% for Cream Puff")
    @app_commands.describe(lvl="Cream Puff Magic Candy lvl (#)", added_crit="CRIT% Buff from Allies")
    async def cpuff(
        self,
        ctx,
        lvl=parameter(description="cpuff mc lvl", converter=Range[int, 1, 30]),
        added_crit=parameter(description="ally crit% buff", converter=float, default=43.0),
    ):
        guaranteed_success, capped_cdmg_buff, added = cpuff_needed_crit(lvl, Decimal(added_crit))

        if capped_cdmg_buff is None:
            await send_msg(
                ctx,
                title="Your Needed CPuff CRIT% Buff",
                description=[
                    "Needed CRIT%:",
                    f"├ {guaranteed_success:.1f}%*",
                    f"{guaranteed_success:.1f}% - Guaranteed Success",
                    "",
                    "Added CRIT%:",
                    f"├ {added:.1f}%",
                    "",
                    "Ally CRIT% Buff:",
                    f"├ {added_crit:.1f}%",
                    "",
                    "*This includes the set bonus",
                ],
                thumbnail=False,
            )
        else:
            await send_msg(
                ctx,
                title="Your Needed CPuff CRIT% Buff",
                description=[
                    "Needed CRIT%:",
                    f"├ {max(guaranteed_success, capped_cdmg_buff):.1f}%*",
                    f"{guaranteed_success:.1f}% - Guaranteed Success",
                    f"{capped_cdmg_buff:.1f}% - Capped CRIT DMG Buff",
                    "",
                    "Added CRIT%:",
                    f"├ {added:.1f}%",
                    "",
                    "Ally CRIT% Buff:",
                    f"├ {added_crit:.1f}%",
                    "",
                    "*This includes the set bonus",
                ],
                thumbnail=False,
            )

    @cooldown(1, 1, BucketType.user)
    @commands.hybrid_command(brief="Prophet CRIT%", description="Determine the needed CRIT% to lock prophecies")
    async def prophet(self, ctx):
        await send_msg(
            ctx,
            title=f"Your Needed Prophet CRIT% Buff",
            description=[
                "Prophecy Lock Requirements:",
                "├ Fire     XX.95 - XX.14",
                "├ Squid    XX.15 - XX.34",
                "├ Mango    XX.35 - XX.54",
                "├ Thunder  XX.55 - XX.74",
                "├ Water    XX.75 - XX.84",
                "├ Ice      XX.85 - XX.94",
                "├ Repeat   XX.95 - ∞",
                "",
                "CRIT% to two decimal places is",
                "viewable in the 'Toppings' screen",
                "",
                "Subtract CRIT% shown by 13%",
                "e.g. 23.47% -> 10.47% (Mango)",
            ],
            thumbnail=False,
        )

    @commands.hybrid_group(brief="Gacha commands", description="Commands to run the gacha")
    async def gacha(self, ctx):
        pass

    @cooldown(1, 1, BucketType.user)
    @gacha.command(brief="Gacha info", description="Info about the simulated gacha")
    async def info(self, ctx):
        await send_msg(
            ctx,
            title=f"Simulated Gacha Info",
            description=[
                "The /gacha command simulates the Featured Cookie Gacha*",
                "",
                "Meaning:",
                "1. A cookie is guaranteed every 10 pulls",
                "2. An epic cookie is guaranteed every 100 pulls",
                "",
                "Odds:",
                "├ 2.536% - Ancient + Legendary + Dragon",
                "├ 19.28% - Super Epic + Epic*",
                "├ 36.932% - Rare",
                "├ 40.752% - Common",
                "├ 0.5% - Special*",
                "",
                "*The Special & Cream Puff chance deviates from in-game",
                "*Featured Epic cookies have a chance up",
            ],
            thumbnail=False,
        )

    @cooldown(1, 3, BucketType.member)
    @cooldown(5, 86399, BucketType.member)
    @cooldown(3, 86400, BucketType.user)
    @gacha.command(checks=[guild_only], brief="Gacha pull", description="10 pull the simulated gacha")
    async def pull(self, ctx):
        async with ctx.typing():
            if not DEBUG and (not ctx.guild or ctx.guild.member_count < 10):
                await send_msg(
                    ctx,
                    title="Err: Gacha Server Size",
                    description=[
                        "'/gacha pull' must be run in a server with at least 10 members",
                        "",
                        "Feel free to make pulls in a different server!",
                    ],
                )
                return
            if not ctx.guild.created_at + timedelta(days=14) < datetime.now(tz=pytz.UTC):
                await send_msg(
                    ctx,
                    title="Err: Gacha Server Age",
                    description=[
                        "'/gacha pull' must be run in a server at least 14 days old",
                        "",
                        "Feel free to make pulls in a different server!",
                    ],
                )
                return

            gacha = Gacha.load_history(ctx.message.author.id)

            pull_days = (
                datetime.now(tz=ZoneInfo("Asia/Seoul"))
                - datetime(year=2023, month=4, day=19, tzinfo=ZoneInfo("Asia/Seoul"))
            ).days
            max_pulls = pull_days * 40 * 10
            if not DEBUG and gacha.pulls >= max_pulls:
                await send_msg(
                    ctx,
                    title="Gacha Limit Reached!",
                    description=[
                        f"You have the max amount of pulls possible in {pull_days} days",
                        "",
                        "Please come back tomorrow to make more pulls!",
                    ],
                )
                return

            if not DEBUG:
                PULL_USER_1_PER_3S.update_rate_limit(ctx.message.author.id)
                PULL_MEMBER_5_PER_DAY.update_rate_limit((ctx.guild.id, ctx.message.author.id))
                PULL_USER_50_PER_DAY.update_rate_limit(ctx.message.author.id)

            fp = gacha_pull_to_image(gacha.ten_pull(), gacha, ctx.message.author.id)
            gacha.save_history(ctx.message.author.id)

            image = discord.File(fp, filename=f"gacha-{ctx.message.author.id}.png")
            embed = await new_embed(
                image=f"attachment://gacha-{ctx.message.author.id}.png",
                footer="Use /gacha stats & /gacha lb",
                thumbnail=False,
            )

            await asyncio.sleep(2)

            await ctx.reply(embed=embed, file=image)
        fp.unlink(missing_ok=True)

    @pull.error
    async def on_pull_error(self, ctx, error):
        if type(error) == CommandOnCooldown:
            today = datetime.now(tz=ZoneInfo("Asia/Seoul"))
            wait = timedelta(hours=24) - timedelta(hours=today.hour, minutes=today.minute, seconds=today.second)
            if error.cooldown.rate == 1:
                await send_msg(
                    ctx,
                    title="Gacha Slowdown!",
                    description=[
                        "Slowdown! Wait until your current pull is done!",
                    ],
                )
            elif error.cooldown.rate == 5:
                await send_msg(
                    ctx,
                    title="Gacha Limit Reached!",
                    description=[
                        "You've reached your five pulls daily limit in this server",
                        f"Cooldown up in {wait.seconds}s",
                        "",
                        "Feel free to make more pulls in a different server!",
                    ],
                )
            else:
                await send_msg(
                    ctx,
                    title="Gacha Limit Reached!",
                    description=[
                        "You've reached your 50 pulls daily limit",
                        f"Cooldown up in {wait.seconds}s",
                        "",
                        "Come back tomorrow to make more pulls!",
                    ],
                )

    @cooldown(1, 30, BucketType.user)
    @gacha.command(brief="Gacha stats", description="Stats about your simulated gacha")
    async def stats(self, ctx):
        async with ctx.typing():
            msgs = []
            embed_images = []
            channel = self.bot.get_channel(CONFIG["community"]["img-dump"])

            gacha = Gacha.load_history(ctx.message.author.id)
            images = gacha_inv_to_image(gacha, ctx.message.author.id)

            for subset in (images[i : i + 10] for i in range(0, len(images), 10)):
                msg = await channel.send(files=[discord.File(image, filename=image.name) for image in subset])
                embed_images.extend([attachment.url for attachment in msg.attachments])
                msgs.append(msg)

        await Paginator().start(
            ctx,
            pages=[
                await new_embed(title="**Your Cookie Inventory**", image=image, thumbnail=False)
                for image in embed_images
            ],
            end_screen=await new_embed(
                title=f"**Your Cookie Inventory**",
                description=[
                    "Gacha Statistics:",
                    f"Pulls - {gacha.pulls}",
                    f"Since Cookie - {gacha.since_last_cookie}",
                    f"Since Epic - {gacha.since_last_epic}",
                    f"Mileage - {gacha.mileage()}",
                ],
                footer="Update with /gacha stats",
                thumbnail=False,
            ),
            messages=msgs,
        )

        for fp in images:
            fp.unlink(missing_ok=True)

    @cooldown(1, 30, BucketType.user)
    @gacha.command(checks=[guild_only], brief="Gacha lb", description="Leaderboard for the simulated gacha")
    async def lb(self, ctx):
        async with ctx.typing():
            members = [
                fp
                for fp in DATA_PATH.iterdir()
                if fp.stem.isdigit() and fp.suffix == ".json" and ctx.guild.get_member(int(fp.stem))
            ]
            entries = []
            calling_entry = tuple()
            for member in members:
                gacha = Gacha.load_history(member.stem)
                member = ctx.guild.get_member(int(member.stem))
                name = member.nick if member.nick else member.name
                entries.append((name, gacha.pulls // 10, gacha.mileage(), member.id))
                if member.id == ctx.author.id:
                    calling_entry = (name, gacha.pulls // 10, gacha.mileage(), member.id)
            entries.sort(key=lambda x: x[2], reverse=True)

            items = [
                f"{'>>> ' if entry[3] == ctx.author.id else ''}{idx+1}. {entry[2]:,} ({entry[1]:,}) - {entry[0][:24]}"
                for idx, entry in enumerate(entries)
            ]

            pages = []
            for i, group in enumerate(items[i : i + 25] for i in range(0, len(items), 25)):
                pages.append(
                    await new_embed(
                        title=f"__**Gacha Leaderboard**__",
                        description=["Mileage (pulls):"] + group,
                        thumbnail=False,
                    )
                )

        await Paginator().start(
            ctx,
            pages=pages,
            end_screen=await new_embed(
                title=f"__**Gacha Leaderboard**__",
                description=["Mileage (pulls):"]
                + [f"{calling_entry[2]:,} ({calling_entry[1]:,}) - {calling_entry[0][:24]}"],
                footer="Update with /gacha lb",
                thumbnail=False,
            ),
        )

    @cooldown(1, 1, BucketType.user)
    @commands.hybrid_command(brief="Good sources", description="View valuable sources for info & guides")
    async def source(self, ctx):
        await send_msg(
            ctx,
            title=f"All Sources",
            description=[
                "__**Guides:**__",
                "",
                "**ND러너** : https://www.youtube.com/@ndlover7",
                "```",
                "Offers new update analysis, arena guides, and guild battle guides",
                "```",
                "**SunnyLiu** : https://www.youtube.com/@SunnyLiu",
                "```",
                "Offers story mode guides and cookie rankings",
                "```",
                "**PonPonLin蹦蹦林** : https://www.youtube.com/@ponponlin",
                "```",
                "Offers new update analysis, arena guides, and guild battle guides",
                "```",
                "**1타법사 (1Wizard)** : https://www.youtube.com/@1Wizard",
                "```",
                "Offers cookie analysis and arena guides",
                "```",
                "**누리머 Noorimer** : https://www.youtube.com/@noorimer",
                "```",
                "Offers cookie analysis and arena guides",
                "```",
                "**Yubi!** : https://www.youtube.com/@Yubituber",
                "```",
                "Offers arena, guild battle, and alliance guides",
                "```",
                "**Lunie Anami** : https://www.youtube.com/@LunieAnami",
                "```",
                "Offers story mode and alliance guides",
                "```",
                "**Dreakt** : https://www.youtube.com/@dreaktcrk",
                "```",
                "Offers arena guides",
                "```",
                "**Timotsuki Gaming** : https://www.youtube.com/@timotsuki0806",
                "```",
                "Offers story mode, tower of chaos, and event guides",
                "```",
                "",
                "__**Data Collection:**__",
                "",
                "**The Eclair Bot!** : <@985098992360771585>" "```",
                "Contains information and calculations",
                "Run /help to view the list of commands offered",
                "```",
                "**The Loser Squad Spreadsheet** : https://tinyurl.com/lsquad-data",
                "```",
                "Lots of raw data collected over the years",
                "*now closed rip ;-;*",
                "```",
            ],
            wrap=False,
            thumbnail=False,
            footer=f"To request updates, msg {(await ctx.bot.application_info()).owner}",
        )

    @tasks.loop(minutes=5)
    async def save_cooldowns(self):
        PULL_USER_1_PER_3S.save()
        PULL_MEMBER_5_PER_DAY.save()
        PULL_USER_50_PER_DAY.save()

    @save_cooldowns.before_loop
    async def before_save_cooldowns(self):
        await self.bot.wait_until_ready()

    @tasks.loop(hours=24)
    async def reset_cooldowns(self):
        PULL_USER_1_PER_3S.reset()
        PULL_MEMBER_5_PER_DAY.reset()
        PULL_USER_50_PER_DAY.reset()

    @reset_cooldowns.before_loop
    async def before_reset_cooldowns(self):
        await self.bot.wait_until_ready()
        today = datetime.now(tz=ZoneInfo("Asia/Seoul"))
        wait = timedelta(hours=24) - timedelta(hours=today.hour, minutes=today.minute, seconds=today.second)
        await asyncio.sleep(wait.seconds)

    @app_commands.command(description="View help information for the bot")
    async def help(self, interaction, command: str = None):
        ctx = await self.bot.get_context(interaction)
        self.bot.help_command.context = ctx
        await self.bot.help_command.command_callback(ctx, command=command)
