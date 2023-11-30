import os
import subprocess
import sys
import traceback
from datetime import datetime

from discord import Game
from discord.ext import commands
from discord.ext.commands import Cog
from tqdm import tqdm

from topping_bot.crk.cookies import Cookie
from topping_bot.crk.gacha import Gacha
from topping_bot.util.common import admin_only, approved_guild_only, new_embed, send_msg
from topping_bot.util.const import CONFIG, DEBUG, INFO_PATH
from topping_bot.util.cooldown import PULL_USER_1_PER_3S, PULL_MEMBER_5_PER_DAY, PULL_USER_50_PER_DAY
from topping_bot.util.parallel import SEMAPHORE

from topping_bot.crk.cookies import Filter, Order
from topping_bot.util.const import STATIC_PATH


class Utility(Cog, description="The utility commands available to you"):
    def __init__(self, bot):
        self.bot = bot

    def cog_check(self, ctx):
        try:
            approved_guild_only(ctx)
        except:
            traceback.print_exc()
        return approved_guild_only(ctx)

    @Cog.listener()
    async def on_ready(self):
        tqdm.write(f"{datetime.now().isoformat(sep=' ', timespec='seconds')} : Logged in as {self.bot.user}")

    @Cog.listener()
    async def on_command_error(self, ctx, error):
        if DEBUG:
            traceback.print_exception(error.original)

    @commands.command(checks=[admin_only], brief="Test", description="Test")
    async def test(self, ctx):
        await send_msg(
            ctx,
            title="Boosts",
            description=[f"All Boosts ({ctx.guild.premium_subscription_count})"]
            + [f"- {member}" for member in ctx.guild.premium_subscribers],
            wrap=False,
        )

    @commands.command(checks=[admin_only], brief="Restart", description="Restart")
    async def restart(self, ctx, update: bool = False):
        if SEMAPHORE.locked():
            tqdm.write(
                f"{datetime.now().isoformat(sep=' ', timespec='seconds')} : {ctx.message.author} queued !restart"
            )
            await send_msg(
                ctx,
                title="Restart Queued",
                description=[
                    "Your request to !restart has been queued",
                    "",
                    "This will start automatically when ready",
                ],
            )
        async with SEMAPHORE:
            action = "Restarting"
            f"{datetime.now().isoformat(sep=' ', timespec='seconds')} : {ctx.message.author} began !restart"
            if update:
                result = subprocess.run(["git pull"], shell=True, capture_output=True)
                if result.returncode != 0:
                    await send_msg(
                        ctx, title="Err: Update failed", description="Update failed, please perform manual update"
                    )
                    return
                action = "Updating"
            await send_msg(ctx, thumbnail=False, title=f"__**{action} Bot**__", image=CONFIG["static"]["revive"])
            PULL_USER_1_PER_3S.save()
            PULL_MEMBER_5_PER_DAY.save()
            PULL_USER_50_PER_DAY.save()
            exit(0)

    @commands.command(checks=[admin_only], brief="Commit", description="Commit")
    async def commit(self, ctx):
        add_result = subprocess.run(["git add ."], shell=True, capture_output=True)
        commit_result = subprocess.run(["git commit -m 'Automatic bot update'"], shell=True, capture_output=True)
        push_result = subprocess.run(["git push"], shell=True, capture_output=True)

        if any([add_result.returncode, commit_result.returncode, push_result.returncode]):
            await send_msg(ctx, title="Err: Commit failed", description="Commit failed, please perform manual commit")
        else:
            await send_msg(ctx, title="Commit Successful", description="Commit successful and pushed to remote")

    @commands.command(checks=[admin_only], brief="Reset CD", description="Reset CD")
    async def resetcd(self, ctx):
        PULL_USER_1_PER_3S.reset()
        PULL_MEMBER_5_PER_DAY.reset()
        PULL_USER_50_PER_DAY.reset()
        await send_msg(
            ctx, thumbnail=False, title="__**Resetting Cooldowns**__", description="Resetting all gacha cooldowns"
        )

    @commands.command(checks=[admin_only], brief="Kill", description="Kill")
    async def kill(self, ctx):
        await send_msg(ctx, thumbnail=False, title="__**Killing Bot**__", image=CONFIG["static"]["kill"])
        exit(-1)

    @commands.command(checks=[admin_only], brief="Rename", description="Rename the bot")
    async def nick(self, ctx, nickname):
        await ctx.bot.user.edit(username=nickname)

    @commands.command(checks=[admin_only], brief="View/edit todo", description="View or edit the todo list")
    async def todo(self, ctx, *args):
        if args:
            if not await admin_only(ctx):
                return

            item = " ".join(args)
            with open(INFO_PATH / "todo.txt", "a") as f:
                f.write(f"[ ] {item}\n")

        with open(INFO_PATH / "todo.txt") as f:
            items = f.readlines()

        await send_msg(
            ctx,
            title=f"Todo",
            description="".join(items),
            thumbnail=False,
        )

    @commands.command(brief="Acquired info", description="View acquired info that we've discovered")
    async def info(self, ctx):
        await send_msg(
            ctx,
            title="The Knowledge",
            description=[
                "1. ATK buffs come in the form of flat (nominal) increases, and percentage (multiplicative) buffs\n",
                "2. Buffed ATK is calculated as (base + flat) * percentage\n",
                "3. Each cookie has a base ATK% applied, check your cookie's with !baseatk\n"
                "4. The base crit multiplier is 1.5x\n",
                "5. Should you crit, the previous ATK calculation is performed then multiplied for a crit\n",
                "6. ATK% buffs that activate at the start of a battle (treasures, relics) are not added to topping ATK% buffs, but instead are their own multiplier\n",
                "7. Therefor, total ATK is calculated as ((base + flat) * topping %) * relic %\n",
                "8. After rebalancing updates, you may discover baseatk has been lowered for a given cookie, this is a buff",
            ],
        )

    @commands.command(brief="Ping the bot", description="Ping the bot and view the current latency")
    async def ping(self, ctx):
        await send_msg(
            ctx,
            title=f"{ctx.bot.user.name} Bot Latency",
            description=f"pong! (bot latency is {round(ctx.bot.latency, 3)} s)",
        )

    @commands.command(brief="Check status", description="Check the status of the bot")
    async def status(self, ctx):
        await send_msg(
            ctx,
            title=f"{ctx.bot.user.name} Status",
            description=[
                "Alive?: True",
                f"CPU Task?: {SEMAPHORE.locked()}",
                f"Queued Tasks: {len(SEMAPHORE._waiters) if SEMAPHORE._waiters else 0}",
            ],
        )

    @commands.command(checks=[admin_only], brief="Sync", description="Sync")
    async def sync(self, ctx, this_guild=False):
        if this_guild:
            self.bot.tree.copy_global_to(guild=ctx.guild)
            cmds = await self.bot.tree.sync(guild=ctx.guild)
        else:
            cmds = await self.bot.tree.sync()
        await send_msg(
            ctx,
            title=f"{ctx.bot.user.name} Command Sync",
            description=[
                f"{len(cmds)} commands synced",
            ],
        )

    @commands.command(checks=[admin_only], brief="Clear", description="Clear")
    async def clear(self, ctx):
        self.bot.tree.clear_commands(guild=None)
        cmds = await self.bot.tree.sync()
        self.bot.tree.clear_commands(guild=ctx.guild)
        self.bot.tree.copy_global_to(guild=ctx.guild)
        cmds = await self.bot.tree.sync()

        await send_msg(
            ctx,
            title=f"{ctx.bot.user.name} Command Clear",
            description=[
                f"{len(cmds)} commands cleared",
            ],
        )

    @commands.group(checks=[admin_only], brief="Announce", description="Announce")
    async def ann(self, ctx):
        pass

    @ann.command(checks=[admin_only], brief="Announce update", description="Announce update")
    async def update(self, ctx, push=True):
        with open(INFO_PATH / "update.txt", encoding="utf-8") as f:
            lines = f.readlines()

        channel = await ctx.bot.fetch_channel(CONFIG["community"]["updates"])

        msg = await channel.send(
            embed=await new_embed(
                title=f"{ctx.bot.user.name} {lines[0]}",
                description=[line.replace("\n", "") for line in lines[1:]],
            )
        )
        await msg.publish()
        if push:
            await channel.send(content="<@&1101366597953781810>")

    @ann.command(checks=[admin_only], brief="Announce secret", description="Announce secret")
    async def secret(self, ctx, push=True):
        with open(INFO_PATH / "secret.txt", encoding="utf-8") as f:
            lines = f.readlines()

        channel = await ctx.bot.fetch_channel(CONFIG["community"]["secrets"])

        msg = await channel.send(
            embed=await new_embed(
                title=f"{ctx.bot.user.name} {lines[0]}", description=[line.replace("\n", "") for line in lines[1:]]
            )
        )
        await msg.publish()
        if push:
            await channel.send(content="<@&1101366662147604540>")

    @commands.command(checks=[admin_only], brief="Vote", description="Vote")
    async def vote(self, ctx, cookie: str, add=True):
        cookie = Cookie.get(cookie)

        channel = await ctx.bot.fetch_channel(CONFIG["community"]["meta-vote"])

        msg = await channel.send(
            embed=await new_embed(
                title=f"{'Add' if add else 'Remove'} {cookie.name}?",
                description=[
                    f"{'Add' if add else 'Remove'} {cookie.name} {'to' if add else 'from'} the meta list?",
                    "Vote up for yes, down for no",
                ],
            )
        )
        await msg.add_reaction("🔼")
        await msg.add_reaction("🔽")

    @commands.command(checks=[admin_only], brief="Status", description="Status")
    async def status_msg(self, ctx, msg):
        await self.bot.change_presence(activity=Game(msg))

    @commands.command(checks=[admin_only], brief="Rules", description="Rules")
    async def rules(self, ctx):
        await ctx.send(
            embed=await new_embed(
                title=f"__**DISCORD RULES**__",
                description=[
                    "**GENERAL**",
                    "```"
                    "- This server is meant to aid in the development of the Eclair CRK bot, "
                    "please keep all discussion related to this effort",
                    "```",
                    "**CONTRIBUTIONS**",
                    "```" "- If you have something you'd like to see added, take it to #suggestions",
                    "",
                    "- The top 500 of arena (any server) may vote on the meta list, verify in #500-verify",
                    "```",
                    "**OPTIMIZATION**",
                    "```"
                    "- Team comp guide creators, server boosters (up to 20), or one representative from a top 30 guild "
                    "(any server) may request optimization access",
                    "",
                    "- Bot can only take so much, I can't give everyone optimization access",
                    "",
                    "- Please do not try to backdoor optimization for multiple people on one account",
                    "",
                    "- If you need any help while optimizing, ping either the @Admin or a @Moderator",
                    "```",
                    "**LASTLY**",
                    "```",
                    "- If you experience any issues, please ping the @Admin",
                    "",
                    "- Thank you and enjoy!",
                    "```",
                ],
                thumbnail=False,
                wrap=False,
            )
        )
