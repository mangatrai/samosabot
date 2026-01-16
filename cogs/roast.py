"""
RoastCog Module

This module defines the RoastCog for the Discord bot, providing roast commands that generate
witty, edgy, and humorous roasts using the OpenAI API. It supports both prefix commands and slash
commands, allowing users to request a roast aimed at a specified user. The roast prompt template is
retrieved from a central prompts module, and the generated roast is produced via openai_utils.
If no target user is specified, the command defaults to roasting the command invoker.

Usage:
  - Prefix command: !roast [user]
  - Slash command: /roast [user]
"""

import discord
from discord.ext import commands
from discord import app_commands
from utils import openai_utils
from configs import prompts

class RoastCog(commands.Cog):
    """
    A Discord Cog that provides roast functionality.

    This cog defines both a prefix command and a slash command for generating roasts.
    The commands format a roast prompt using a template from the prompts module, then
    call openai_utils to generate the roast, which is sent back to the channel.
    """

    def __init__(self, bot: commands.Bot):
        """
        Initialize the RoastCog with the given bot instance.

        Args:
            bot (commands.Bot): The Discord bot instance.
        """
        self.bot = bot

    @commands.command(name="roast")
    async def roast(self, ctx: commands.Context, user: discord.Member = None):
        """
        Generate a witty roast for a user using a prefix command.

        If no user is specified, the command roasts the command invoker.

        Args:
            ctx (commands.Context): The context of the command.
            user (discord.Member, optional): The user to roast.
        """
        async with ctx.typing():
            target = user.display_name if user else ctx.author.display_name
            prompt = prompts.roast_prompt.format(target=target)
            content = openai_utils.generate_openai_response(prompt)
            await ctx.send(f"🔥 {content}")

    @app_commands.command(name="roast", description="Generate a witty roast for a user.")
    @app_commands.describe(user="The user to roast (optional)")
    async def slash_roast(self, interaction: discord.Interaction, user: discord.Member = None):
        """
        Generate a witty roast for a user using a slash command.

        This command defers the interaction response to allow for processing time,
        then generates the roast using OpenAI and sends the result as a followup message.

        Args:
            interaction (discord.Interaction): The interaction object from Discord.
            user (discord.Member, optional): The user to roast.
        """
        await interaction.response.defer()
        target = user.display_name if user else interaction.user.display_name
        prompt = prompts.roast_prompt.format(target=target)
        content = openai_utils.generate_openai_response(prompt)
        await interaction.followup.send(f"🔥 {content}")

async def setup(bot: commands.Bot):
    """
    Set up the RoastCog by adding it to the bot.

    Args:
        bot (commands.Bot): The Discord bot instance.
    """
    await bot.add_cog(RoastCog(bot))