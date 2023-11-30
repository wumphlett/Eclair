import math
from decimal import Decimal
from pathlib import Path

from discord.ext import commands
from discord.ext.commands import Cog, parameter

from topping_bot.crk.stats import cookie_base_atk
from topping_bot.optimize.leaderboard import leaderboard
from topping_bot.util.common import approved_guild_ctx, approved_guild_only, filter_requirements_files, send_msg
from topping_bot.ui.common import RequirementView
from topping_bot.util.utility import leaderboard_path


class Stats(Cog, description="View build related statistics"):
    def __init__(self, bot):
        self.bot = bot

    def cog_check(self, ctx):
        return approved_guild_only(ctx)

    @commands.command(brief="N choose 5", description="Calculate the number of possible combos")
    async def combo(self, ctx, topping_num=parameter(description="inv size")):
        topping_num = int(topping_num.replace(",", ""))
        await send_msg(
            ctx,
            title="Number of Possible Combos",
            description=[
                f"Given {topping_num} toppings",
                f"├ {math.comb(topping_num, 5):,}",
                "possible combinations exist",
            ],
        )

    @commands.command(brief="Base STAT buff", description="Determine your base STAT% buff")
    async def basestat(
        self,
        ctx,
        before=parameter(description="before diff%", converter=int),
        after=parameter(description="after diff%", converter=int),
        diff=parameter(description="difference", converter=Decimal, default=9),
    ):
        await send_msg(
            ctx,
            title="Your Base STAT% Buff",
            description=[
                "Base STAT%:",
                f"├ {cookie_base_atk(before, after, diff / Decimal(100)) * 100:.2f}",
                "",
                "If the STAT in question is ATK:",
                "Typical range across all cookies is 25%-65%",
                "The higher the base ATK% buff, the less effective ATK toppings are",
            ],
        )

    @commands.command(brief="Leaderboard", description="View leaderboard")
    async def leaderboard(self, ctx):
        options = await filter_requirements_files(ctx, include_personal=False)

        reqs_view = RequirementView()
        await reqs_view.start(ctx, options, "What team would you like view the leaderboard of?")

        timeout = await reqs_view.wait()
        if timeout or not reqs_view.result:
            return

        requirements_fp = Path(reqs_view.result)
        leaderboard_fp = leaderboard_path(requirements_fp)

        if not leaderboard_fp.exists():
            await send_msg(
                ctx,
                title="Err: No Leaderboard",
                description=[
                    "No leaderboard exists yet for this file",
                    "Please use !optimize to add yourself",
                ],
            )
            return

        description = []
        for idx, (member, score) in enumerate(leaderboard(requirements_fp, leaderboard_fp)):
            if ctx.guild:
                member = await ctx.guild.fetch_member(member)
                name = member.nick if member.nick else member.name
            else:
                name = (await self.bot.fetch_user(member)).name
            description.append(f"{idx + 1}. {name[:10]}: {score:,}")

        name = requirements_fp.stem
        guild = approved_guild_ctx(ctx)
        name = guild.sanitize(name, ctx.message.author.id)

        await send_msg(
            ctx,
            title=f"{name} Leaderboard",
            description=description,
            thumbnail=False,
        )
