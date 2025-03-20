"""
UtilsCog Module

This module defines a utility cog for the Discord bot, providing common helper commands.
It includes commands such as 'ping' to check the bot's latency.
"""

import discord
from discord.ext import commands

class UtilsCog(commands.Cog):
    """
    A Cog that contains utility commands for the bot.

    Attributes:
        bot (commands.Bot): The instance of the Discord bot.
    
    Commands:
        ping: Checks and displays the bot's current latency.
    """
    
    def __init__(self, bot):
        """
        Initializes the UtilsCog with the provided Discord bot instance.

        Args:
            bot (commands.Bot): The Discord bot instance.
        """
        self.bot = bot

    @commands.command(name="ping", description="Check the bot's latency.")
    async def ping(self, ctx):
        """
        Responds with the bot's latency in milliseconds.

        This command calculates the current latency of the bot, rounds it to the nearest integer,
        and sends a message displaying the latency.

        Args:
            ctx (commands.Context): The context of the command invocation.
        """
        latency = round(self.bot.latency * 1000)
        await ctx.send(f"Pong! Latency: {latency}ms")

async def setup(bot):
    """
    Sets up the UtilsCog for the Discord bot.

    This function is used by the bot's extension loader to add the UtilsCog to the bot.

    Args:
        bot (commands.Bot): The instance of the Discord bot.
    """
    await bot.add_cog(UtilsCog(bot))
