import asyncio
from datetime import datetime
from multiprocessing import Process
from multiprocessing.sharedctypes import Value
from multiprocessing.shared_memory import SharedMemory

import discord
from discord.ext import commands
from discord.ext.commands import Cog, parameter
import pyparsing as pp
from tqdm import tqdm

from topping_bot.optimize.inventory import Inventory as ToppingInventory
from topping_bot.optimize.reader import write_toppings
from topping_bot.util.common import (
    admin_only,
    approved_guild_only,
    edit_msg,
    guild_only,
    new_embed,
    send_msg,
)
from topping_bot.util.const import CONFIG, DATA_PATH, DEBUG_PATH, TMP_PATH
from topping_bot.util.cpu import full_extraction
from topping_bot.util.parallel import RUNNING_CPU_TASK, SEMAPHORE
from topping_bot.ui.common import Paginator, RemoveToppingsMenu


class Inventory(Cog, description="View and update your topping inventory"):
    def __init__(self, bot):
        self.bot = bot

    def cog_check(self, ctx):
        return approved_guild_only(ctx)

    @commands.command(brief="View count", description="View your topping inventory size")
    async def count(self, ctx):
        fp = DATA_PATH / f"{ctx.message.author.id}.csv"
        if not fp.exists():
            await send_msg(
                ctx,
                title="Err: No Topping Inventory",
                description=[
                    "You have not submitted a topping video.",
                    "Please use !inv add <video> to update your inventory.",
                    "Use !tutorial to learn more.",
                ],
            )
            return

        with open(fp) as f:
            count = len(f.readlines())

        await send_msg(
            ctx,
            title="Topping Inventory Count",
            description=[
                "You currently have",
                f"├ {count} Toppings",
                "Use !inv add to add more",
            ],
        )

    @commands.group(brief="View inv", description="View your topping inventory", invoke_without_command=True)
    async def inv(self, ctx, *query: str):
        fp = DATA_PATH / f"{ctx.message.author.id}.csv"
        if not fp.exists():
            await send_msg(
                ctx,
                title="Err: No Topping Inventory",
                description=[
                    "You have not submitted a topping video.",
                    "Please use !inv add <video> to update your inventory.",
                    "Use !tutorial to learn more.",
                ],
            )
            return

        query = " ".join(query).strip()
        inventory = ToppingInventory.from_file(fp)
        if not inventory.toppings:
            await send_msg(
                ctx,
                title="Err: No Topping Inventory",
                description=[
                    "Your toppings on file are empty.",
                    "Please use !inv add <video> to update your inventory.",
                    "Use !tutorial to learn more.",
                ],
            )
            return

        if query:
            try:
                inventory = inventory.filter(query)
            except pp.ParseException as exc:
                await send_msg(
                    ctx,
                    title="Err: Invalid Topping Filter",
                    description=exc.explain(depth=0),
                )
                return

            if len(inventory.toppings) == 0:
                await send_msg(
                    ctx,
                    title="Err: Strict Topping Filter",
                    description=[
                        "The specified topping filter leaves zero toppings for viewing",
                        "",
                        "Please relax the filter and try again",
                    ],
                )
                return

        async with ctx.typing():
            channel = self.bot.get_channel(CONFIG["community"]["img-dump"])

            msgs = []
            embed_images = []

            images = inventory.to_images(ctx.message.author.id)

            for subset in (images[i : i + 10] for i in range(0, len(images), 10)):
                msg = await channel.send(files=[discord.File(image, filename=image.name) for image in subset])
                embed_images.extend([attachment.url for attachment in msg.attachments])
                msgs.append(msg)

            await Paginator().start(
                ctx,
                pages=[
                    await new_embed(title="**Your Topping Inventory**", image=image, thumbnail=False)
                    for image in embed_images
                ],
                messages=msgs,
            )

        for fp in images:
            fp.unlink(missing_ok=True)

    @inv.command(aliases=["a"], brief="Add to inv", description="Add to your topping inventory")
    async def add(self, ctx):
        if not ctx.message.attachments:
            await send_msg(
                ctx,
                title="Err: No Topping Video",
                description=[
                    "You do not have a topping video attached",
                    f"Please use !inv add <video> to update your inventory",
                    "Use !tutorial to learn more",
                ],
            )
            return

        if ctx.message.author.id in RUNNING_CPU_TASK:
            await send_msg(
                ctx,
                title="Err: Running CPU Task",
                description=[
                    "You are already running or have queued one CPU task*",
                    f"Please wait for this task to finish before queueing another",
                    "",
                    "CPU tasks include !optimize and !inv add",
                ],
            )
            return

        msg = None
        if SEMAPHORE.locked():
            tqdm.write(
                f"{datetime.now().isoformat(sep=' ', timespec='seconds')} : {ctx.message.author} queued !inv add"
            )
            msg = await send_msg(
                ctx,
                title="Upload Toppings Queued",
                description=[
                    f"Your request to !inv add has been queued",
                    "",
                    "This will start automatically when ready",
                ],
            )

        RUNNING_CPU_TASK[ctx.message.author.id] = None
        async with SEMAPHORE:
            tqdm.write(f"{datetime.now().isoformat(sep=' ', timespec='seconds')} : {ctx.message.author} began !inv add")
            if msg is None:
                msg = await send_msg(ctx, title="Uploading Toppings...", description=["Please wait"])
            else:
                await edit_msg(msg, title="Uploading Toppings...", description=["Please wait"])

            fp = TMP_PATH / f"{ctx.message.author.id}.mp4"
            fp.unlink(missing_ok=True)

            await edit_msg(
                msg,
                title=f"Uploading Toppings...",
                description=[
                    "Please wait",
                    "",
                    f"Downloading video...",
                ],
            )

            topping_fp = DATA_PATH / f"{ctx.message.author.id}.csv"

            for idx, attachment in enumerate(ctx.message.attachments):
                await attachment.save(fp)

                solution = Value("i", -1)
                shared_memory = SharedMemory(create=True, size=64)
                process = Process(target=full_extraction, args=(fp, topping_fp, shared_memory.name, solution))
                RUNNING_CPU_TASK[ctx.message.author.id] = process

                process.start()
                while process.is_alive():
                    await edit_msg(
                        msg,
                        title=f"Uploading Toppings...",
                        description=[
                            f"Video {idx + 1}/{len(ctx.message.attachments)}",
                            "",
                            f"Discovering toppings",
                            bytes(shared_memory.buf[:]).decode(encoding="utf-8", errors="ignore").rstrip("\x00"),
                        ],
                    )
                    await asyncio.sleep(2)

                shared_memory.close()
                shared_memory.unlink()

                toppings = solution

                if process.exitcode != 0:
                    await send_msg(
                        ctx,
                        title="Err: Upload Forcibly Stopped",
                        description=[
                            "The upload was forcibly stopped either by extended timeout or !stop",
                            "",
                            "If this is unexpected, please contact the admin",
                        ],
                        footer=f"admin: @{(await ctx.bot.application_info()).owner}",
                    )
                    RUNNING_CPU_TASK.pop(ctx.message.author.id, None)
                    return
                elif toppings.value <= 0:
                    await edit_msg(
                        msg,
                        title=f"Err: Uploading Toppings {idx + 1}/{len(ctx.message.attachments)}",
                        description=["Parsing error when reading topping video", "Please contact the admin"],
                        footer=f"admin: @{(await ctx.bot.application_info()).owner}",
                    )
                    RUNNING_CPU_TASK.pop(ctx.message.author.id, None)
                    return

        RUNNING_CPU_TASK.pop(ctx.message.author.id, None)

        await edit_msg(
            msg,
            title=f"Uploading Toppings Complete",
            description=["Finished.", "", f"Thank you for your patience!", "Use !inv to view your inventory!"],
        )

        fp.unlink(missing_ok=True)

        inventory = ToppingInventory.from_file(topping_fp).filter("dups")

        if len(inventory.toppings) > 0:
            await send_msg(
                ctx,
                title="Duplicate Toppings",
                description=[
                    f"You have {len(inventory.toppings)} duplicate topping{'s' if len(inventory.toppings) != 1 else ''}",
                    "",
                    "View them with '!inv dups' or delete them with '!inv delete dups'",
                ],
                thumbnail=False,
            )

    @inv.command(aliases=["del"], brief="Delete inv", description="Delete your topping inventory")
    async def delete(self, ctx, *query: str):
        topping_fp = DATA_PATH / f"{ctx.message.author.id}.csv"

        if not topping_fp.exists():
            await send_msg(
                ctx,
                title="Err: No Topping Inventory",
                description=[
                    "You do not have a topping inventory to delete",
                    f"Please use !inv add <video> to update your inventory",
                    "Use !tutorial to learn more",
                ],
            )
            return

        query = " ".join(query).strip()
        inventory = ToppingInventory.from_file(topping_fp)
        if not inventory.toppings:
            await send_msg(
                ctx,
                title="Err: No Topping Inventory",
                description=[
                    "Your toppings on file are empty.",
                    "Please use !inv add <video> to update your inventory.",
                    "Use !tutorial to learn more.",
                ],
            )
            return

        if query:
            try:
                filtered_inventory = inventory.filter(query)
            except pp.ParseException as exc:
                await send_msg(
                    ctx,
                    title="Err: Invalid Topping Filter",
                    description=exc.explain(depth=0),
                )
                return

            if len(filtered_inventory.toppings) == 0:
                await send_msg(
                    ctx,
                    title="Err: Strict Topping Filter",
                    description=[
                        "The specified topping filter leaves zero toppings for deletion",
                        "",
                        "Please relax the filter and try again",
                    ],
                )
                return

        if query:
            async with ctx.typing():
                channel = self.bot.get_channel(CONFIG["community"]["img-dump"])

                msgs = []
                embed_images = []

                images = filtered_inventory.to_images(ctx.message.author.id)

                for subset in (images[i : i + 10] for i in range(0, len(images), 10)):
                    msg = await channel.send(files=[discord.File(image, filename=image.name) for image in subset])
                    embed_images.extend([attachment.url for attachment in msg.attachments])
                    msgs.append(msg)

                remove_toppings = RemoveToppingsMenu()
                await remove_toppings.start(ctx, pages=embed_images, messages=msgs)

            for fp in images:
                fp.unlink(missing_ok=True)

        else:
            remove_toppings = RemoveToppingsMenu()
            await remove_toppings.start(ctx)

        timeout = await remove_toppings.wait()
        if timeout or not remove_toppings.result:
            return

        if query:
            inventory = inventory.filter(f"not ({query})")
            write_toppings((t for _, t in inventory.toppings), topping_fp)
        else:
            topping_fp.unlink(missing_ok=True)

    @inv.command(aliases=["h"], brief="Learn inv", description="Learn about how inv filters work")
    async def help(self, ctx):
        embed = await new_embed(
            title="__**Inventory Filters Guide**__",
            description=[
                "**FILTERS**",
                "```Both '!inv' and '!inv delete' support optional filters for viewing/deletion```",
                "**TYPES**",
                "``` - Resonance : e.g. !inv resonance == Trio",
                " - Flavor : e.g. !inv delete flavor != ATK",
                " - Substats : e.g. !inv ATK in subs | !inv delete (ATK SPD, Cooldown) in substats",
                " - ID : e.g. !inv delete 123, 456, 789",
                " - Duplicates : e.g. !inv delete duplicates```",
                "**COMBINATIONS**",
                "```All of these specifiers can be combined with logical operators (not, and, or)",
                " - e.g. !inv res is Normal and flavor == Cooldown",
                "   ↳ Would show all non-resonant chocolate toppings",
                "",
                "Be sure to use parenthesis to override operator precedence```",
                "**ALL OPERATORS**",
                "``` - equals : == | is",
                " - not equals : != | is not",
                " - in : in",
                " - not in : not in```",
            ],
            wrap=False,
        )
        await ctx.reply(embed=embed)

    @commands.command(checks=[admin_only], brief="Debug video", description="Debug video")
    async def debug(self, ctx, video_id, verbose=False):
        msg = None
        if SEMAPHORE.locked():
            msg = await send_msg(
                ctx,
                title="Debug Toppings Queued",
                description=[
                    "Your request to !debug has been queued",
                    "",
                    "This will start automatically when ready",
                ],
            )

        async with SEMAPHORE:
            # clear out debug folder on each run
            for file in DEBUG_PATH.iterdir():
                file.unlink(missing_ok=True)

            if msg is None:
                msg = await send_msg(ctx, title="Debugging toppings...", description=["Please wait"])
            else:
                await edit_msg(msg, title="Debugging toppings...", description=["Please wait"])

            fp = TMP_PATH / f"{video_id}.mp4"

            topping_fp = DATA_PATH / f"{video_id}.csv"

            solution = Value("i", -1)
            shared_memory = SharedMemory(create=True, size=64)
            process = Process(
                target=full_extraction, args=(fp, topping_fp, shared_memory.name, solution, True, verbose)
            )

            process.start()
            while process.is_alive():
                await edit_msg(
                    msg,
                    title=f"Debugging toppings...",
                    description=[
                        "Please wait",
                        "",
                        f"Discovering toppings",
                        bytes(shared_memory.buf[:]).decode(encoding="utf-8", errors="ignore").rstrip("\x00"),
                    ],
                )
                await asyncio.sleep(2)

            shared_memory.close()
            shared_memory.unlink()

            toppings = solution

            if process.exitcode != 0:
                await send_msg(
                    ctx,
                    title="Err: Debug Forcibly Stopped",
                    description=[
                        "The debug was forcibly stopped either by extended timeout or !stop",
                        "",
                        "If this is unexpected, please contact the admin",
                    ],
                    footer=f"admin: @{(await ctx.bot.application_info()).owner}",
                )
                RUNNING_CPU_TASK.pop(ctx.message.author.id, None)
                return
            elif toppings.value <= 0:
                await edit_msg(
                    msg,
                    title=f"Debugging toppings error",
                    description=[
                        "No toppings found in the provided video",
                    ],
                )
                return

            member = await ctx.guild.fetch_member(video_id)
            name = member.nick if member.nick else member.name

            await edit_msg(
                msg,
                title=f"Debugging toppings complete",
                description=[
                    "```Finished.",
                    "",
                    f"Thank you for your patience!",
                    f"{name}, please use !inv```",
                    f"<@{video_id}>",
                ],
                wrap=False,
            )

    @commands.command(checks=[guild_only], brief="DEPRECATED", description="DEPRECATED | Use !inv add")
    async def appendinv(self, ctx):
        await send_msg(
            ctx,
            title="Err: Use !inv add",
            description=[
                "!appendinv has been DEPRECATED, please use '!inv add' instead",
                "Use !tutorial to learn more",
            ],
        )

    @commands.command(
        checks=[guild_only],
        aliases=["uploadinv"],
        brief="DEPRECATED",
        description="DEPRECATED | Use !inv delete & !inv add",
    )
    async def updateinv(self, ctx):
        await send_msg(
            ctx,
            title="Err: Use !inv delete & !inv add",
            description=[
                "!updateinv has been DEPRECATED, please use '!inv delete' & '!inv add' instead",
                "Use !tutorial to learn more",
            ],
        )

    @inv.command(aliases=["delt"], brief="DEPRECATED", description="DEPRECATED")
    async def deletetopping(
        self,
        ctx,
        indices=parameter(
            description="indices of toppings in inventory separated by space (up to 25 toppings)",
        ),
    ):
        await send_msg(
            ctx,
            title="Err: Use !inv delete <index list>",
            description=[
                "!inv deletetopping has been DEPRECATED, please use '!inv delete <index list>' instead",
                "Use !inv help to learn more",
            ],
        )
