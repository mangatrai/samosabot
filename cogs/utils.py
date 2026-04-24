"""
UtilsCog Module

This module defines a utility cog for the Discord bot, providing common helper commands.
It includes ping, help, bot status (samosa), and listservers.
"""

import base64
import logging
import discord
from discord.ext import commands, tasks
from discord import app_commands

from utils import astra_db_ops
from utils import error_handler


class UtilsCog(commands.Cog):
    """
    A Cog that contains utility commands for the bot.

    Attributes:
        bot (commands.Bot): The instance of the Discord bot.

    Commands:
        ping: Checks and displays the bot's current latency.
        help: Displays a comprehensive list of all available commands organized by category.
    """

    _ALLOWED_ICON_EXTS = (".png", ".jpg", ".jpeg", ".webp")
    _MAX_ICON_BYTES = 8 * 1024 * 1024  # 8 MB

    samosa_group = app_commands.Group(name="samosa", description="Bot administration commands")

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
                "`/help` - Show help (slash command)\n"
                "`/samosa seticon <image>` - Set guild-specific bot avatar (Manage Server)\n"
                "`/samosa removeicon` - Revert bot to global default avatar (Manage Server)"
            ),
            inline=False
        )
        
        # Clan Events Section
        embed.add_field(
            name="🏆 Clan Events",
            value=(
                "`/event list` - See all events and their activities & points\n"
                "`/event leaderboard [member] [event]` - Scores and clan rankings\n"
                "**Mod only:**\n"
                "`/events setup` - Configure clans, channels, and mod roles\n"
                "`/events settings` - View current configuration\n"
                "`/event create` - Create a new event (multi-step)\n"
                "`/event start/stop <event>` - Start or end an event\n"
                "`/event award @member <event> <activity>` - Award points\n"
                "`/event adjust @member <event> <pts> <reason>` - Adjust points with audit trail\n"
                "`/event setbanner <event> <image>` - Upload a PNG/JPG/WEBP banner image"
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

    @commands.command(name="samosa", description="Configure bot status updates or guild avatar")
    async def samosa(self, ctx, action: str, channel: discord.TextChannel = None):
        """Enable bot status updates, disable them, or set/remove the guild avatar."""
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
        elif action.lower() == "seticon":
            if not ctx.author.guild_permissions.manage_guild:
                await ctx.send("❌ You need **Manage Server** permission to change the bot's icon.")
                return
            if not ctx.message.attachments:
                await ctx.send("❌ Please attach a PNG, JPG, JPEG, or WEBP image to your message (max 8 MB).")
                return
            attachment = ctx.message.attachments[0]
            if not any(attachment.filename.lower().endswith(ext) for ext in self._ALLOWED_ICON_EXTS):
                await ctx.send("❌ Unsupported file type. Use PNG, JPG, JPEG, or WEBP.")
                return
            if attachment.size > self._MAX_ICON_BYTES:
                await ctx.send(f"❌ Image too large ({attachment.size // (1024 * 1024)} MB). Max is 8 MB.")
                return
            try:
                image_bytes = await attachment.read()
                ext = attachment.filename.rsplit('.', 1)[-1].lower()
                mime = {
                    'png': 'image/png', 'jpg': 'image/jpeg',
                    'jpeg': 'image/jpeg', 'webp': 'image/webp',
                }.get(ext, 'image/png')
                b64 = base64.b64encode(image_bytes).decode('utf-8')
                await ctx.bot.http.edit_member(
                    str(ctx.guild.id), '@me', avatar=f"data:{mime};base64,{b64}"
                )
                astra_db_ops.update_guild_custom_bot_icon(str(ctx.guild.id), True)
                await ctx.send("✅ Guild avatar updated! It may take a moment to propagate.")
            except Exception as e:
                await error_handler.handle_error(e, ctx, "samosa seticon")
        elif action.lower() == "removeicon":
            if not ctx.author.guild_permissions.manage_guild:
                await ctx.send("❌ You need **Manage Server** permission.")
                return
            try:
                await ctx.bot.http.edit_member(str(ctx.guild.id), '@me', avatar=None)
                astra_db_ops.update_guild_custom_bot_icon(str(ctx.guild.id), False)
                await ctx.send("✅ Guild avatar removed. Bot will show its global default avatar.")
            except Exception as e:
                await error_handler.handle_error(e, ctx, "samosa removeicon")

    @samosa_group.command(name="botstatus", description="Send bot status updates to a channel every 30 minutes")
    @app_commands.describe(channel="Channel for status updates (defaults to current channel)")
    async def samosa_botstatus(self, interaction: discord.Interaction, channel: discord.TextChannel = None):
        channel_id = channel.id if channel else interaction.channel.id
        guild_id = interaction.guild_id
        astra_db_ops.save_bot_status_channel(guild_id, channel_id)
        await interaction.response.send_message(f"✅ Bot status updates will be sent to <#{channel_id}> every 30 minutes.")
        if not self.bot_status_task.is_running():
            self.bot_status_task.start()

    @samosa_group.command(name="disable", description="Disable bot status updates for this server")
    async def samosa_disable(self, interaction: discord.Interaction):
        guild_id = interaction.guild_id
        astra_db_ops.save_bot_status_channel(guild_id, None)
        await interaction.response.send_message("✅ Bot status updates have been disabled for this server.")

    @samosa_group.command(name="seticon", description="Set a guild-specific avatar for the bot (Manage Server)")
    @app_commands.describe(image="PNG, JPG, or WEBP image — recommended 512×512 or 1024×1024 px, max 8 MB")
    async def samosa_seticon(self, interaction: discord.Interaction, image: discord.Attachment):
        if not interaction.user.guild_permissions.manage_guild:
            await interaction.response.send_message(
                "❌ You need **Manage Server** permission to change the bot's icon.", ephemeral=True
            )
            return
        if not any(image.filename.lower().endswith(ext) for ext in self._ALLOWED_ICON_EXTS):
            await interaction.response.send_message(
                f"❌ **{image.filename}** is not a supported type. Use PNG, JPG, JPEG, or WEBP.", ephemeral=True
            )
            return
        if image.size > self._MAX_ICON_BYTES:
            await interaction.response.send_message(
                f"❌ Image is too large ({image.size // (1024 * 1024)} MB). Maximum is 8 MB.", ephemeral=True
            )
            return
        await interaction.response.defer(ephemeral=True)
        try:
            image_bytes = await image.read()
            ext = image.filename.rsplit('.', 1)[-1].lower()
            mime = {
                'png': 'image/png', 'jpg': 'image/jpeg',
                'jpeg': 'image/jpeg', 'webp': 'image/webp',
            }.get(ext, 'image/png')
            b64 = base64.b64encode(image_bytes).decode('utf-8')
            await interaction.client.http.edit_member(
                str(interaction.guild_id), '@me', avatar=f"data:{mime};base64,{b64}"
            )
            astra_db_ops.update_guild_custom_bot_icon(str(interaction.guild_id), True)
            embed = discord.Embed(
                title="✅ Guild Avatar Updated",
                description=(
                    "The bot now has a custom look in **this server only**. "
                    "Changes may take a moment to propagate.\n\n"
                    "**Tips:**\n"
                    "• Recommended size: 512×512 or 1024×1024 px\n"
                    "• Supported formats: PNG, JPG, WEBP\n"
                    "• Use `/samosa removeicon` to revert to the global default"
                ),
                color=discord.Color.green(),
            )
            embed.set_thumbnail(url=image.url)
            await interaction.followup.send(embed=embed, ephemeral=True)
        except Exception as e:
            await error_handler.handle_error(e, interaction, "samosa seticon")

    @samosa_group.command(name="removeicon", description="Reset the bot to its global default avatar (Manage Server)")
    async def samosa_removeicon(self, interaction: discord.Interaction):
        if not interaction.user.guild_permissions.manage_guild:
            await interaction.response.send_message(
                "❌ You need **Manage Server** permission.", ephemeral=True
            )
            return
        await interaction.response.defer(ephemeral=True)
        try:
            await interaction.client.http.edit_member(str(interaction.guild_id), '@me', avatar=None)
            astra_db_ops.update_guild_custom_bot_icon(str(interaction.guild_id), False)
            await interaction.followup.send(
                "✅ Guild avatar removed. The bot will now show its global default avatar in this server.",
                ephemeral=True,
            )
        except Exception as e:
            await error_handler.handle_error(e, interaction, "samosa removeicon")

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
