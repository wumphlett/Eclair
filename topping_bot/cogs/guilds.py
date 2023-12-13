import asyncio
import traceback
from collections import defaultdict
import contextlib
from datetime import datetime
from typing import Callable
import yaml

from tqdm import tqdm

from discord.ext import commands, tasks
from discord.ext.commands import Cog

from topping_bot.crk.guild import Guild
from topping_bot.util.common import (
    admin_only,
    approved_guild_only,
    edit_msg,
    guild_only,
    new_embed,
    send_msg,
    server_admin_only,
)
from topping_bot.util.const import CONFIG, DEBUG, GUILD_PATH, STATIC_PATH
from topping_bot.ui.common import AutoGuildSetup, Paginator


async def entrap_errors(throwable_function: Callable, on_error_function: Callable):
    try:
        await throwable_function()
    except:
        traceback.print_exc()
        with contextlib.suppress(Exception):
            await on_error_function()


class Guilds(Cog, description="The guild commands available to you"):
    def __init__(self, bot):
        self.bot = bot
        self.dev_server = None
        Guild.update()

    @Cog.listener()
    async def on_ready(self):
        self.dev_server = self.bot.get_guild(CONFIG["community"]["dev-server"])
        if not DEBUG:
            self.autoguilds.start()

    @Cog.listener()
    async def on_guild_join(self, guild):
        owner = (await self.bot.application_info()).owner
        await owner.send(
            embed=await new_embed(title="Joined Guild", description=f"{guild} - {guild.owner} ({guild.member_count})")
        )

        if guild.member_count >= 10:
            channel = await self.bot.fetch_channel(CONFIG["stats"]["join"])
            await channel.send(
                embed=await new_embed(
                    title="Joined Guild!",
                    description=[
                        "```",
                        "The Eclair Bot has joined a new guild!",
                        "```",
                        "https://eclair.community/add-bot",
                    ],
                    wrap=False,
                )
            )

        channel = await self.bot.fetch_channel(CONFIG["stats"]["server"])
        await channel.edit(name=f"Server Count: {len(self.bot.guilds):,}")

        channel = await self.bot.fetch_channel(CONFIG["stats"]["user"])
        await channel.edit(name=f"User Count: {sum(guild.member_count for guild in self.bot.guilds):,}")

    @Cog.listener()
    async def on_guild_remove(self, guild):
        owner = (await self.bot.application_info()).owner
        await owner.send(embed=await new_embed(title="Left Guild", description=f"{guild}"))

    @Cog.listener()
    async def on_member_join(self, member):
        if member.guild.id in Guild.subscribed_servers:
            owner = (await self.bot.application_info()).owner
            server_info = Guild.load_subscribed_server_info(member.guild.id)

            for guild in (
                guild
                for guild in Guild.supported
                if (not guild.is_special or member.guild.id == CONFIG["community"]["dev-server"])
            ):
                tracked_server = self.bot.get_guild(guild.server)
                if tracked_server is None:
                    await owner.send(
                        embed=await new_embed(title="Invalid Server", description=f"{guild.name} server is missing")
                    )
                    return

                tracked_role = tracked_server.get_role(guild.role)
                if tracked_role is None:
                    await owner.send(
                        embed=await new_embed(title="Invalid Role", description=f"{guild.name} role is missing")
                    )
                    return

                if member in tracked_role.members:

                    async def add_roles():
                        await member.add_roles(
                            member.guild.get_role(server_info["roles"][guild.name]),
                            reason=f"Now a member of {guild.name}",
                        )

                    async def add_roles_error():
                        error_channel = await self.bot.fetch_channel(server_info["utility"]["error-msgs"])
                        await error_channel.send(
                            embed=await new_embed(
                                title="Err: Member Join", description=f"Could not add {member} to {guild.name}"
                            )
                        )

                    await entrap_errors(add_roles, add_roles_error)

    @Cog.listener()
    async def on_member_update(self, before, after):
        if after.guild.id in Guild.tracked_servers:
            before_roles, after_roles = set(role.id for role in before.roles), set(role.id for role in after.roles)
            for tracked_role in Guild.tracked_servers[after.guild.id]:
                if tracked_role.role in after_roles and tracked_role.role not in before_roles:
                    for server in (server for server in Guild.subscribed_servers if server != after.guild.id):
                        server_info = Guild.load_subscribed_server_info(server)

                        async def add_roles():
                            subscribed_server = await self.bot.fetch_guild(server)
                            if (member := subscribed_server.get_member(after.id)) is not None:
                                await member.add_roles(
                                    subscribed_server.get_role(server_info["roles"][tracked_role.name]),
                                    reason=f"Now a member of {tracked_role.name}",
                                )

                        async def add_roles_error():
                            error_channel = await self.bot.fetch_channel(server_info["utility"]["error-msgs"])
                            await error_channel.send(
                                embed=await new_embed(
                                    title="Err: Member Update",
                                    description=f"Could not update members of {tracked_role.name}",
                                )
                            )

                        await entrap_errors(add_roles, add_roles_error)
                elif tracked_role.role in before_roles and tracked_role.role not in after_roles:
                    for server in (server for server in Guild.subscribed_servers if server != after.guild.id):
                        server_info = Guild.load_subscribed_server_info(server)

                        async def remove_roles():
                            subscribed_server = await self.bot.fetch_guild(server)
                            if (member := subscribed_server.get_member(after.id)) is not None:
                                await member.remove_roles(
                                    subscribed_server.get_role(server_info["roles"][tracked_role.name]),
                                    reason=f"No longer a member of {tracked_role.name}",
                                )

                        async def remove_roles_error():
                            error_channel = await self.bot.fetch_channel(server_info["utility"]["error-msgs"])
                            await error_channel.send(
                                embed=await new_embed(
                                    title="Err: Member Update",
                                    description=f"Could not update members of {tracked_role.name}",
                                )
                            )

                        await entrap_errors(remove_roles, remove_roles_error)

    @Cog.listener()
    async def on_raw_member_remove(self, payload):
        if (removed_roles := Guild.tracked_servers.get(payload.guild_id)) is not None:
            for tracked_role in removed_roles:
                for server in (server for server in Guild.subscribed_servers if server != payload.guild_id):
                    server_info = Guild.load_subscribed_server_info(server)

                    async def remove_roles():
                        subscribed_server = await self.bot.fetch_guild(server)
                        if (member := subscribed_server.get_member(payload.user.id)) is not None:
                            await member.remove_roles(
                                subscribed_server.get_role(server_info["roles"][tracked_role.name]),
                                reason=f"No longer a member of {tracked_role.name}",
                            )

                    async def remove_roles_error():
                        error_channel = await self.bot.fetch_channel(server_info["utility"]["error-msgs"])
                        await error_channel.send(
                            embed=await new_embed(
                                title="Err: Member Remove",
                                description=f"Could not update removed members of {tracked_role.name}",
                            )
                        )

                    await entrap_errors(remove_roles, remove_roles_error)

    async def update_subscribed_server_config(self, server: int, error_msg_channel: int = None):
        server_fp = GUILD_PATH / f"{server}.yaml"
        subscribed_server = await self.bot.fetch_guild(server)
        owner = (await self.bot.application_info()).owner

        if subscribed_server is None:
            await owner.send(
                embed=await new_embed(title="Invalid Subscriber", description=f"Server ID: {server} cannot be found")
            )
            server_fp.unlink(missing_ok=True)
            return

        if server_fp.exists():
            with open(server_fp) as f:
                server_info = yaml.safe_load(f)
        else:
            server_info = {"utility": {"index": None, "error-msgs": None}, "roles": {}}

        index = server_info["utility"]["index"]
        if index is None or (index_role := subscribed_server.get_role(index)) is None:
            index_role = await subscribed_server.create_role(name="== ECLAIR MANAGED BELOW ==")
            server_info["utility"]["index"] = index_role.id

        if error_msg_channel:
            server_info["utility"]["error-msgs"] = error_msg_channel

        tracked_roles = {
            guild.name: guild for guild in Guild.supported if (not guild.is_special or server == CONFIG["community"]["dev-server"]) and guild.server != server
        }
        mirrored_roles = set(server_info["roles"].keys())

        use_icons = "ROLE_ICONS" in subscribed_server.features
        for missing_role in set(tracked_roles.keys()).difference(mirrored_roles):
            guild = tracked_roles[missing_role]
            if use_icons and guild.icon:
                with open(STATIC_PATH / "misc" / "guild" / f"guild_emblem_{f'{guild.icon}'.zfill(2)}.png", "rb") as f:
                    role = await subscribed_server.create_role(
                        name=guild.name, colour=guild.color, display_icon=f.read(), reason="Now tracking role"
                    )
            else:
                role = await subscribed_server.create_role(
                    name=guild.name, colour=guild.color, reason="Now tracking role"
                )
            server_info["roles"][missing_role] = role.id

        for untracked_role in mirrored_roles.difference(tracked_roles.keys()):
            role_to_remove = subscribed_server.get_role(server_info["roles"][untracked_role])
            if role_to_remove:
                await role_to_remove.delete(reason="No longer tracked")
            server_info["roles"].pop(untracked_role)

        with open(server_fp, "w") as f:
            yaml.safe_dump(server_info, f, sort_keys=False)

        async def reorder_roles():
            role_order = []
            await asyncio.sleep(3)  # need time to let created roles propagate
            full_role_list = await subscribed_server.fetch_roles()
            full_roles = {server_role.id: server_role for server_role in full_role_list}
            for guild in Guild.supported:
                if (
                    (not guild.is_special or server == CONFIG["community"]["dev-server"])
                    and server_info["roles"].get(guild.name)
                    and full_roles.get(server_info["roles"][guild.name])
                ):
                    role_order.append(full_roles.get(server_info["roles"][guild.name]))
            role_positions = {matched_role: index_role.position - i - 1 for i, matched_role in enumerate(role_order)}
            idx = index_role.position - len(role_positions) - 1
            full_role_list.sort(key=lambda x: -x.position)
            for existing_role in full_role_list[full_role_list.index(index_role) + 1 :]:
                if existing_role not in role_positions:
                    role_positions[existing_role] = idx
                    idx -= 1
            role_positions[index_role] = max(role_positions.values()) + 1
            await subscribed_server.edit_role_positions(role_positions)

        async def reorder_roles_error():
            error_channel = await self.bot.fetch_channel(server_info["utility"]["error-msgs"])
            await error_channel.send(
                embed=await new_embed(
                    title="Err: Move Roles",
                    description=[
                        "Could not move managed roles below '== ECLAIR MANAGED BELOW =='",
                        "",
                        "Please ensure Eclair's highest role is above '== ECLAIR MANAGED BELOW =='",
                    ],
                )
            )

        await entrap_errors(reorder_roles, reorder_roles_error)
        return server_info["roles"]

    @tasks.loop(hours=24)
    async def autoguilds(self):
        tqdm.write(f"{datetime.now().isoformat(sep=' ', timespec='seconds')} : Beginning Auto-guilds")

        Guild.update()
        tracked_members = {}
        owner = (await self.bot.application_info()).owner

        # tracked guilds
        # for guild in (guild for guild in Guild.supported if not guild.is_special):
        for guild in Guild.supported:
            server = self.bot.get_guild(guild.server)
            if server is None:
                await owner.send(
                    embed=await new_embed(title="Invalid Server", description=f"{guild.name} server is missing")
                )
                continue

            role = server.get_role(guild.role)
            if role is None:
                await owner.send(
                    embed=await new_embed(title="Invalid Role", description=f"{guild.name} role is missing")
                )
                continue

            await server.chunk()
            tracked_members[guild] = set(server.get_role(guild.role).members)

        # subscribed servers
        for server in Guild.subscribed_servers:
            mirrored_roles = await self.update_subscribed_server_config(server)
            if not mirrored_roles:
                continue

            subscribed_server = self.bot.get_guild(server)
            server_info = Guild.load_subscribed_server_info(subscribed_server.id)
            await subscribed_server.chunk()
            all_server_members = set([member for member in subscribed_server.members])

            for guild, members in tracked_members.items():
                if guild.server == server:
                    continue

                if guild.is_special and server != CONFIG["community"]["dev-server"]:
                    continue

                if subscribed_server.get_role(mirrored_roles[guild.name]) is None:
                    continue
                mirrored_members = set(subscribed_server.get_role(mirrored_roles[guild.name]).members)

                for add_member in members.difference(mirrored_members).intersection(all_server_members):

                    async def add_roles():
                        member = subscribed_server.get_member(add_member.id)
                        await member.add_roles(
                            subscribed_server.get_role(mirrored_roles[guild.name]),
                            reason=f"Now a member of {guild.name}",
                        )

                    async def add_roles_error():
                        error_channel = await self.bot.fetch_channel(server_info["utility"]["error-msgs"])
                        await error_channel.send(
                            embed=await new_embed(
                                title="Err: Daily Member Update",
                                description=f"Could not add members to {guild.name}",
                            )
                        )

                    await entrap_errors(add_roles, add_roles_error)

                for remove_member in mirrored_members.difference(members).intersection(all_server_members):

                    async def remove_roles():
                        member = subscribed_server.get_member(remove_member.id)
                        await member.remove_roles(
                            subscribed_server.get_role(mirrored_roles[guild.name]),
                            reason=f"No longer a member of {guild.name}",
                        )

                    async def remove_roles_error():
                        error_channel = await self.bot.fetch_channel(server_info["utility"]["error-msgs"])
                        await error_channel.send(
                            embed=await new_embed(
                                title="Err: Daily Member Update",
                                description=f"Could not add members to {guild.name}",
                            )
                        )

                    await entrap_errors(remove_roles, remove_roles_error)

        tqdm.write(f"{datetime.now().isoformat(sep=' ', timespec='seconds')} : Completed Auto-guilds")

    @autoguilds.before_loop
    async def before_autoguilds(self):
        await self.bot.wait_until_ready()

    @commands.group(
        aliases=["g"],
        checks=[guild_only, server_admin_only],
        brief="Guilds",
        description="Guilds",
        invoke_without_command=True,
    )
    async def guild(self, ctx):
        pass

    @guild.command(
        checks=[guild_only, server_admin_only], brief="Join auto-guilds", description="Subscribe to auto-guilds"
    )
    async def subscribe(self, ctx):
        if ctx.guild.id in Guild.subscribed_servers:
            await send_msg(
                ctx,
                title="Err: Server Already Subscribed",
                description=[
                    "Your server is already subscribed to auto-guilds",
                    "To change this, use !guild cancel",
                ],
            )
            return

        if not ctx.guild.me.guild_permissions.manage_roles:
            await send_msg(
                ctx,
                title="Err: Needs Manage Roles",
                description=[
                    "In order to subscribe to auto-guilds, the bot must have the 'Manage Roles' permission",
                    "",
                    "Please grant the bot this permission and try again",
                ],
            )
            return

        autoguild_setup = AutoGuildSetup()
        await autoguild_setup.start(ctx, None)

        timeout = await autoguild_setup.wait()
        if timeout or not autoguild_setup.result:
            return

        error_channel = await autoguild_setup.result.fetch()
        permissions = error_channel.permissions_for(ctx.guild.me)

        if not permissions.send_messages:
            await send_msg(
                ctx,
                title="Err: Cannot Send in Error Channel",
                description=[
                    "In order to subscribe to auto-guilds, the bot must be able to write messages in the specified error channel",
                    "",
                    "Please grant the bot this permission and try again",
                ],
            )
            return

        Guild.subscribed_servers.append(ctx.guild.id)
        Guild.dump_subscribed_servers()

        await send_msg(
            ctx,
            title="Successfully Subscribed to Auto-Guilds",
            description=[
                "Congratulations!",
                "",
                "You have successfully subscribed to auto-guilds",
                "Members of top-30 guilds will automatically be given roles in your server",
            ],
        )

        await self.update_subscribed_server_config(ctx.guild.id, error_channel.id)
        await self.autoguilds()

    @guild.command(checks=[guild_only, server_admin_only], brief="Leave auto-guilds", description="Cancel auto-guilds")
    async def cancel(self, ctx):
        server_fp = GUILD_PATH / f"{ctx.guild.id}.yaml"
        if not server_fp.exists():
            await send_msg(
                ctx,
                title="Err: Server Not Subscribed",
                description=[
                    "Your server is not subscribed to auto-guilds",
                    "To change this, use !guild subscribe",
                ],
            )
            return

        msg = await send_msg(
            ctx,
            title="Unsubscribing From Auto-guilds",
            description=[
                "Please wait...",
            ],
        )

        Guild.subscribed_servers = [server for server in Guild.subscribed_servers if server != ctx.guild.id]
        Guild.dump_subscribed_servers()

        with open(server_fp) as f:
            server_info = yaml.safe_load(f)
        for role in server_info["roles"].values():
            with contextlib.suppress(Exception):
                role_to_delete = ctx.guild.get_role(role)
                await role_to_delete.delete(reason="Unsubscribed from auto-guilds")
        with contextlib.suppress(Exception):
            index_role = ctx.guild.get_role(server_info["utility"]["index"])
            await index_role.delete(reason="Unsubscribed from auto-guilds")

        server_fp.unlink(missing_ok=True)
        # TODO delete index role, more specifically order created roles, and exactly where intended
        # TODO prevent fail to reorder row from firing on initial create
        # TODO fail to reorder still fires when roles aren't created

        await edit_msg(
            msg,
            title="Unsubscribed From Auto-guilds",
            description=[
                "Your server has successfully unsubscribed from auto-guilds",
                "To change this, use !guild subscribe",
            ],
        )

    @commands.command(checks=[admin_only], brief="List guilds", description="List guilds")
    async def guilds(self, ctx, idx: int = None, search: str = ""):
        guild_list = sorted(ctx.bot.guilds, key=lambda x: -x.member_count)
        if idx is not None:
            idx -= 1
            guild = guild_list[idx]
            roles = [role for role in guild.roles if search.lower() in role.name.lower()]
            await send_msg(
                ctx,
                title=f"{guild.name} ({guild.id})",
                description=["\nRoles:"] + [f"├ {role} ({role.id})" for role in roles],
                thumbnail=False,
            )
            return

        pages = []
        for i, group in enumerate(guild_list[i : i + 25] for i in range(0, len(guild_list), 25)):
            pages.append(
                await new_embed(
                    title=f"{ctx.bot.user.name} Guilds",
                    description=["All Active Guilds:"]
                    + [f"{i * 25 + j + 1}. {guild.name} ({guild.member_count})" for j, guild in enumerate(group)],
                    thumbnail=False,
                )
            )

        await Paginator().start(
            ctx,
            pages=pages,
        )
