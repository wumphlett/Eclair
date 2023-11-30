import asyncio
import os

from discord import Intents
from discord.ext.commands import Bot as BaseBot

from topping_bot.cogs.community import Community
from topping_bot.cogs.cookies import Cookies
from topping_bot.cogs.guilds import Guilds
from topping_bot.cogs.inventory import Inventory
from topping_bot.cogs.requirement_files import RequirementFiles
from topping_bot.cogs.stats import Stats
from topping_bot.cogs.utility import Utility
from topping_bot.util.cooldown import PULL_USER_1_PER_3S, PULL_MEMBER_5_PER_DAY, PULL_USER_50_PER_DAY
from topping_bot.util.help import BotHelpCommand


class Bot(BaseBot):
    async def close(self):
        PULL_USER_1_PER_3S.save()
        PULL_MEMBER_5_PER_DAY.save()
        PULL_USER_50_PER_DAY.save()
        return await super().close()


async def main():
    intents = Intents.all()
    intents.presences = False
    bot = Bot(command_prefix="!", intents=intents)
    async with bot:
        await bot.add_cog(Inventory(bot))
        await bot.add_cog(Utility(bot))
        await bot.add_cog(Guilds(bot))
        await bot.add_cog(Cookies(bot))
        await bot.add_cog(Stats(bot))
        await bot.add_cog(RequirementFiles(bot))
        community = Community(bot)
        await bot.add_cog(community)
        bot.help_command = BotHelpCommand()
        bot.help_command.cog = community
        bot.owner_id = 389884580812947459
        await bot.start(os.getenv("DISCORD_API_TOKEN"))


if __name__ == "__main__":
    asyncio.run(main())
