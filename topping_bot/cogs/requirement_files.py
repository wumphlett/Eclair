from datetime import datetime
from pathlib import Path
import shutil

import discord
from discord.ext import commands
from discord.ext.commands import Cog, parameter
from tqdm import tqdm

from topping_bot.optimize.requirements import Requirements, sanitize
from topping_bot.util.common import (
    approved_guild_ctx,
    approved_guild_only,
    filter_requirements_files,
    find_member,
    guild_only,
    moderator_only,
    new_embed,
    send_msg,
)
from topping_bot.util.const import REQS_PATH, TMP_PATH
from topping_bot.ui.common import OverwriteConfirm, RequirementView


class RequirementFiles(Cog, description="View and edit your requirement files"):
    def __init__(self, bot):
        self.bot = bot

    def cog_check(self, ctx):
        return approved_guild_only(ctx)

    @commands.group(aliases=["rq", "r"], brief="Req file commands", description="Commands for req files")
    async def req(self, ctx):
        pass

    @req.group(
        name="def",
        aliases=["default"],
        checks=[approved_guild_only, guild_only, moderator_only],
        brief="Default req file commands",
        description="Commands to manage default req files",
    )
    async def default(self, ctx):
        pass

    @req.command(aliases=["h"], brief="Learn reqs", description="Learn about the structure of requirement files")
    async def help(self, ctx):
        embed = await new_embed(
            title="__**Requirement Files Guide**__",
            description=[
                "**GENERAL**",
                "```1. Requirement files hold the details of the team you're trying to optimize.",
                "2. You can optimize up to 10 cookies in each file.",
                "3. Use !req download to download a default file and view an example.```",
                "**REQUIREMENTS**",
                "```4. Requirements are specified under each cookie in a yaml file.",
                "5. Each cookie can accept a collection of validity requirements and one objective requirement.```",
                "**VALIDITY**",
                "``` - Simple: Substat compared to a target",
                "   ↳ Cooldown >= 6.3",
                " - Relative: Substat, above or below, and target",
                "   ↳ ATK SPD below Rye",
                " - Range: A range of valid substat values",
                "   ↳ 28 <= Cooldown <= 28.5",
                "   ↳ Note: targets must be cookies",
                " - Equality: Pin a substat to a specific value",
                "   ↳ Cooldown == 28.3```",
                "**OBJECTIVE**",
                "``` - Objective: Require objective and a substat",
                " - Special: Require special and relevant info.",
                "   - E[DMG] : Combines the right amount CRIT% and ATK",
                "   - Vitality : Combines the right amount HP and DMG Res.",
                "   - Combo : Combines multiple substats```",
            ],
            wrap=False,
        )
        await ctx.reply(embed=embed, file=discord.File(REQS_PATH / "example.yaml", filename="example.yaml"))

    @req.command(aliases=["v"], brief="View", description="View a requirements file")
    async def view(self, ctx):
        options = await filter_requirements_files(ctx)
        if len(options) == 0:
            await send_msg(
                ctx,
                title="Err: No Requirements Files",
                description=[
                    "You have not uploaded a requirement file",
                    "Please use !req upload <attch file> to specify a team to optimize",
                    "Use !req help to learn more",
                ],
            )
            return

        reqs_view = RequirementView()
        await reqs_view.start(ctx, options, "What requirement file do you want to view?")

        timeout = await reqs_view.wait()
        if timeout or not reqs_view.result:
            return

        requirements_fp = Path(reqs_view.result)

        if requirements_fp.parent != REQS_PATH:
            return

        name = requirements_fp.stem
        guild = approved_guild_ctx(ctx)
        emoji = guild.choose_emoji(name)
        name = guild.sanitize(name, ctx.message.author.id)

        try:
            cookies = Requirements.from_yaml(requirements_fp)
        except Exception as exc:
            await send_msg(
                ctx,
                title="Err: Improper Requirement File",
                description=[
                    "Requirements file cannot be parsed",
                    "",
                    f"├ {exc}",
                    "",
                    "Please use !req upload <file> once fixed",
                ],
            )
            return
        await send_msg(
            ctx,
            title="__**View Requirements File**__",
            description=f"{emoji} **{name} Requirements**\n\n" + "\n".join(str(cookie) for cookie in cookies),
            wrap=False,
            thumbnail=False,
        )

    @req.command(aliases=["c"], brief="Copy", description="Copy a requirements file")
    async def copy(self, ctx, target=parameter(description="who to copy to", default=None)):
        if target and not moderator_only(ctx):
            return
        if target and (target := await find_member(ctx, target)) is None:
            return
        if target and not moderator_only(ctx, member_id=target.id):
            return

        options = await filter_requirements_files(ctx, include_personal=target is not None)
        if len(options) == 0:
            await send_msg(
                ctx,
                title="Err: No Requirements Files",
                description=[
                    "You have not uploaded a requirement file",
                    "Please use !req upload <attch file> to specify a team to optimize",
                    "Use !req help to learn more",
                ],
            )
            return

        reqs_view = RequirementView()
        await reqs_view.start(ctx, options, "What requirement file do you want to copy?")

        timeout = await reqs_view.wait()
        if timeout or not reqs_view.result:
            return

        requirements_fp = Path(reqs_view.result)

        if requirements_fp.parent != REQS_PATH:
            return

        tmp = sanitize(requirements_fp, ctx.message.author.id, rem_leaderboard=True)

        index = requirements_fp.name.index("-") + 1
        req_name = requirements_fp.name[index:]
        base = req_name.rsplit(".", 1)[0]

        destination = REQS_PATH / f"{target.id if target else ctx.message.author.id}-{req_name}"

        guild = approved_guild_ctx(ctx)
        name = guild.sanitize(destination.stem, target.id if target else ctx.message.author.id)

        if target and destination.exists():
            overwrite_confirm = OverwriteConfirm()
            await overwrite_confirm.start(
                ctx,
                target,
                "\n".join(
                    [
                        "```",
                        f"Would you like to let {ctx.message.author} overwrite {name.title()}?",
                        "```",
                        f"<@{target.id}>",
                    ]
                ),
            )

            timeout = await overwrite_confirm.wait()
            if timeout or not overwrite_confirm.result:
                return
        else:
            count = 1
            while destination.exists():
                destination = REQS_PATH / f"{target.id if target else ctx.message.author.id}-{base}-{count}.yaml"
                count += 1

        shutil.copy(tmp, destination)
        tmp.unlink(missing_ok=True)

        await send_msg(
            ctx,
            title="Copied Requirements File",
            description=["```", f"Your requirements file has been copied to {name.title()}", "```"]
            + ([f"<@{target.id}>"] if target else []),
            wrap=False,
        )

    @req.command(name="download", aliases=["d", "dl"], brief="Download", description="Download a requirements file")
    async def req_download(self, ctx):
        await self.common_download(ctx)

    @default.command(
        name="download", aliases=["d", "dl"], brief="Download", description="Download a default requirements file"
    )
    async def def_download(self, ctx):
        await self.common_download(ctx, default_mode=True)

    @staticmethod
    async def common_download(ctx, default_mode=False):
        options = (
            await filter_requirements_files(ctx)
            if not default_mode
            else await filter_requirements_files(ctx, include_personal=False)
        )
        if len(options) == 0:
            await send_msg(
                ctx,
                title="Err: No Requirements Files",
                description=[
                    "You have not uploaded a requirement file",
                    "Please use !req upload <attch file> to specify a team to optimize",
                    "Use !req help to learn more",
                ],
            )
            return

        reqs_view = RequirementView()
        await reqs_view.start(ctx, options, "What requirement file do you want to download?")

        timeout = await reqs_view.wait()
        if timeout or not reqs_view.result:
            return

        requirements_fp = Path(reqs_view.result)

        if requirements_fp.parent != REQS_PATH:
            return

        tmp = sanitize(requirements_fp, ctx.message.author.id, rem_leaderboard=not default_mode)

        index = requirements_fp.name.index("-") + 1
        embed = await new_embed(
            title="Requested Requirements File",
            description=[
                "Here is the requirements file you requested",
                "",
                "Feel free to make changes and upload your own copy",
            ],
        )
        await ctx.reply(embed=embed, file=discord.File(tmp, filename=requirements_fp.name[index:]))
        tmp.unlink(missing_ok=True)

    @req.command(name="upload", aliases=["u"], brief="Upload", description="Upload a requirements file")
    async def req_upload(self, ctx, target=parameter(description="who to upload for", default=None)):
        await self.common_upload(ctx, target=target)

    @default.command(name="upload", aliases=["u"], brief="Upload", description="Upload a default requirements file")
    async def def_upload(self, ctx):
        await self.common_upload(ctx, default_mode=True)

    @staticmethod
    async def common_upload(ctx, target=None, default_mode=False):
        if target and not moderator_only(ctx):
            return
        if target and (target := await find_member(ctx, target)) is None:
            return
        if target and not moderator_only(ctx, member_id=target.id):
            return

        if not ctx.message.attachments:
            await send_msg(
                ctx,
                title="Err: No Requirement File",
                description=[
                    "You do not have a requirement file attached",
                    "Please use !req upload <file> to upload a file",
                ],
            )
            return

        if len(await filter_requirements_files(ctx, include_personal=not default_mode, override_user=target)) >= 25:
            await send_msg(
                ctx,
                title="Err: Too Many Requirement Files",
                description=[
                    "You have too many requirement files",
                    "Please use !req delete to remove some",
                ],
            )
            return

        req_file = ctx.message.attachments[0]

        if not (req_file.filename.endswith("yaml") or req_file.filename.endswith("yml")):
            await send_msg(
                ctx,
                title="Err: Improper Requirement File",
                description=[
                    "Requirements file must be a yaml file",
                    "Please use !req upload <file> to upload a file",
                ],
            )
            return

        if req_file.size > 10_240:
            await send_msg(
                ctx,
                title="Err: Improper Requirement File",
                description=[
                    "Requirements file must less than 10 KB",
                    "Please use !req upload <file> to upload a file",
                ],
            )
            return

        guild = approved_guild_ctx(ctx)

        fp = REQS_PATH / (
            f"{target.id if target else ctx.message.author.id}-{req_file.filename}"
            if not default_mode
            else f"{guild.fp}-{req_file.filename}"
        )

        name = guild.sanitize(fp.stem, target.id if target else ctx.message.author.id)

        if target and fp.exists():
            overwrite_confirm = OverwriteConfirm()
            await overwrite_confirm.start(
                ctx,
                target,
                "\n".join(
                    [
                        "```",
                        f"Would you like to let {ctx.message.author} overwrite {name.title()}?",
                        "```",
                        f"<@{target.id}>",
                    ]
                ),
            )

            timeout = await overwrite_confirm.wait()
            if timeout or not overwrite_confirm.result:
                return

        tmp_fp = TMP_PATH / f"{ctx.message.author.id}.yaml"
        tmp_fp.unlink(missing_ok=True)

        await req_file.save(tmp_fp)

        try:
            cookies = Requirements.from_yaml(tmp_fp)
        except Exception as exc:
            msg = str(exc).replace(f' "tmp/{ctx.message.author.id}.yaml",', "")
            await send_msg(
                ctx,
                title="Err: Improper Requirement File",
                description=[
                    "Requirements file cannot be parsed",
                    "",
                    f"{msg}",
                    "",
                    "Please use !req upload <file> once fixed",
                ],
            )
            tmp_fp.unlink(missing_ok=True)
            return

        shutil.copy(tmp_fp, fp)

        if len(cookies) > 10:
            await send_msg(
                ctx,
                title="Err: Improper Requirement File",
                description=[
                    "Requirements file cannot have more than 10 cookies",
                    "Please use !req upload <file> to upload a file",
                ],
            )
            fp.unlink(missing_ok=True)
            return

        tmp = sanitize(fp, ctx.message.author.id, rem_leaderboard=not default_mode)
        shutil.copy(tmp, fp)
        tmp.unlink(missing_ok=True)

        if target:
            tqdm.write(
                f"{datetime.now().isoformat(sep=' ', timespec='seconds')} : Mod {ctx.message.author} uploaded {req_file.filename} to {target}"
            )

        await send_msg(
            ctx,
            title="Uploaded Requirements File",
            description=[
                "\n".join(str(cookie) for cookie in cookies),
                "",
                "```Your requirements file has been uploaded",
                "",
                "Feel free to optimize with it```",
            ]
            + ([f"<@{target.id}>"] if target else []),
            wrap=False,
            thumbnail=False,
        )

    @req.command(name="delete", aliases=["del"], brief="Delete", description="Delete a requirements file you own")
    async def req_delete(self, ctx):
        await self.common_delete(ctx)

    @default.command(name="delete", aliases=["del"], brief="Delete", description="Delete a default requirements file")
    async def def_delete(self, ctx):
        await self.common_delete(ctx, default_mode=True)

    @staticmethod
    async def common_delete(ctx, default_mode=False):
        options = (
            await filter_requirements_files(ctx, include_default=False)
            if not default_mode
            else await filter_requirements_files(ctx, include_personal=False)
        )

        reqs_view = RequirementView()
        await reqs_view.start(ctx, options, "What requirement file do you want to delete?", is_multi=True)

        timeout = await reqs_view.wait()
        if timeout or not reqs_view.result:
            return

        for fp in reqs_view.result:
            requirements_fp = Path(fp)

            if requirements_fp.parent != REQS_PATH or not (
                default_mode or requirements_fp.stem.startswith(f"{ctx.message.author.id}-")
            ):
                return

            requirements_fp.unlink(missing_ok=True)

        await send_msg(
            ctx,
            title="Deleted Requirements File(s)",
            description=[
                "Your requirements files have been deleted",
                "",
                "Feel free to make a new one and upload it",
            ],
        )
