from pathlib import Path
from typing import Optional, Union

import discord
from discord import Color, Embed, Interaction, SelectOption
from discord.ext.commands import Context

from topping_bot.crk.guild import Guild
from topping_bot.util.const import CONFIG, DEBUG, ECLAIR_GREEN, REQS_PATH


async def guild_only(ctx):
    return DEBUG or bool(ctx.guild)


async def dm_only(ctx):
    return DEBUG or not bool(ctx.guild)


def moderator_only(ctx, member_id=None):
    guild = approved_guild_ctx(ctx, member_id=member_id)
    return guild and (
        DEBUG
        or ctx.message.author.id == ctx.bot.owner_id
        # TODO mod roles need to become a server & role pair
        or bool(ctx.guild.get_member(ctx.message.author.id).get_role(guild.mod))
        or bool(ctx.bot.get_guild(guild.server).get_member(ctx.message.author.id).get_role(guild.mod))
    )


def admin_only(ctx):
    return ctx.bot.is_owner(ctx.author)


def server_admin_only(ctx):
    return ctx.guild and ctx.message.author.guild_permissions.administrator


def approved_guild_only(ctx):
    return approved_guild_ctx(ctx) is not None


def approved_guild_ctx(ctx, member_id=None):
    member_id = member_id if member_id is not None else ctx.message.author.id
    if DEBUG:
        for guild in Guild.supported:
            if guild.name == CONFIG["debug"]:
                return guild
        raise Exception("invalid debug name set")
    elif ctx.guild:
        possible_guilds = [guild for guild in Guild.optimizers if ctx.channel.id in guild.channels]
        for guild in possible_guilds:
            server = ctx.bot.get_guild(guild.server)
            if member_id == ctx.bot.owner_id:
                return guild
            elif (member := server.get_member(member_id)) is not None and (
                member.get_role(guild.role) or any(member.get_role(role) for role in guild.roles)
            ):
                return guild
        if member_id == ctx.bot.owner_id:
            for guild in Guild.supported:
                if guild.name == CONFIG["debug"]:
                    return guild
            raise Exception("invalid debug name set")
    else:
        for guild in Guild.optimizers:
            member = ctx.bot.get_guild(guild.server).get_member(member_id)
            if member is not None and (
                member.get_role(guild.role) or any(member.get_role(role) for role in guild.roles)
            ):
                return guild


async def new_embed(
    title: Optional[str] = None,
    image: Optional[str] = None,
    description: Optional[Union[list, str]] = "",
    footer: Optional[str] = None,
    wrap: bool = True,
    thumbnail: Union[bool, Path] = True,
    color: Color = Color.from_rgb(*ECLAIR_GREEN),
):
    if type(description) == list:
        description = "\n".join(description)
    if description and wrap:
        description = "```\n" + description + "```"
    embed = Embed(title=title, description=description, colour=color).set_image(url=image)
    if isinstance(thumbnail, Path):
        embed.set_thumbnail(url=f"attachment://{thumbnail.name}")
    elif thumbnail:
        embed.set_thumbnail(url=CONFIG["static"]["thumbnail"])
    if footer:
        embed.set_footer(text=footer, icon_url=CONFIG["static"]["icon"])
    return embed


async def send_msg(
    ctx: Union[Context, Interaction],
    title: Optional[str] = None,
    image: Optional[str] = None,
    description: Optional[Union[list, str]] = None,
    footer: Optional[str] = None,
    wrap: bool = True,
    thumbnail: Union[bool, Path] = True,
    thread: discord.Thread = None,
):
    thumbnail_img = discord.File(thumbnail, filename=thumbnail.name) if isinstance(thumbnail, Path) else None
    if thread:
        return await thread.send(
            embed=await new_embed(title, image, description, footer, wrap, thumbnail), file=thumbnail_img
        )
    elif type(ctx) == Context:
        return await ctx.reply(
            embed=await new_embed(title, image, description, footer, wrap, thumbnail), file=thumbnail_img
        )
    else:
        return await ctx.response.send_message(
            embed=await new_embed(title, image, description, footer, wrap, thumbnail), file=thumbnail_img
        )


async def edit_msg(
    msg,
    title: Optional[str] = None,
    image: Optional[str] = None,
    description: Optional[Union[list, str]] = None,
    footer: Optional[str] = None,
    wrap: bool = True,
):
    await msg.edit(embed=await new_embed(title, image, description, footer, wrap))


async def filter_requirements_files(ctx, include_default=True, include_personal=True, override_user=None):
    user_id = override_user.id if override_user else ctx.message.author.id
    guild = approved_guild_ctx(ctx, member_id=user_id)

    requirement_files = []
    for child in REQS_PATH.iterdir():
        if not child.is_file():
            continue
        elif include_personal and child.stem.startswith(f"{user_id}-"):
            requirement_files.append(child)
        elif include_default and child.stem.startswith(f"{guild.fp}-"):
            requirement_files.append(child)
    requirement_files.sort(key=lambda x: (not x.stem.startswith(f"{guild.fp}-"), x.stem))

    options = []

    for reqs in requirement_files:
        name = guild.sanitize(reqs.stem, user_id)

        options.append(
            SelectOption(
                label=name,
                value=str(reqs),
                emoji=guild.choose_emoji(reqs.stem),
            )
        )

    return options


async def find_member(ctx, name: str):
    if DEBUG:
        return await ctx.bot.fetch_user(int(name))
    if not ctx.guild:
        return None
    member = ctx.guild.get_member_named(name)
    if not member:
        if name.isdigit():
            member = ctx.guild.get_member(int(name))
            if member is not None:
                return member
            else:
                await send_msg(ctx, title="Err: Find User", description=f"No member found with the id {name}")
                return None
        if name.startswith("<@"):
            member = ctx.guild.get_member(int(name[2:-1]))
            if member is not None:
                return member
            else:
                await send_msg(ctx, title="Err: Find User", description=f"No member found with the id {name[2:-1]}")
                return None
        members = [
            member
            for member in ctx.guild.members
            if name.lower() in member.name.lower() or (member.nick and name.lower() in member.nick.lower())
        ]
        if len(members) == 0:
            await send_msg(ctx, title="Err: Find User", description=f"No member found with the name {name}")
            return None
        elif len(members) > 1:
            await send_msg(ctx, title="Err: Find User", description=f"Too many members found with the name {name}")
            return None
        else:
            member = members[0]
    return member
