import asyncio
from concurrent.futures import ProcessPoolExecutor
from datetime import datetime
from multiprocessing.shared_memory import SharedMemory

import discord
from discord.ext import commands
from discord.ext.commands import Cog, parameter
from tqdm import tqdm

from topping_bot.optimize.reader import read_toppings, write_toppings
from topping_bot.util.common import (
    admin_only,
    approved_guild_ctx,
    approved_guild_only,
    edit_msg,
    guild_only,
    new_embed,
    send_msg,
)
from topping_bot.util.const import CONFIG, DATA_PATH, DEBUG_PATH, TMP_PATH
from topping_bot.util.cpu import full_extraction
from topping_bot.util.image import toppings_to_images
from topping_bot.util.parallel import RUNNING_CPU_TASK, SEMAPHORE
from topping_bot.ui.common import Paginator


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
    async def inv(self, ctx):
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

        toppings = read_toppings(fp)

        if not toppings:
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

        async with ctx.typing():
            channel = self.bot.get_channel(CONFIG["community"]["img-dump"])

            msgs = []
            embed_images = []

            images = toppings_to_images(toppings, ctx.message.author.id)

            for subset in (images[i: i + 10] for i in range(0, len(images), 10)):
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
            tqdm.write(
                f"{datetime.now().isoformat(sep=' ', timespec='seconds')} : {ctx.message.author} began !inv add"
            )
            if msg is None:
                msg = await send_msg(ctx, title="Uploading toppings...", description=["Please wait"])
            else:
                await edit_msg(msg, title="Uploading toppings...", description=["Please wait"])

            fp = TMP_PATH / f"{ctx.message.author.id}.mp4"
            fp.unlink(missing_ok=True)

            await edit_msg(
                msg,
                title=f"Uploading toppings...",
                description=[
                    "Please wait",
                    "",
                    f"Downloading video...",
                ],
            )

            topping_fp = DATA_PATH / f"{ctx.message.author.id}.csv"

            for idx, attachment in enumerate(ctx.message.attachments):
                await attachment.save(fp)

                loop = asyncio.get_running_loop()

                shared_memory = SharedMemory(create=True, size=64)
                with ProcessPoolExecutor() as executor:
                    task = loop.run_in_executor(executor, full_extraction, fp, shared_memory.name)

                    while not task.done():
                        await edit_msg(
                            msg,
                            title=f"Uploading toppings...",
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

                    toppings = task.result()

                if toppings is None or len(toppings) == 0:
                    await edit_msg(
                        msg,
                        title=f"Uploading toppings error {idx + 1}/{len(ctx.message.attachments)}",
                        description=["Parsing error when reading topping video", "Please contact the admin"],
                    )
                    RUNNING_CPU_TASK.pop(ctx.message.author.id)
                    return

                await edit_msg(
                    msg,
                    title=f"Uploading toppings...",
                    description=[
                        f"Video {idx + 1}/{len(ctx.message.attachments)}",
                        "",
                        f"Saving toppings",
                    ],
                )

                write_toppings(toppings, topping_fp, append=True)

        RUNNING_CPU_TASK.pop(ctx.message.author.id)

        await edit_msg(
            msg,
            title=f"Uploading toppings complete",
            description=[
                "Finished.",
                "",
                f"Thank you for your patience!",
                "Use !inv to view your inventory!"
            ],
        )

        fp.unlink(missing_ok=True)

    @inv.command(aliases=["del"], brief="Delete inv", description="Delete your topping inventory")
    async def delete(self, ctx):
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
        else:
            topping_fp.unlink(missing_ok=True)
            await send_msg(
                ctx,
                title="Deleted Topping Inventory",
                description=[
                    "Your topping inventory has been deleted",
                    f"Please use !inv add <video> to update your inventory",
                    "Use !tutorial to learn more",
                ],
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
        checks=[guild_only], aliases=["uploadinv"], brief="DEPRECATED", description="DEPRECATED | Use !inv delete & !inv add"
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

            loop = asyncio.get_running_loop()

            topping_fp = DATA_PATH / f"{video_id}.csv"

            shared_memory = SharedMemory(create=True, size=64)
            with ProcessPoolExecutor() as executor:
                task = loop.run_in_executor(executor, full_extraction, fp, shared_memory.name, True, verbose)

                while not task.done():
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

                toppings = task.result()

            if toppings is None or len(toppings) == 0:
                await edit_msg(
                    msg,
                    title=f"Debugging toppings error",
                    description=[
                        "No toppings found in the provided video",
                    ],
                )
                return

            await edit_msg(
                msg,
                title=f"Debugging toppings...",
                description=[
                    "Please wait",
                    "",
                    f"Saving toppings",
                ],
            )

            write_toppings(toppings, topping_fp, append=True)
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
