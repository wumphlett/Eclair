import traceback
from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any, List, Optional

import discord
from discord import ButtonStyle, ChannelType
from discord.ext import commands
from discord.ui import Button, ChannelSelect, Modal, Select, TextInput, View

from topping_bot.optimize.toppings import Topping
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


@dataclass
class ThreadSave:
    jump_url: str
    default_name: str
    user_id: int


class ThreadSaveModal(Modal):
    def __init__(self, save: ThreadSave):
        super().__init__(title="Save Your Optimization")

        self.save = save
        self.save_input = TextInput(
            label="Set Name",
            placeholder="Provide a name for the set",
            default=save.default_name,
            max_length=50,
        )
        self.add_item(self.save_input)

    async def on_submit(self, interaction: discord.Interaction):
        fp = DATA_PATH / f"{self.save.user_id}-save.json"
        if fp.exists():
            with open(fp) as f:
                saves = json.load(f)
        else:
            saves = {}

        if len(saves) >= 25:
            embed = await new_embed(
                title="Err: Too Many Saves",
                description=["You have too many topping sets saved", "", "Please use '!optimize delete' and try again"],
            )
            return await interaction.response.send_message(embed=embed, ephemeral=True)

        saves[self.save.jump_url] = self.save_input.value

        with open(fp, "w") as f:
            json.dump(saves, f, indent=4)

        embed = await new_embed(
            title="Save Success!",
            description=f"Your set is now viewable with '!optimize load' under '{self.save_input.value}'",
        )
        return await interaction.response.send_message(embed=embed, ephemeral=True)

    async def on_error(self, interaction, error: Exception, /) -> None:
        traceback.print_exc()


class RemoveToppingsMenu(View):
    ctx: Any
    messages: List
    page: List
    pages: List
    end_screen: Any
    message: Any
    cur_page: int
    total_page_count: int

    solve: bool
    thread: Any
    save: ThreadSave

    fp: Path
    toppings: List[Topping]

    prev_button: Any
    page_counter: Any
    next_button: Any
    save_button: Any
    yes_button: Any
    no_button: Any

    result: bool

    def __init__(self, *, timeout: Optional[int] = 60):
        super().__init__(timeout=timeout)
        self.pages = None
        self.messages = None
        self.inner = False

    async def start(self, ctx, pages=None, messages=None, solve=False, thread=None, save: ThreadSave = None):
        if isinstance(ctx, discord.Interaction):
            ctx = await commands.Context.from_interaction(ctx)

        self.ctx = ctx
        self.solve = solve
        self.thread = thread
        self.save = save

        if pages:
            self.messages = messages
            self.pages = [
                await new_embed(
                    title="**Delete Selected Toppings**",
                    description="Would you like to remove the selected toppings from your inventory?",
                    image=image,
                    thumbnail=False,
                )
                for image in pages
            ]
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

        else:
            if solve:
                self.page = await new_embed(
                    title="**Remove Used Toppings?**",
                    description="Would you like to remove the used toppings from your inventory?",
                    thumbnail=False,
                )
            else:
                self.page = await new_embed(
                    title="**Delete Topping Inventory**",
                    description="Would you like to remove all toppings from your inventory?",
                    thumbnail=False,
                )

        self.yes_button = Button(label="Remove", style=ButtonStyle.danger, row=1)
        self.yes_button.callback = self.yes_button_callback
        self.no_button = Button(label="Keep", style=ButtonStyle.gray, row=1)
        self.no_button.callback = self.no_button_callback

        if self.save:
            self.save_button = Button(label="Save Set", style=ButtonStyle.success, row=1)
            self.save_button.callback = self.save_button_callback
            self.add_item(self.save_button)

        self.add_item(self.no_button)
        self.add_item(self.yes_button)

        send_mode = ctx.reply if not thread else thread.send
        if pages:
            self.message = await send_mode(embed=self.pages[self.cur_page], view=self)
        else:
            self.message = await send_mode(embed=self.page, view=self)

    async def previous(self):
        self.cur_page = self.cur_page - 1 if self.cur_page != 0 else self.total_page_count - 1

        self.page_counter.label = f"{self.cur_page + 1}/{self.total_page_count}"
        await self.message.edit(embed=self.pages[self.cur_page], view=self)

    async def next(self):
        self.cur_page = self.cur_page + 1 if self.cur_page != self.total_page_count - 1 else 0

        self.page_counter.label = f"{self.cur_page + 1}/{self.total_page_count}"
        await self.message.edit(embed=self.pages[self.cur_page], view=self)

    async def yes(self, interaction):
        if not self.inner:
            if self.pages:
                self.remove_item(self.prev_button)
                self.remove_item(self.page_counter)
                self.remove_item(self.next_button)
                await self.message.edit(
                    embed=await new_embed(
                        title="**CONFIRM TOPPING DELETION**",
                        description="ARE YOU SURE YOU WANT TO REMOVE SELECTED TOPPINGS FROM YOUR INVENTORY?",
                        thumbnail=False,
                    ),
                    view=self,
                )
            else:
                if self.solve:
                    await self.message.edit(
                        embed=await new_embed(
                            title="**CONFIRM USED TOPPING DELETION**",
                            description="ARE YOU SURE YOU WANT TO REMOVE THE USED TOPPINGS FROM YOUR INVENTORY?",
                            thumbnail=False,
                        ),
                        view=self,
                    )
                else:
                    await self.message.edit(
                        embed=await new_embed(
                            title="**CONFIRM INVENTORY DELETION**",
                            description="ARE YOU SURE YOU WANT TO REMOVE ALL TOPPINGS FROM YOUR INVENTORY?",
                            thumbnail=False,
                        ),
                        view=self,
                    )
            self.inner = True
            await interaction.response.defer()
        else:
            self.result = True
            self.end_screen = await new_embed(
                title="**Inventory Updated**",
                description="Your topping inventory has been updated",
                thumbnail=False,
            )
            self.stop()
            await self.cleanup()

    async def no(self, interaction):
        self.result = False
        self.end_screen = await new_embed(
            title="**Inventory Unchanged**",
            description="Your topping inventory remains unchanged",
            thumbnail=False,
        )
        self.stop()
        await self.cleanup()

    async def save_call(self, interaction):
        await interaction.response.send_modal(ThreadSaveModal(self.save))

    async def cleanup(self):
        if self.messages:
            for message in self.messages:
                await message.delete()
        if self.end_screen:
            if self.pages and not self.inner:
                self.remove_item(self.prev_button)
                self.remove_item(self.page_counter)
                self.remove_item(self.next_button)
            self.remove_item(self.yes_button)
            self.remove_item(self.no_button)
            await self.message.edit(embed=self.end_screen, view=None)
        else:
            await self.message.delete()

    async def on_timeout(self):
        await self.cleanup()

    async def on_error(self, interaction, error, item):
        await self.cleanup()

    async def prev_button_callback(self, interaction: discord.Interaction):
        if interaction.user != self.ctx.author:
            embed = await new_embed(
                title="Hey!", description="This is not your topping inventory!", color=discord.Colour.red()
            )
            return await interaction.response.send_message(embed=embed, ephemeral=True)
        await self.previous()
        await interaction.response.defer()

    async def next_button_callback(self, interaction: discord.Interaction):
        if interaction.user != self.ctx.author:
            embed = await new_embed(
                title="Hey!", description="This is not your topping inventory!", color=discord.Colour.red()
            )
            return await interaction.response.send_message(embed=embed, ephemeral=True)
        await self.next()
        await interaction.response.defer()

    async def yes_button_callback(self, interaction: discord.Interaction):
        if interaction.user != self.ctx.author:
            embed = await new_embed(
                title="Hey!", description="This is not your topping inventory!", color=discord.Colour.red()
            )
            return await interaction.response.send_message(embed=embed, ephemeral=True)
        await self.yes(interaction)

    async def no_button_callback(self, interaction: discord.Interaction):
        if interaction.user != self.ctx.author:
            embed = await new_embed(
                title="Hey!", description="This is not your topping inventory!", color=discord.Colour.red()
            )
            return await interaction.response.send_message(embed=embed, ephemeral=True)
        await self.no(interaction)

    async def save_button_callback(self, interaction: discord.Interaction):
        if interaction.user != self.ctx.author:
            embed = await new_embed(
                title="Hey!", description="This is not your topping inventory!", color=discord.Colour.red()
            )
            return await interaction.response.send_message(embed=embed, ephemeral=True)
        await self.save_call(interaction)


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


class SaveSelect(Select):
    def __init__(self, options, max_values):
        super().__init__(placeholder="Select a Saved Set", options=options[:25], max_values=max_values)


class SaveView(View):
    ctx: Any
    message: Any

    save_select: Any

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

        self.save_select = SaveSelect(options=options, max_values=max_values)
        self.save_select.callback = self.select_callback

        self.add_item(self.save_select)

        self.message = await ctx.reply(
            embed=await new_embed(
                title="Select Saved Set",
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
                title="Hey!", description="This is not your save selection!", color=discord.Colour.red()
            )
            return await interaction.response.send_message(embed=embed, ephemeral=True)

        if self.is_multi:
            self.result = self.save_select.values
        else:
            self.result = self.save_select.values[0]
        self.stop()
        self.ctx = await commands.Context.from_interaction(interaction)
        await interaction.response.defer()
        await self.cleanup()
