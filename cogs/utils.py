"""
UtilsCog Module

This module defines a utility cog for the Discord bot, providing common helper commands.
It includes ping, help, bot status (samosa), and listservers.
"""

import logging
import discord
from discord.ext import commands, tasks
from discord import app_commands

from utils import astra_db_ops


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

    @tasks.loop(minutes=30)
    async def bot_status_task(self):
        """Send periodic bot status updates."""
        bot_status_channels = astra_db_ops.load_bot_status_channels()
        for guild_id, channel_id in bot_status_channels.items():
            if channel_id is None:
                logging.warning(f"No channel set for guild {guild_id}. Skipping status update.")
                continue
            try:
                channel = self.bot.get_channel(int(channel_id))
                if channel:
                    await channel.send("✅ **SamosaBot is up and running!** 🔥")
                else:
                    logging.warning(f"Could not find channel {channel_id} for guild {guild_id}. Removing entry.")
                    astra_db_ops.save_bot_status_channel(guild_id, None)
            except Exception as e:
                logging.error(f"Error sending bot status update for guild {guild_id}: {e}")

    async def cog_load(self):
        """Start bot status task if channels are stored."""
        bot_status_channels = astra_db_ops.load_bot_status_channels()
        if bot_status_channels and not self.bot_status_task.is_running():
            self.bot_status_task.start()

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
                "`!trivia start <category> [fast/slow]` - Start trivia (prefix)\n"
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
                "`/ship <user1> [user2]` - Check compatibility between two users\n"
                "`!ship @user1 [@user2]` - Ship compatibility (prefix)\n"
                "`/pickup` - Get a pickup line\n"
                "`!pickup` - Get pickup line (prefix)\n"
                "`/roast @user` - Generate playful roast\n"
                "`!roast @user` - Roast user (prefix)\n"
                "`!compliment @user` - Generate compliment\n"
                "`!fortune` - Get AI-generated fortune"
            ),
            inline=False
        )
        
        # Community Section
        embed.add_field(
            name="💬 Community",
            value=(
                "`/confession <message>` - Submit an anonymous confession\n"
                "`/confession-setup` - Configure confession settings (admin only)\n"
                "`/confession-view <id>` - View a confession by ID (admin only)\n"
                "`/confession-history` - List confession history with pagination (admin only)\n"
                "\n*Confessions are analyzed for sentiment and may be auto-approved or queued for review*"
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

    @commands.command(name="samosa", description="Configure bot status updates")
    async def samosa(self, ctx, action: str, channel: discord.TextChannel = None):
        """Enable bot status updates (every 30 min) or disable."""
        if action.lower() == "botstatus":
            channel_id = channel.id if channel else ctx.channel.id
            guild_id = ctx.guild.id
            astra_db_ops.save_bot_status_channel(guild_id, channel_id)
            await ctx.send(f"✅ Bot status updates will be sent to <#{channel_id}> every 30 minutes.")
            if not self.bot_status_task.is_running():
                self.bot_status_task.start()
        elif action.lower() == "disable":
            guild_id = ctx.guild.id
            astra_db_ops.save_bot_status_channel(guild_id, None)
            await ctx.send("✅ Bot status updates have been disabled for this server.")

    @app_commands.command(name="samosa", description="Check or enable bot status updates")
    @app_commands.describe(action="Enable or disable bot status updates", channel="Select a channel (optional, defaults to current)")
    @app_commands.choices(action=[
        app_commands.Choice(name="Bot Status", value="botstatus"),
        app_commands.Choice(name="Disable", value="disable")
    ])
    async def slash_samosa(self, interaction: discord.Interaction, action: str, channel: discord.TextChannel = None):
        if action.lower() == "botstatus":
            channel_id = channel.id if channel else interaction.channel.id
            guild_id = interaction.guild_id
            astra_db_ops.save_bot_status_channel(guild_id, channel_id)
            await interaction.response.send_message(f"✅ Bot status updates will be sent to <#{channel_id}> every 30 minutes.")
            if not self.bot_status_task.is_running():
                self.bot_status_task.start()
        elif action.lower() == "disable":
            guild_id = interaction.guild_id
            astra_db_ops.save_bot_status_channel(guild_id, None)
            await interaction.response.send_message("✅ Bot status updates have been disabled for this server.")

    @commands.command(name="listservers", description="List servers where the bot is registered")
    async def list_servers(self, ctx):
        """List all servers (guilds) where the bot is registered with installation dates."""
        servers = astra_db_ops.list_registered_servers()
        if servers:
            response_lines = ["📜 **Registered Servers:**"]
            for server in servers:
                response_lines.append(
                    f"**{server['guild_name']}** (ID: {server['guild_id']}), Installed: {server['installed_at']}"
                )
            await ctx.send("\n".join(response_lines))
        else:
            await ctx.send("No registered servers found.")

async def setup(bot):
    """
    Sets up the UtilsCog for the Discord bot.

    This function is used by the bot's extension loader to add the UtilsCog to the bot.

    Args:
        bot (commands.Bot): The instance of the Discord bot.
    """
    await bot.add_cog(UtilsCog(bot))
