"""
UtilsCog Module

This module defines a utility cog for the Discord bot, providing common helper commands.
It includes commands such as 'ping' to check the bot's latency and 'help' to display all available commands.
"""

import discord
from discord.ext import commands
from discord import app_commands

class UtilsCog(commands.Cog):
    """
    A Cog that contains utility commands for the bot.

    Attributes:
        bot (commands.Bot): The instance of the Discord bot.
    
    Commands:
        ping: Checks and displays the bot's current latency.
        help: Displays a comprehensive list of all available commands organized by category.
    """
    
    def __init__(self, bot):
        """
        Initializes the UtilsCog with the provided Discord bot instance.

        Args:
            bot (commands.Bot): The Discord bot instance.
        """
        self.bot = bot

    def create_help_embed(self):
        """Create a comprehensive help embed with all bot commands organized by category."""
        embed = discord.Embed(
            title="🤖 SamosaBot - Command Help",
            description="A feature-rich Discord bot with games, jokes, facts, and more!",
            color=discord.Color.blue()
        )
        
        # Games Section
        embed.add_field(
            name="🎉 Games",
            value=(
                "`/trivia start <category>` - Start interactive trivia game\n"
                "`/trivia stop` - Stop current trivia game\n"
                "`/trivia leaderboard` - View top players\n"
                "`!trivia start <category> <fast/slow>` - Start trivia (prefix)\n"
                "`!trivia stop` - Stop trivia (prefix)\n"
                "`!mystats` - View your trivia stats\n"
                "`/tod` - Truth or Dare game (with buttons)\n"
                "`/tod-submit` - Submit your own questions"
            ),
            inline=False
        )
        
        # Entertainment Section
        embed.add_field(
            name="🤣 Entertainment",
            value=(
                "`/joke <category>` - Get jokes (dad, insult, general, dark, spooky)\n"
                "`!joke <category>` - Get joke (prefix)\n"
                "`/joke-submit` - Submit your own joke\n"
                "`/fact` - Get random general fact\n"
                "`/fact animals` - Get random animal fact\n"
                "`!fact` - Get fact (prefix)\n"
                "`/fact-submit` - Submit your own fact\n"
                "`/pickup` - Get a pickup line\n"
                "`!pickup` - Get pickup line (prefix)\n"
                "`/roast @user` - Generate playful roast\n"
                "`!roast @user` - Roast user (prefix)\n"
                "`!compliment @user` - Generate compliment\n"
                "`!fortune` - Get AI-generated fortune"
            ),
            inline=False
        )
        
        # AI & Questions Section
        embed.add_field(
            name="🤖 AI & Questions",
            value=(
                "`/ask <question>` - Ask AI anything or generate images\n"
                "`!asksamosa <question>` - Ask AI (prefix)\n"
                "`/qotd` - Get Question of the Day\n"
                "`!qotd` - Get QOTD (prefix)\n"
                "`!setqotdchannel <channel>` - Set QOTD channel (admin)\n"
                "`!startqotd` - Start daily QOTD schedule (admin)"
            ),
            inline=False
        )
        
        # Utility Section
        embed.add_field(
            name="🔧 Utility",
            value=(
                "`!ping` - Check bot response time\n"
                "`!help` - Show this help message\n"
                "`/help` - Show help (slash command)"
            ),
            inline=False
        )
        
        # Additional Info
        embed.add_field(
            name="💡 Tips",
            value=(
                "• Use **slash commands** (`/`) for the best experience\n"
                "• Many commands use **interactive buttons** for easy navigation\n"
                "• Rate content with 👍/👎 reactions to help improve the bot\n"
                "• Submit your own questions, jokes, and facts to grow the community!"
            ),
            inline=False
        )
        
        embed.set_footer(text="Use !help or /help anytime to see this message")
        
        return embed

    @commands.command(name="help", description="Display all available commands organized by category.")
    async def help_command(self, ctx):
        """
        Displays a comprehensive help message with all available bot commands.
        
        Shows commands organized by category: Games, Entertainment, AI & Questions,
        Utility, and Server Management. Includes both slash and prefix commands.
        
        Args:
            ctx (commands.Context): The context of the command invocation.
        """
        embed = self.create_help_embed()
        await ctx.send(embed=embed)

    @app_commands.command(name="help", description="Display all available commands organized by category.")
    async def help_slash(self, interaction: discord.Interaction):
        """
        Display all available commands (slash command version).
        
        Shows commands organized by category with usage examples.
        """
        embed = self.create_help_embed()
        await interaction.response.send_message(embed=embed)

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
