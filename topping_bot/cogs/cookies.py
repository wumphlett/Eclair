import asyncio
import json
from datetime import datetime, timedelta
from multiprocessing import Process
from multiprocessing.sharedctypes import Array
from multiprocessing.shared_memory import SharedMemory
from pathlib import Path

import discord
from discord.ext import commands
from discord.ext.commands import Cog, parameter
from tqdm import tqdm

from topping_bot.optimize.optimize import Optimizer
from topping_bot.optimize.reader import read_toppings
from topping_bot.optimize.requirements import Requirements
from topping_bot.util.common import (
    approved_guild_ctx,
    approved_guild_only,
    edit_msg,
    filter_requirements_files,
    find_member,
    moderator_only,
    new_embed,
    send_msg,
)
from topping_bot.util.const import CONFIG, DATA_PATH
from topping_bot.util.cpu import optimize_cookie
from topping_bot.util.image import topping_set_to_image
from topping_bot.util.parallel import RUNNING_CPU_TASK, SEMAPHORE
from topping_bot.ui.common import RemoveToppingsMenu, RequirementConfirm, RequirementView
from topping_bot.util.utility import leaderboard_path


class Cookies(Cog, description="Optimize your cookies' toppings"):
    def __init__(self, bot):
        self.bot = bot

    def cog_check(self, ctx):
        return approved_guild_only(ctx)

    @commands.command(brief="Bot tutorial", description="Learn how to use the topping optimizer")
    async def tutorial(self, ctx):
        await send_msg(
            ctx,
            title="__**Tutorial**__",
            image=CONFIG["static"]["tutorial"],
            description=[
                "**SETUP**",
                "```1. Set your in-game language to English",
                "2. Set your Discord upload quality to Best Quality```",
                "**RECORD**",
                "```3. Record a video of your best toppings",
                "4. Upload your video using the command !inv add```",
                "**OPTIMIZE**",
                "```5. Calculate your topping sets with !optimize```",
            ],
            wrap=False,
        )

    @commands.command(
        brief="Optimize", description="Optimize toppings given a requirements file", aliases=["optimise", "o"]
    )
    async def optimize(self, ctx, target=parameter(description="who to optimize for", default=None)):
        if target and not moderator_only(ctx):
            return
        if target and (target := await find_member(ctx, target)) is None:
            return
        if target and not moderator_only(ctx, member_id=target.id):
            return

        options = await filter_requirements_files(ctx, override_user=target)
        if len(options) == 0:
            await send_msg(
                ctx,
                title="Err: No Requirements Files",
                description=[
                    "You have uploaded a requirement file",
                    "Please use !req upload <attch file> to specify a team to optimize",
                    "Use !req help to learn more",
                ],
            )
            return

        user = target if target else ctx.message.author

        reqs_view = RequirementView()
        await reqs_view.start(ctx, options, "What team would you like to optimize towards?")

        timeout = await reqs_view.wait()
        if timeout or not reqs_view.result:
            return

        requirements_fp = Path(reqs_view.result)
        cookies = Requirements.from_yaml(requirements_fp)

        topping_fp = DATA_PATH / f"{user.id}.csv"
        if not topping_fp.exists():
            await send_msg(
                ctx,
                title="Err: No Topping Inventory",
                description=[
                    "You have not submitted a topping video",
                    "Please use !inv add <attch video> to update your inventory",
                    "Use !tutorial to learn more",
                ],
            )
            return

        toppings = read_toppings(topping_fp)

        if not toppings:
            await send_msg(
                ctx,
                title="Err: No Topping Inventory",
                description=[
                    "Your toppings on file are empty",
                    "Please use !inv add <attch video> to update your inventory",
                    "Use !tutorial to learn more",
                ],
            )
            return

        if user.id in RUNNING_CPU_TASK:
            await send_msg(
                ctx,
                title="Err: Running CPU Task",
                description=[
                    "You are already running or have queued one CPU task*",
                    f"Please wait for this task to finish before queueing another",
                    "",
                    "*CPU tasks include !optimize and !inv add",
                ],
            )
            return

        name = requirements_fp.stem
        guild = approved_guild_ctx(ctx)
        is_default = name.startswith(f"{guild.fp}-")
        emoji = guild.choose_emoji(name)
        name = guild.sanitize(name, user.id)

        reqs_confirm = RequirementConfirm()
        await reqs_confirm.start(
            ctx,
            f"{emoji} **{name} Requirements**\n\n" + "\n".join(str(cookie) for cookie in cookies),
        )

        timeout = await reqs_confirm.wait()
        if timeout or not reqs_confirm.result:
            return

        msg = None
        if SEMAPHORE.locked():
            tqdm.write(f"{datetime.now().isoformat(sep=' ', timespec='seconds')} : {user} queued !optimize")
            msg = await send_msg(
                ctx,
                title="Optimize Toppings Queued",
                description=[
                    "Your request to !optimize has been queued",
                    "",
                    "This will start automatically when ready",
                ],
            )

        RUNNING_CPU_TASK[user.id] = None
        async with SEMAPHORE:
            tqdm.write(f"{datetime.now().isoformat(sep=' ', timespec='seconds')} : {user} began !optimize")

            if msg is None:
                await send_msg(
                    ctx,
                    title="Optimizing Cookie Toppings",
                    description=[f"```Solving {emoji} {name}:"]
                    + [f"├ {cookie.name}" for cookie in cookies]
                    + ["", "Please wait ...```"]
                    + ([f"<@{target.id}>"] if target else []),
                    wrap=False,
                )
            else:
                await edit_msg(
                    msg,
                    title="Optimizing Cookie Toppings",
                    description=[f"```Solving {emoji} {name}:"]
                    + [f"├ {cookie.name}" for cookie in cookies]
                    + ["", "Please wait ...```"]
                    + ([f"<@{target.id}>"] if target else []),
                    wrap=False,
                )

            results = {}
            cancelled = False
            optimizer = Optimizer(toppings)

            for cookie in cookies:
                if len(optimizer.inventory) < 5:
                    await send_msg(
                        ctx,
                        title="Err: Low Topping Inventory",
                        description=[
                            "You have less than 5 toppings currently in inventory",
                            "Please use !inv add <attch video> to add more toppings",
                        ],
                    )
                    RUNNING_CPU_TASK.pop(user.id, None)
                    return

                progress = await send_msg(ctx, title=f"Solving {cookie.name} ...")

                solution = Array("i", 5)
                shared_memory = SharedMemory(create=True, size=64)
                process = Process(target=optimize_cookie, args=(optimizer, cookie, shared_memory.name, solution))
                RUNNING_CPU_TASK[user.id] = process

                old_desc = ""
                start_time = datetime.now()
                process.start()
                while process.is_alive():
                    desc = bytes(shared_memory.buf[:]).decode(encoding="utf-8", errors="ignore").rstrip("\x00")
                    if old_desc != desc and shared_memory.buf[-1] != 1:
                        await edit_msg(progress, title=f"Solving {cookie.name} ...", description=desc)
                        old_desc = desc
                    elif shared_memory.buf[-1] == 1:
                        await edit_msg(progress, title=f"Solving {cookie.name} Stopping", description="Stopping...")

                    await asyncio.sleep(2)

                    if not cancelled and start_time + timedelta(minutes=20) < datetime.now():
                        cancel_memory = SharedMemory(name=shared_memory.name)
                        cancel_memory.buf[-1] = 1
                        cancelled = True

                    if cancelled and start_time + timedelta(minutes=22) < datetime.now():
                        process.terminate()

                shared_memory.close()
                shared_memory.unlink()

                await progress.delete()

                if process.exitcode != 0:
                    await send_msg(
                        ctx,
                        title="Err: Solve Forcibly Stopped",
                        description=[
                            "The topping set solve was forcibly stopped either by extended timeout or !stop",
                            "",
                            "If this is unexpected, please optimize your requirements or contact the admin",
                        ],
                        footer=f"admin: @{(await ctx.bot.application_info()).owner}",
                    )
                    RUNNING_CPU_TASK.pop(user.id, None)
                    return
                elif not any(solution[:]):
                    await send_msg(
                        ctx,
                        title="Err: No Solution Found",
                        description=[
                            "A valid topping set given your current inventory is impossible",
                            "",
                            "Please use !inv add <attch video> to add more toppings",
                        ],
                    )
                    RUNNING_CPU_TASK.pop(user.id, None)
                    return

                optimizer.set_solution(solution)
                optimizer.reqs = cookie
                optimizer.select(cookie.name)

                cookie_img = topping_set_to_image(optimizer.solution, ctx.message.author.id)

                name = "".join(char for char in cookie.name if char.isalnum())
                image = discord.File(cookie_img, filename=f"{name}.png")
                title = (
                    f"__**{cookie.name} Topping Set**__"
                    if not cancelled
                    else f"__**{cookie.name} STOPPED Topping Set**__"
                )
                footer = "  |  ".join(
                    f"{substat.value} : {value:.1f}"
                    for substat, value in optimizer.reqs.objective.fancy_value(optimizer.solution).items()
                )
                embed = await new_embed(
                    title=title,
                    image=f"attachment://{name}.png",
                    footer=footer,
                    thumbnail=False,
                )

                await ctx.reply(embed=embed, file=image)

                if cancelled:
                    break

                results[name] = str(optimizer.reqs.objective.value(optimizer.solution))

            RUNNING_CPU_TASK.pop(user.id, None)

            if is_default and not cancelled:
                leaderboard_fp = leaderboard_path(requirements_fp)

                if leaderboard_fp.exists():
                    with open(leaderboard_fp) as f:
                        data = json.load(f)
                else:
                    data = {}

                data[user.id] = results

                with open(leaderboard_fp, "w") as f:
                    json.dump(data, f, indent=4)

        cookie_img.unlink(missing_ok=True)

        embed_options = {
            "title": "Remove Used Toppings?",
            "description": "Would you like to remove the used toppings from your inventory?",
        }
        inner_embed_options = {
            "title": "CONFIRM REMOVE USED TOPPINGS",
            "description": "ARE YOU SURE YOU WANT TO REMOVE THE USED TOPPINGS FROM YOUR INVENTORY?",
        }

        await RemoveToppingsMenu(timeout=600).start(
            ctx,
            user,
            toppings=optimizer.inventory,
            fp=topping_fp,
            embed_options=embed_options,
            inner_embed_options=inner_embed_options,
        )

    @commands.command(brief="Stop", description="Stop a running cpu task")
    async def stop(self, ctx):
        if RUNNING_CPU_TASK.get(ctx.message.author.id):
            process = RUNNING_CPU_TASK[ctx.message.author.id]
            process.terminate()
            RUNNING_CPU_TASK.pop(ctx.message.author.id, None)
            await send_msg(
                ctx,
                title="Stopping Task",
                description=[
                    "Your running cpu task is being stopped",
                ],
            )
        elif await ctx.bot.is_owner(ctx.author):
            for k, process in RUNNING_CPU_TASK.items():
                process.terminate()
            RUNNING_CPU_TASK.clear()
