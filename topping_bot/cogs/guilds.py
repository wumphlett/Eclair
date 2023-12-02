import traceback
from collections import defaultdict
from datetime import datetime
import yaml

from tqdm import tqdm

from discord.ext import commands, tasks
from discord.ext.commands import Cog

from topping_bot.crk.guild import Guild
from topping_bot.util.common import admin_only, approved_guild_only, new_embed, send_msg
from topping_bot.util.const import CONFIG, CONFIG_FILE, DEBUG, GUILD_PATH, STATIC_PATH
from topping_bot.ui.common import Paginator


class Guilds(Cog, description="The guild commands available to you"):
    def __init__(self, bot):
        self.bot = bot
        self.dev_server = None
        Guild.update()

    def cog_check(self, ctx):
        return approved_guild_only(ctx) and admin_only(ctx)

    # async def member_update(self, member, role, info):
    #     guild_server = await self.bot.fetch_guild(info["server"])
    #     if not guild_server:
    #         return
    #
    #     try:
    #         guild_member = await guild_server.fetch_member(member.id)
    #     except:
    #         return
    #
    #     dev_server_role = self.dev_server.get_role(role)
    #
    #     if member.get_role(role):
    #         if not (guild_member and guild_member.get_role(info["role"])):
    #             await member.remove_roles(dev_server_role, reason=f"No longer a member of {guild_server}")
    #     else:
    #         if guild_member and guild_member.get_role(info["role"]):
    #             await member.add_roles(dev_server_role, reason=f"Now a member of {guild_server}")

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
        pass  # TODO if joining a subscribed server, add app. roles
        # if member.guild == self.dev_server:
        #     for role, info in CONFIG["guilds"].items():
        #         await self.member_update(member, role, info)

    @Cog.listener()
    async def on_member_update(self, before, after):
        pass  # TODO if in subscribed server, add/rem app. roles
        # if self.dev_server.get_member(after.id):
        #     member = await self.dev_server.fetch_member(after.id)
        #     for role, info in CONFIG["guilds"].items():
        #         await self.member_update(member, role, info)

    @Cog.listener()
    async def on_raw_member_remove(self, member):
        pass  # TODO if in subscribed server, rem app. roles
        # if self.dev_server.get_member(member.id):
        #     member = await self.dev_server.fetch_member(member.id)
        #     for role, info in CONFIG["guilds"].items():
        #         await self.member_update(member, role, info)

    @tasks.loop(hours=24)
    async def autoguilds(self):
        tqdm.write(f"{datetime.now().isoformat(sep=' ', timespec='seconds')} : Beginning Auto-guilds")

        Guild.update()
        all_tracked_roles = set(guild.name for guild in Guild.supported)

        role_members = {}
        for guild in Guild.supported:
            if guild.is_special:
                continue
            try:
                server = self.bot.get_guild(guild.server)
                role_members[guild] = set(server.get_role(guild.role).members)
            except:
                pass  # TODO tracked roles error messages

        # TODO Don't auto role in the source server

        # TODO Error msgs to subscribed servers & tracked roles
        for server in Guild.subscribed_servers:
            server_fp = GUILD_PATH / f"{server}.yaml"
            if not server_fp.exists():

                subbed_server = await self.bot.fetch_guild(server)
                index = await subbed_server.create_role(name="== ECLAIR MANAGED BELOW ==")
                with open(server_fp, "w") as f:
                    yaml.safe_dump({"utility": {"index": index.id, "error-msgs": None}, "roles": {}}, f)

            with open(server_fp) as f:
                server_info = yaml.safe_load(f)

            # TODO booted from server
            server = await self.bot.fetch_guild(server)
            await server.fetch_roles()
            index = server.get_role(server_info["utility"]["index"])

            roles = []
            use_icons = "ROLE_ICONS" in server.features
            for guild in Guild.supported:
                if not guild.is_special and guild.name not in server_info["roles"] and guild.server != server.id:
                    if use_icons and guild.icon:
                        with open(
                            STATIC_PATH / "misc" / "guild" / f"guild_emblem_{f'{guild.icon}'.zfill(2)}.png", "rb"
                        ) as f:
                            role = await server.create_role(
                                name=guild.name, colour=guild.color, display_icon=f.read(), reason="Now tracking role"
                            )
                    else:
                        role = await server.create_role(name=guild.name, colour=guild.color, reason="Now tracking role")

                    roles.append(role)
                    server_info["roles"][guild.name] = role.id
                elif guild.name in server_info["roles"]:
                    roles.append(server.get_role(server_info["roles"][guild.name]))

            deleted_roles = [(role, role_id) for role, role_id in server_info["roles"].items() if role not in all_tracked_roles]
            for role, role_id in deleted_roles:
                untracked_role = server.get_role(role_id)
                await untracked_role.delete(reason="No longer tracked")
                server_info["roles"].pop(role)

            # TODO try catch error msg
            await server.edit_role_positions({role: index.position - 1 for role in roles})

            with open(server_fp, "w") as f:
                yaml.safe_dump(server_info, f)

            all_server_members = set([member async for member in server.fetch_members()])

            server = self.bot.get_guild(server.id)
            server_role_members = {}
            for guild in Guild.supported:
                # TODO try catch deleted role
                if guild.server == server.id:
                    continue
                if guild.is_special:
                    continue
                server_role_members[guild] = set(server.get_role(server_info["roles"][guild.name]).members)

            for role, tracked_members in role_members.items():
                for member in tracked_members:
                    if role.server != server.id and member in all_server_members and member not in server_role_members[role]:
                        member = await server.fetch_member(member.id)
                        await member.add_roles(server.get_role(server_info["roles"][role.name]), reason=f"Now a member of {role.name}")

            for role, tracked_members in server_role_members.items():
                for member in tracked_members:
                    if role.server != server.id and member not in role_members[role]:
                        member = await server.fetch_member(member.id)
                        await member.add_roles(server.get_role(server_info["roles"][role.name]), reason=f"No longer a member of {role.name}")

        # TODO Create channel if needed
        tqdm.write(f"{datetime.now().isoformat(sep=' ', timespec='seconds')} : Completed Auto-guilds")

    @autoguilds.before_loop
    async def before_autoguilds(self):
        await self.bot.wait_until_ready()

    @commands.command(brief="Guilds", description="Guilds")
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

    @commands.command(brief="Reconfig", description="Reconfig")
    async def reconfig(self, ctx):
        with open(CONFIG_FILE, encoding="utf-8") as f:
            CONFIG.update(yaml.safe_load(f))
        if not DEBUG:
            self.autoguilds.cancel()
            self.autoguilds.start()
        await send_msg(
            ctx,
            title=f"Successful Reconfig",
            description="Saved config restarted and guild roles have been updated",
            thumbnail=False,
        )
