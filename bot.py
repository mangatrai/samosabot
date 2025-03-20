"""
SamosaBot Main Module

This module serves as the primary entry point for the SamosaBot Discord bot. It is responsible for:
  - Loading configuration from environment variables (including Discord credentials, bot prefix,
    and AstraDB settings).
  - Setting up Discord bot intents and initializing the bot instance with both prefix and slash commands.
  - Registering and managing various commands and scheduled tasks, such as:
      • Scheduled QOTD (Question of the Day) postings.
      • Periodic bot status updates.
      • Fun commands including jokes, roasts, compliments, pick-up lines, and fortune-telling.
  - Interacting with AstraDB for persistent storage (e.g., QOTD schedules, bot status channels, and user statistics).
  - Integrating with OpenAI via openai_utils to generate dynamic content based on user prompts.
  - Loading additional bot extensions (joke_cog, trivia_cog, utils_cog, ask_cog) and synchronizing slash commands.
  - Initiating a keep-alive web server to prevent the bot from being suspended in certain hosting environments.
  
All events, command errors, and operational messages are logged using the logging module for debugging and monitoring.
Running this module starts the bot and connects it to Discord using the specified TOKEN.
"""

from configs import setup_logger
import discord
import os
from discord.ext import commands, tasks
from discord import app_commands
from dotenv import load_dotenv
import logging
import math
import asyncio

from utils import astra_db_ops,openai_utils,keep_alive,throttle
from configs import prompts
from configs.version import __version__

# Load environment variables
load_dotenv()
TOKEN = os.getenv("DISCORD_BOT_TOKEN")
PREFIX = os.getenv("BOT_PREFIX", "!")  # Default prefix if not set
# Load environment variables for AstraDB
ASTRA_API_ENDPOINT = os.getenv("ASTRA_API_ENDPOINT")  # AstraDB API endpoint
ASTRA_NAMESPACE = os.getenv("ASTRA_NAMESPACE")  # Your namespace (like a database)
ASTRA_API_TOKEN = os.getenv("ASTRA_API_TOKEN")  # API authentication token

# Intents & Bot Setup
intents = discord.Intents.default()
intents.messages = True
intents.guilds = True
intents.message_content = True  # Ensure message content intent is enabled
bot = commands.Bot(command_prefix=PREFIX, intents=intents)
tree = bot.tree

# QOTD Schedule Tracking
qotd_channels = {}  # Dictionary to store QOTD channel IDs per server
# Global dictionary to track user command timestamps
user_command_timestamps = {}

#prompts laoding
qotd_prompt = prompts.qotd_prompt
joke_insult_prompt = prompts.joke_insult_prompt
joke_dad_prompt = prompts.joke_dad_prompt
joke_gen_prompt = prompts.joke_gen_prompt
pickup_prompt = prompts.pickup_prompt

# Load scheduled QOTD channels from AstraDB
def load_qotd_schedules():
    """Load scheduled QOTD channels from AstraDB."""
    return astra_db_ops.load_qotd_schedules()

# Save scheduled QOTD channels
def save_qotd_schedules():
    """Save QOTD channels in AstraDB."""
    for guild_id, channel_id in qotd_channels.items():
        astra_db_ops.save_qotd_schedules({"guild_id": guild_id, "channel_id": channel_id})

# Initialize QOTD storage
qotd_channels = load_qotd_schedules()

# Retrieve user stats from AstraDB
def get_user_stats(user_id):
    """Fetch user statistics from trivia_leaderboard in AstraDB."""
    return astra_db_ops.get_user_stats(user_id)

# Update user stats in AstraDB
def update_user_stats(user_id, username, correct_increment=0, wrong_increment=0):
    """Update user statistics and leaderboard in AstraDB."""
    astra_db_ops.update_user_stats(user_id, username, correct_increment, wrong_increment)

# Load stored bot status channels from AstraDB
def load_bot_status_channels():
    """Load bot status channels from AstraDB."""
    return astra_db_ops.load_bot_status_channels()

# Save bot status channel to AstraDB
def save_bot_status_channel(guild_id, channel_id):
    """Save bot status channel in AstraDB."""
    astra_db_ops.save_bot_status_channel(guild_id, channel_id)

# Initialize bot status channels
bot_status_channels = load_bot_status_channels()

# Scheduled QOTD Task
@tasks.loop(hours=24)
async def scheduled_qotd():
    for guild_id, channel_id in qotd_channels.items():
        channel = bot.get_channel(channel_id)
        if channel:
            content = openai_utils.generate_openai_response(qotd_prompt)
            await channel.send(f"🌟 **Question of the Day:** {content}")
        else:
            logging.warning(f"QOTD channel {channel_id} not found for server {guild_id}")


# Scheduled BotStatus Task
@tasks.loop(minutes=30)
async def bot_status_task():
    """Send periodic bot status updates."""
    bot_status_channels = astra_db_ops.load_bot_status_channels()  # Load from AstraDB

    for guild_id, channel_id in bot_status_channels.items():
        channel = bot.get_channel(int(channel_id))
        if channel:
            await channel.send("✅ **SamosaBot is up and running!** 🔥")
        else:
            logging.warning(f"Could not find channel {channel_id} for guild {guild_id}. Removing entry.")
            astra_db_ops.save_bot_status_channel(guild_id, None)  # Save None to remove entry in AstraDB

# Prefix Command for Bot Status
@bot.command(name="samosa")
async def samosa(ctx, action: str, channel: discord.TextChannel = None):
    if action.lower() == "botstatus":
        channel_id = channel.id if channel else ctx.channel.id  # Use input channel or default to current channel
        guild_id = ctx.guild.id

       # Store bot status channel in Postgres
        save_bot_status_channel(guild_id, channel_id)
        await ctx.send(f"✅ Bot status updates will be sent to <#{channel_id}> every 30 minutes.")

        # Start the scheduled bot status task if not running
        if not bot_status_task.is_running():
            bot_status_task.start()

# Prefix Command for SetQOTD Channel
@bot.command(name="setqotdchannel")
async def set_qotd_channel(ctx, channel_id: int = None):
    if channel_id is None:
        channel_id = ctx.channel.id  # Default to the current channel if none is provided

    # ✅ Reload qotd_channels from database to ensure correct state
    qotd_channels = load_qotd_schedules()
    qotd_channels[ctx.guild.id] = channel_id  # Store in memory
    save_qotd_schedules()  # Save to Postgres DB
    await ctx.send(
        f"✅ Scheduled QOTD channel set to <#{channel_id}> for this server."
    )

# Prefix Command for StartQOTD
@bot.command(name="startqotd")
async def start_qotd(ctx):

    qotd_channels = load_qotd_schedules()  # ✅ Refresh data from DB

    if ctx.guild.id not in qotd_channels or not qotd_channels[ctx.guild.id]:
        await ctx.send("[ERROR] No scheduled QOTD channel set for this server. Use `!setqotdchannel <channel_id>`")
        return

    if not scheduled_qotd.is_running():  # ✅ Prevent duplicate loops
        scheduled_qotd.start()
        await ctx.send("✅ Scheduled QOTD started for this server!")
    else:
        await ctx.send("⚠️ QOTD is already running!")  # ✅ Avoid duplicate start

# Prefix Command for QOTD
@bot.command(name="qotd")
async def qotd(ctx):
    content = openai_utils.generate_openai_response(qotd_prompt)
    await ctx.send(f"🌟 **Question of the Day:** {content}")


# Prefix Command for Pick-up Line
@bot.command(name="pickup")
async def pickup(ctx):
    content = openai_utils.generate_openai_response(pickup_prompt)
    await ctx.send(f"💘 **Pick-up Line:** {content}")

#Compliment Machine
@bot.command(name="compliment")
async def compliment(ctx, user: discord.Member = None):
    """Generate a compliment for a user."""
    target = user.display_name if user else ctx.author.display_name
    prompt = f"Generate a wholesome and genuine compliment for {target}."
    content = openai_utils.generate_openai_response(prompt)
    await ctx.send(f"💖 {content}")

#AI-Powered Fortune Teller
@bot.command(name="fortune")
async def fortune(ctx):
    """Give a user their AI-powered fortune."""
    prompt = "Generate a fun, unpredictable, and mystical fortune-telling message. Keep it engaging and lighthearted."
    content = openai_utils.generate_openai_response(prompt)
    await ctx.send(f"🔮 **Your fortune:** {content}")

# Prefix command to ListServers who have bot registered
@bot.command(name="listservers")
async def list_servers(ctx):
    """
    List all servers (guilds) where the bot is registered along with their installation dates.
    """
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

# Slash Command for Bot Status
@tree.command(name="samosa", description="Check or enable bot status updates")
@app_commands.describe(action="Enable bot status updates", channel="Select a channel (optional, defaults to current)")
@app_commands.choices(action=[app_commands.Choice(name="Bot Status", value="botstatus")])
async def slash_samosa(interaction: discord.Interaction, action: str, channel: discord.TextChannel = None):
    if action == "botstatus":
        channel_id = channel.id if channel else interaction.channel_id
        guild_id = interaction.guild_id

        # Store bot status channel in AstraDB
        save_bot_status_channel(guild_id, channel_id)

        await interaction.response.send_message(f"✅ Bot status updates will be sent to <#{channel_id}> every 30 minutes.", ephemeral=True)

        # Start the scheduled bot status task if not running
        if not bot_status_task.is_running():
            bot_status_task.start()

# Slash Command for QOTD
@tree.command(name="qotd", description="Get a Question of the Day")
async def slash_qotd(interaction: discord.Interaction):
    try:
        await interaction.response.defer()  # Acknowledge the interaction immediately
        content = openai_utils.generate_openai_response(qotd_prompt)
        await interaction.followup.send(f"🌟 **Question of the Day:** {content}")
    except Exception as e:
        logging.error(f"Error in slash_qotd: {e}")
        await interaction.followup.send("❌ An error occurred while fetching the Question of the Day.")

# Slash Command with Pickup
@tree.command(name="pickup", description="Get a pick-up line")
async def slash_pickup(interaction: discord.Interaction):
    content = openai_utils.generate_openai_response(pickup_prompt)
    await interaction.response.send_message(f"💘 **Pick-up Line:** {content}")

@bot.event
async def on_ready():
    await bot.wait_until_ready()  # Ensure bot is fully ready before proceeding
    logging.info(f"🤖 SamosaBot Version: {__version__}")
    logging.info(f'Logged in as {bot.user}')

    await bot.load_extension("cogs.joke")
    await bot.load_extension("cogs.trivia")
    await bot.load_extension("cogs.utils")
    await bot.load_extension("cogs.ask")
    await bot.load_extension("cogs.roast")
    # Load stored QOTD schedules and bot status channels from DB
    qotd_channels = load_qotd_schedules()
    bot_status_channels = load_bot_status_channels()

    logging.debug(f"[DEBUG] Loaded QOTD schedules: {qotd_channels}")
    logging.debug(f"[DEBUG] Loaded bot status channels: {bot_status_channels}")

    # Start bot status task if channels are stored
    if bot_status_channels and not bot_status_task.is_running():
        bot_status_task.start()

    # Sync slash commands globally
    try:
        await tree.sync(guild=None)
        logging.debug(f"[DEBUG] Synced {len(tree.get_commands())} slash commands globally")
    except Exception as e:
        logging.error(f"[ERROR] Failed to sync commands globally: {e}")

    # Sync slash commands for each guild
    for guild in bot.guilds:
        try:
            await tree.sync(guild=guild)
            astra_db_ops.register_or_update_guild(guild.id, guild.name,"JOINED")
            logging.debug(f"[DEBUG] Synced slash commands for {guild.name} ({guild.id})")
        except Exception as e:
            logging.error(f"[ERROR] Failed to sync commands for {guild.name} ({guild.id}): {e}")

@bot.check
async def global_throttle_check(ctx):
    """
    Global check to throttle commands per user, excluding exempt commands.
    
    Raises:
        commands.CommandOnCooldown: If the user is sending commands too frequently.
    """
    command_name = ctx.command.name if ctx.command else ""
    retry_after = throttle.check_command_throttle(ctx.author.id, command_name)

    if retry_after > 0:
        cooldown = commands.Cooldown(1, retry_after)
        raise commands.CommandOnCooldown(cooldown, retry_after, commands.BucketType.user)

    return True

@bot.event
async def on_guild_join(guild: discord.Guild):
    logging.info(f"Joined new guild: {guild.name} ({guild.id})")
    astra_db_ops.register_or_update_guild(guild.id, guild.name,"JOINED")

@bot.event
async def on_guild_remove(guild: discord.Guild):
    logging.info(f"Left guild: {guild.name} ({guild.id})")
    astra_db_ops.register_or_update_guild(guild.id, guild.name,"LEFT")

@bot.event
async def on_command_error(ctx, error):
    """
    Global error handler for command invocation errors.

    This event is triggered when a command raises an error during execution. It checks if the error is of type 
    CommandOnCooldown and, if so, sends a custom cooldown message with a live countdown timer indicating when the user 
    can try again. For other types of errors, it logs the error and notifies the user with a generic error message.

    Args:
        ctx (commands.Context): The context in which the command was invoked.
        error (Exception): The exception raised by the command.
    """
    if isinstance(error, commands.CommandOnCooldown):
        # Round up the retry time
        retry = math.ceil(error.retry_after)
        # Send an initial cooldown message with a countdown
        cooldown_message = await ctx.send(f"Slow down {ctx.author.mention}! Try again in {retry} sec.")
        # Update the message each second until cooldown expires
        for remaining in range(retry, 0, -1):
            try:
                await asyncio.sleep(1)
                await cooldown_message.edit(content=f"Slow down {ctx.author.mention}! Try again in {remaining} sec.")
            except Exception:
                break
        try:
            await cooldown_message.delete()
        except Exception:
            pass
    else:
        # Log other errors for debugging purposes
        logging.error(f"Command error: {error}")
        await ctx.send(f"An error occurred: {error}")

# Wrap bot.run in a try-except block to handle unexpected crashes
try:
    keep_alive.keep_alive()  # Start the background web server
    bot.run(TOKEN)
except Exception as e:
    logging.error(f"[ERROR] Bot encountered an unexpected issue: {e}")
