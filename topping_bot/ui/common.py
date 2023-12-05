from pathlib import Path
from typing import Any, List, Optional

import discord
from discord import ButtonStyle, ChannelType
from discord.ext import commands
from discord.ui import Button, ChannelSelect, Select, View

from topping_bot.crk.toppings import Topping
from topping_bot.optimize.reader import write_toppings
from topping_bot.util.common import new_embed
from topping_bot.util.const import DATA_PATH


class RequirementSelect(Select):
    def __init__(self, options, max_values):
        super().__init__(placeholder="Select a Requirement List", options=options[:25], max_values=max_values)


class RequirementView(View):
    ctx: Any
    message: Any

    req_select: Any

    is_multi: bool
    result: str

    def __init__(self, *, timeout: int = 60):
        super().__init__(timeout=timeout)

    async def start(self, ctx, options, description, is_multi=False):
        if isinstance(ctx, discord.Interaction):
            ctx = await commands.Context.from_interaction(ctx)

        self.ctx = ctx
        self.is_multi = is_multi

        max_values = 1 if not is_multi else len(options)

        self.req_select = RequirementSelect(options=options, max_values=max_values)
        self.req_select.callback = self.select_callback

        self.add_item(self.req_select)

        self.message = await ctx.reply(
            embed=await new_embed(
                title="Select Requirements List",
                description=description,
            ),
            ephemeral=True,
            view=self,
        )

    async def cleanup(self):
        await self.message.delete()

    async def on_timeout(self):
        await self.cleanup()

    async def on_error(self, interaction, error, item):
        await self.cleanup()

    async def select_callback(self, interaction):
        if interaction.user != self.ctx.author:
            embed = await new_embed(
                title="Hey!", description="This is not your requirement selection!", color=discord.Colour.red()
            )
            return await interaction.response.send_message(embed=embed, ephemeral=True)

        if self.is_multi:
            self.result = self.req_select.values
        else:
            self.result = self.req_select.values[0]
        self.stop()
        self.ctx = await commands.Context.from_interaction(interaction)
        await interaction.response.defer()
        await self.cleanup()


class RequirementConfirm(View):
    ctx: Any
    message: Any

    optimize_button: Any
    cancel_button: Any

    result: bool

    def __init__(self, *, timeout: int = 60):
        super().__init__(timeout=timeout)

    async def start(self, ctx, description):
        if isinstance(ctx, discord.Interaction):
            ctx = await commands.Context.from_interaction(ctx)

        self.ctx = ctx

        self.optimize_button = Button(label="Optimize", style=ButtonStyle.gray)
        self.optimize_button.callback = self.optimize_button_callback
        self.cancel_button = Button(label="Cancel", style=ButtonStyle.danger)
        self.cancel_button.callback = self.cancel_button_callback

        self.add_item(self.optimize_button)
        self.add_item(self.cancel_button)

        self.message = await ctx.reply(
            embed=await new_embed(title="__**Confirm Requirements**__", description=description, wrap=False),
            ephemeral=True,
            view=self,
        )

    async def cleanup(self):
        await self.message.delete(delay=1)

    async def on_timeout(self):
        await self.cleanup()

    async def on_error(self, interaction, error, item):
        await self.cleanup()

    async def optimize(self):
        self.result = True
        self.stop()
        await self.cleanup()

    async def cancel(self):
        self.result = False
        self.stop()
        await self.cleanup()

    async def optimize_button_callback(self, interaction: discord.Interaction):
        if interaction.user != self.ctx.author:
            embed = await new_embed(
                title="Hey!", description="This is not your optimization!", color=discord.Colour.red()
            )
            return await interaction.response.send_message(embed=embed, ephemeral=True)
        await self.optimize()

    async def cancel_button_callback(self, interaction: discord.Interaction):
        if interaction.user != self.ctx.author:
            embed = await new_embed(
                title="Hey!", description="This is not your optimization!", color=discord.Colour.red()
            )
            return await interaction.response.send_message(embed=embed, ephemeral=True)
        await self.cancel()


class RemoveToppingsMenu(View):
    ctx: Any
    member: Any
    message: Any

    fp: Path
    toppings: List[Topping]

    yes_button: Any
    no_button: Any

    def __init__(self, *, timeout: Optional[int] = 60, inner: bool = False):
        super().__init__(timeout=timeout)
        self.inner = inner

    async def start(self, ctx, member, toppings: List[Topping], fp: Path):
        if isinstance(ctx, discord.Interaction):
            ctx = await commands.Context.from_interaction(ctx)

        self.ctx = ctx
        self.member = member

        self.toppings = toppings
        self.fp = fp

        self.yes_button = Button(label="Remove", style=ButtonStyle.danger)
        self.yes_button.callback = self.yes_button_callback
        self.no_button = Button(label="Keep", style=ButtonStyle.gray)
        self.no_button.callback = self.no_button_callback

        self.add_item(self.no_button)
        self.add_item(self.yes_button)

        if self.inner:
            title = "CONFIRM REMOVE TOPPINGS"
            desc = "ARE YOU SURE YOU WANT TO REMOVE THE USED TOPPINGS FROM YOUR INVENTORY?"
        else:
            title = "Remove Toppings?"
            desc = "Would you like to remove the used toppings from your inventory?"

        self.message = await ctx.reply(
            embed=await new_embed(
                title=title,
                description=desc,
            ),
            ephemeral=True,
            view=self,
        )

    async def yes(self, interaction):
        if not self.inner:
            self.stop()
            await self.cleanup()
            await RemoveToppingsMenu(timeout=self.timeout, inner=True).start(
                self.ctx, self.member, toppings=self.toppings, fp=self.fp
            )
        if self.inner:
            write_toppings(self.toppings, self.fp)
            embed = await new_embed(title="Toppings Updated", description="Your topping inventory has been updated")
            await interaction.response.send_message(embed=embed, ephemeral=True)
            self.stop()
            await self.cleanup()

    async def no(self, interaction):
        embed = await new_embed(title="Toppings Unchanged", description="Your topping inventory is unchanged")
        await interaction.response.send_message(embed=embed, ephemeral=True)
        self.stop()
        await self.cleanup()

    async def cleanup(self):
        await self.message.delete()

    async def on_timeout(self):
        await self.cleanup()

    async def on_error(self, interaction, error, item):
        await self.cleanup()

    async def yes_button_callback(self, interaction: discord.Interaction):
        if interaction.user != self.member:
            embed = await new_embed(
                title="Hey!", description="This is not your topping inventory!", color=discord.Colour.red()
            )
            return await interaction.response.send_message(embed=embed, ephemeral=True)
        await self.yes(interaction)

    async def no_button_callback(self, interaction: discord.Interaction):
        if interaction.user != self.member:
            embed = await new_embed(
                title="Hey!", description="This is not your topping inventory!", color=discord.Colour.red()
            )
            return await interaction.response.send_message(embed=embed, ephemeral=True)
        await self.no(interaction)


class Paginator(View):
    ctx: Any
    messages: List
    pages: List
    end_screen: Any
    message: Any
    cur_page: int
    total_page_count: int

    prev_button: Any
    page_counter: Any
    next_button: Any

    def __init__(self, *, timeout: int = 60):
        super().__init__(timeout=timeout)

    async def start(self, ctx, pages, end_screen=None, messages=None):
        if isinstance(ctx, discord.Interaction):
            ctx = await commands.Context.from_interaction(ctx)

        self.ctx = ctx

        self.messages = messages
        self.pages = pages
        self.end_screen = end_screen
        self.cur_page = 0
        self.total_page_count = len(pages)

        self.page_counter = Button(label=f"1/{self.total_page_count}", style=ButtonStyle.gray, disabled=True)

        self.prev_button = Button(label="Prev", style=ButtonStyle.primary)
        self.prev_button.callback = self.prev_button_callback
        self.next_button = Button(label="Next", style=ButtonStyle.primary)
        self.next_button.callback = self.next_button_callback

        self.add_item(self.prev_button)
        self.add_item(self.page_counter)
        self.add_item(self.next_button)

        self.message = await ctx.reply(embed=self.pages[self.cur_page], view=self)

    async def previous(self):
        self.cur_page = self.cur_page - 1 if self.cur_page != 0 else self.total_page_count - 1

        self.page_counter.label = f"{self.cur_page + 1}/{self.total_page_count}"
        await self.message.edit(embed=self.pages[self.cur_page], view=self)

    async def next(self):
        self.cur_page = self.cur_page + 1 if self.cur_page != self.total_page_count - 1 else 0

        self.page_counter.label = f"{self.cur_page + 1}/{self.total_page_count}"
        await self.message.edit(embed=self.pages[self.cur_page], view=self)

    async def cleanup(self):
        if self.messages:
            for message in self.messages:
                await message.delete()
        if self.end_screen:
            self.remove_item(self.prev_button)
            self.remove_item(self.page_counter)
            self.remove_item(self.next_button)
            await self.message.edit(embed=self.end_screen, view=None)
        else:
            await self.message.delete()

    async def on_timeout(self):
        await self.cleanup()

    async def on_error(self, interaction, error, item):
        await self.cleanup()

    async def prev_button_callback(self, interaction: discord.Interaction):
        if interaction.user != self.ctx.author:
            embed = await new_embed(title="Hey!", description="This is not your view!", color=discord.Colour.red())
            return await interaction.response.send_message(embed=embed, ephemeral=True)
        await self.previous()
        await interaction.response.defer()

    async def next_button_callback(self, interaction: discord.Interaction):
        if interaction.user != self.ctx.author:
            embed = await new_embed(title="Hey!", description="This is not your view!", color=discord.Colour.red())
            return await interaction.response.send_message(embed=embed, ephemeral=True)
        await self.next()
        await interaction.response.defer()


class OverwriteConfirm(View):
    ctx: Any
    message: Any

    target: Any

    approve_button: Any
    deny_button: Any

    result: bool

    def __init__(self, *, timeout: int = 60):
        super().__init__(timeout=timeout)

    async def start(self, ctx, target, description):
        if isinstance(ctx, discord.Interaction):
            ctx = await commands.Context.from_interaction(ctx)

        self.ctx = ctx
        self.target = target

        self.approve_button = Button(label="Approve", style=ButtonStyle.gray)
        self.approve_button.callback = self.approve_button_callback
        self.deny_button = Button(label="Deny", style=ButtonStyle.danger)
        self.deny_button.callback = self.deny_button_callback

        self.add_item(self.approve_button)
        self.add_item(self.deny_button)

        self.message = await ctx.reply(
            embed=await new_embed(title="Approve Overwrite?", description=description, wrap=False),
            ephemeral=True,
            view=self,
        )

    async def cleanup(self):
        await self.message.delete(delay=1)

    async def on_timeout(self):
        await self.cleanup()

    async def on_error(self, interaction, error, item):
        await self.cleanup()

    async def approve(self):
        self.result = True
        self.stop()
        await self.cleanup()

    async def deny(self):
        self.result = False
        self.stop()
        await self.cleanup()

    async def approve_button_callback(self, interaction: discord.Interaction):
        if interaction.user != self.target:
            embed = await new_embed(title="Hey!", description="This is not your req file!", color=discord.Colour.red())
            return await interaction.response.send_message(embed=embed, ephemeral=True)
        await self.approve()

    async def deny_button_callback(self, interaction: discord.Interaction):
        if interaction.user != self.target:
            embed = await new_embed(title="Hey!", description="This is not your req file!", color=discord.Colour.red())
            return await interaction.response.send_message(embed=embed, ephemeral=True)
        await self.deny()


class AutoGuildSetup(View):
    ctx: Any
    message: Any

    err_channel: Any
    result: Any

    def __init__(self, *, timeout: Optional[int] = 60):
        super().__init__(timeout=timeout)

    async def start(self, ctx, member):
        if isinstance(ctx, discord.Interaction):
            ctx = await commands.Context.from_interaction(ctx)

        self.ctx = ctx

        self.err_channel = ChannelSelect(placeholder="Mod Channel", channel_types=[ChannelType.text])
        self.err_channel.callback = self.err_channel_callback
        self.add_item(self.err_channel)

        self.message = await ctx.reply(
            embed=await new_embed(
                title="Auto-guilds Setup",
                description=[
                    "Welcome to Auto-Guilds!",
                    "By subscribing, supported members of top-30 guilds will automatically receive roles in your server.",
                    "",
                    "Please select a channel to be used to post error messages",
                    "",
                    "It is recommended that this is a mod only channel",
                ],
            ),
            ephemeral=True,
            view=self,
        )

    async def cleanup(self):
        self.stop()
        await self.message.delete(delay=1)

    async def on_timeout(self):
        await self.cleanup()

    async def on_error(self, interaction, error, item):
        await self.cleanup()

    async def err_channel_callback(self, interaction):
        if interaction.user != self.ctx.author:
            embed = await new_embed(
                title="Hey!", description="This is not your auto-guild setup!", color=discord.Colour.red()
            )
            return await interaction.response.send_message(embed=embed, ephemeral=True)

        self.result = self.err_channel.values[0]
        await self.cleanup()


class WipeDataMenu(View):
    ctx: Any
    member: Any
    message: Any

    yes_button: Any
    no_button: Any

    def __init__(self, *, timeout: Optional[int] = 60, inner: bool = False):
        super().__init__(timeout=timeout)
        self.inner = inner

    async def start(self, ctx, member):
        if isinstance(ctx, discord.Interaction):
            ctx = await commands.Context.from_interaction(ctx)

        self.ctx = ctx
        self.member = member

        self.yes_button = Button(label="Wipe", style=ButtonStyle.danger)
        self.yes_button.callback = self.yes_button_callback
        self.no_button = Button(label="Keep", style=ButtonStyle.gray)
        self.no_button.callback = self.no_button_callback

        self.add_item(self.no_button)
        self.add_item(self.yes_button)

        if self.inner:
            title = "CONFIRM DATA REMOVAL"
            desc = [
                "ARE YOU SURE YOU WANT TO REMOVE ALL USER DATA WITHIN THE BOT?",
                "",
                "WARNING: THIS ACTION CANNOT BE REVERSED",
            ]
        else:
            title = "Wipe All User Data?"
            desc = [
                "Would you like to delete all of your user data?",
                "",
                "This will delete gacha and topping data",
                "WARNING: THIS ACTION CANNOT BE REVERSED",
            ]

        self.message = await ctx.reply(
            embed=await new_embed(
                title=title,
                description=desc,
            ),
            ephemeral=True,
            view=self,
        )

    async def yes(self, interaction):
        if not self.inner:
            self.stop()
            await self.cleanup()
            await WipeDataMenu(timeout=self.timeout, inner=True).start(self.ctx, self.member)
        if self.inner:
            (DATA_PATH / f"{self.member.id}.csv").unlink(missing_ok=True)
            (DATA_PATH / f"{self.member.id}.json").unlink(missing_ok=True)
            embed = await new_embed(title="Data Wiped", description="Your user data has been removed")
            await interaction.response.send_message(embed=embed, ephemeral=True)
            self.stop()
            await self.cleanup()

    async def no(self, interaction):
        embed = await new_embed(title="Data Unchanged", description="Your user data is unchanged")
        await interaction.response.send_message(embed=embed, ephemeral=True)
        self.stop()
        await self.cleanup()

    async def cleanup(self):
        await self.message.delete()

    async def on_timeout(self):
        await self.cleanup()

    async def on_error(self, interaction, error, item):
        await self.cleanup()

    async def yes_button_callback(self, interaction: discord.Interaction):
        if interaction.user != self.member:
            embed = await new_embed(title="Hey!", description="This is not your menu!", color=discord.Colour.red())
            return await interaction.response.send_message(embed=embed, ephemeral=True)
        await self.yes(interaction)

    async def no_button_callback(self, interaction: discord.Interaction):
        if interaction.user != self.member:
            embed = await new_embed(title="Hey!", description="This is not your menu!", color=discord.Colour.red())
            return await interaction.response.send_message(embed=embed, ephemeral=True)
        await self.no(interaction)
