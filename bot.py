"""
SamosaBot Main Module

This module serves as the primary entry point for the SamosaBot Discord bot. It is responsible for:
  - Loading configuration from environment variables (including Discord credentials, bot prefix,
    and AstraDB settings).
  - Setting up Discord bot intents and initializing the bot instance with both prefix and slash commands.
  - Registering and managing various commands and scheduled tasks, such as:
      • Interactive Trivia Game with button-based answers, score tracking, and leaderboards
      • Truth or Dare game with persistent buttons, multiple game types (Truth, Dare, WYR, NHIE, Paranoia),
        and rating options (Family-friendly PG13 or Adult Only R)
      • Random Facts (general and animal facts) with user submissions and feedback
      • AI-Powered Jokes (dad, insult, general, dark, spooky) with user submissions and feedback
      • Pickup Lines, Roasts, Compliments, and Fortune Telling
      • Question of the Day (QOTD) with scheduling support
      • AI Ask command with daily request limits and image generation
      • Server verification system with setup wizard
      • Scheduled QOTD postings (24-hour intervals)
      • Periodic bot status updates (30-minute intervals)
  - Interacting with AstraDB for persistent storage (e.g., QOTD schedules, bot status channels, 
    user statistics, trivia leaderboards, truth/dare questions, jokes, facts, verification data).
  - Integrating with OpenAI via openai_utils to generate dynamic content based on user prompts.
  - Loading additional bot extensions (cogs) and synchronizing slash commands with retry logic.
  - Handling persistent views for buttons that work even after bot restarts.
  - Global command throttling and error handling.
  - Initiating a keep-alive web server to prevent the bot from being suspended in certain hosting environments.
  
All events, command errors, and operational messages are logged using the logging module for debugging and monitoring.
Running this module starts the bot and connects it to Discord using the specified TOKEN.
"""

from configs import setup_logger
import discord
import os
import requests
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
RIZZAPI_URL = os.getenv("RIZZAPI_URL")

EXTENSIONS = os.getenv("EXTENSIONS", "").split(",")

# Function to get pickup line from RizzAPI
def get_rizzapi_pickup():
    """Get pickup line from RizzAPI, return None if fails"""
    try:
        response = requests.get(RIZZAPI_URL, timeout=5)
        if response.status_code == 200:
            data = response.json()
            return data.get('text', None)
    except Exception as e:
        logging.warning(f"RizzAPI failed: {e}")
    return None

# Intents & Bot Setup
intents = discord.Intents.default()
intents.members = True  # Enable member intents
intents.messages = True
intents.guilds = True
intents.message_content = True  # Enable message content intent
bot = commands.Bot(command_prefix=PREFIX, intents=intents)
tree = bot.tree

# First user heuristic tracking
newly_joined_guilds = set()  # Track guilds that just joined for first user detection

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
        # Check if channel_id is None or empty, then skip updating
        if channel_id is None:
            logging.warning(f"No channel set for guild {guild_id}. Skipping status update.")
            continue

        try:
            # Ensure channel_id is a valid integer before using it
            channel = bot.get_channel(int(channel_id))
            if channel:
                await channel.send("✅ **SamosaBot is up and running!** 🔥")
            else:
                logging.warning(f"Could not find channel {channel_id} for guild {guild_id}. Removing entry.")
                astra_db_ops.save_bot_status_channel(guild_id, None)
        except Exception as e:
            logging.error(f"Error sending bot status update for guild {guild_id}: {e}")

# Prefix Command for Bot Status
@bot.command(name="samosa")
async def samosa(ctx, action: str, channel: discord.TextChannel = None):
    """
    Configure bot status updates for the server.
    
    Actions:
        - botstatus: Enable bot status updates (sends every 30 minutes to specified channel)
        - disable: Disable bot status updates for this server
    
    Args:
        ctx: Command context
        action: Action to perform (botstatus or disable)
        channel: Optional channel for bot status updates (defaults to current channel)
    """
    if action.lower() == "botstatus":
        channel_id = channel.id if channel else ctx.channel.id  # Use input channel or default to current channel
        guild_id = ctx.guild.id

       # Store bot status channel in Postgres
        save_bot_status_channel(guild_id, channel_id)
        await ctx.send(f"✅ Bot status updates will be sent to <#{channel_id}> every 30 minutes.")

        # Start the scheduled bot status task if not running
        if not bot_status_task.is_running():
            bot_status_task.start()
    elif action.lower() == "disable":
        guild_id = ctx.guild.id
        save_bot_status_channel(guild_id, None)
        await ctx.send("✅ Bot status updates have been disabled for this server.")

# Prefix Command for SetQOTD Channel
@bot.command(name="setqotdchannel")
async def set_qotd_channel(ctx, channel_id: int = None):
    """
    Set the channel for scheduled Question of the Day posts.
    
    Args:
        ctx: Command context
        channel_id: Optional channel ID (defaults to current channel if not provided)
    """
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
    """
    Start the scheduled Question of the Day task (posts every 24 hours).
    
    Requires a QOTD channel to be set first using !setqotdchannel.
    """

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
    """Get a random AI-generated Question of the Day."""
    async with ctx.typing():
        content = openai_utils.generate_openai_response(qotd_prompt)
        await ctx.send(f"🌟 **Question of the Day:** {content}")


# Prefix Command for Pick-up Line
@bot.command(name="pickup")
async def pickup(ctx):
    """Get a fun pickup line from RizzAPI or AI fallback."""
    async with ctx.typing():
        # Try RizzAPI first
        content = get_rizzapi_pickup()
        if content is None:
            # Fallback to AI
            content = openai_utils.generate_openai_response(pickup_prompt)
        await ctx.send(f"💘 **Pick-up Line:** {content}")

#Compliment Machine
@bot.command(name="compliment")
async def compliment(ctx, user: discord.Member = None):
    """Generate a compliment for a user."""
    async with ctx.typing():
        target = user.display_name if user else ctx.author.display_name
        prompt = f"Generate a wholesome and genuine compliment for {target}."
        content = openai_utils.generate_openai_response(prompt)
        await ctx.send(f"💖 {content}")

#AI-Powered Fortune Teller
@bot.command(name="fortune")
async def fortune(ctx):
    """Give a user their AI-powered fortune."""
    async with ctx.typing():
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
@app_commands.describe(action="Enable or disable bot status updates", channel="Select a channel (optional, defaults to current)")
@app_commands.choices(action=[
    app_commands.Choice(name="Bot Status", value="botstatus"),
    app_commands.Choice(name="Disable", value="disable")
])
async def slash_samosa(interaction: discord.Interaction, action: str, channel: discord.TextChannel = None):
    if action.lower() == "botstatus":
        channel_id = channel.id if channel else interaction.channel.id
        guild_id = interaction.guild_id

        # Store bot status channel in AstraDB
        save_bot_status_channel(guild_id, channel_id)
        await interaction.response.send_message(f"✅ Bot status updates will be sent to <#{channel_id}> every 30 minutes.")

        # Start the scheduled bot status task if not running
        if not bot_status_task.is_running():
            bot_status_task.start()
    elif action.lower() == "disable":
        guild_id = interaction.guild_id
        save_bot_status_channel(guild_id, None)
        await interaction.response.send_message("✅ Bot status updates have been disabled for this server.")

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
    await interaction.response.defer()
    # Try RizzAPI first
    content = get_rizzapi_pickup()
    if content is None:
        # Fallback to AI
        content = openai_utils.generate_openai_response(pickup_prompt)
    await interaction.followup.send(f"💘 **Pick-up Line:** {content}")

@bot.event
async def on_ready():
    await bot.wait_until_ready()  # Ensure bot is fully ready before proceeding
    logging.info(f"🤖 SamosaBot Version: {__version__}")
    logging.info(f'Logged in as {bot.user}')

    for ext in EXTENSIONS:
        try:
            await bot.load_extension(ext)
        except commands.ExtensionAlreadyLoaded:
            logging.error(f"Extension '{ext}' is already loaded. Skipping.")

    # Load stored QOTD schedules and bot status channels from DB
    qotd_channels = load_qotd_schedules()
    bot_status_channels = load_bot_status_channels()

    logging.debug(f"[DEBUG] Loaded QOTD schedules: {qotd_channels}")
    logging.debug(f"[DEBUG] Loaded bot status channels: {bot_status_channels}")

    # Start bot status task if channels are stored
    if bot_status_channels and not bot_status_task.is_running():
        bot_status_task.start()

    # Wait for cogs to fully register commands
    await asyncio.sleep(2)
    logging.info("Waiting for cogs to register commands...")

    # Sync slash commands globally with retry
    for attempt in range(3):
        try:
            await tree.sync(guild=None)
            logging.info(f"[SUCCESS] Synced {len(tree.get_commands())} slash commands globally")
            break
        except Exception as e:
            logging.error(f"[ERROR] Failed to sync commands globally (attempt {attempt + 1}/3): {e}")
            if attempt < 2:
                await asyncio.sleep(2)

    # Sync slash commands for each guild with retry
    for guild in bot.guilds:
        for attempt in range(2):
            try:
                await tree.sync(guild=guild)
                register_guild_with_metadata(guild, "JOINED")
                logging.info(f"[SUCCESS] Synced slash commands for {guild.name} ({guild.id})")
                break
            except Exception as e:
                logging.error(f"[ERROR] Failed to sync commands for {guild.name} ({guild.id}) (attempt {attempt + 1}/2): {e}")
                if attempt < 1:
                    await asyncio.sleep(1)

@bot.check
async def global_throttle_check(ctx):
    """
    Global check to throttle commands per user, excluding exempt commands.
    Also tracks first user after bot joins a guild (heuristic for added_by).
    
    Raises:
        commands.CommandOnCooldown: If the user is sending commands too frequently.
    """
    # First user heuristic: track first command after guild join
    if ctx.guild and str(ctx.guild.id) in newly_joined_guilds:
        newly_joined_guilds.discard(str(ctx.guild.id))  # Remove from tracking
        astra_db_ops.update_guild_added_by(
            str(ctx.guild.id),
            str(ctx.author.id),
            ctx.author.display_name
        )
    
    # Track daily command count for all prefix commands
    if ctx.guild:
        astra_db_ops.increment_daily_request_count(
            ctx.author.id,
            str(ctx.guild.id),
            ctx.guild.name,
            ctx.author.display_name
        )
    
    command_name = ctx.command.name if ctx.command else ""
    retry_after = throttle.check_command_throttle(ctx.author.id, command_name)

    if retry_after > 0:
        cooldown = commands.Cooldown(1, retry_after)
        raise commands.CommandOnCooldown(cooldown, retry_after, commands.BucketType.user)

    return True

def extract_guild_metadata(guild: discord.Guild):
    """Extract all available guild metadata."""
    # Get owner info
    owner_id = str(guild.owner_id) if guild.owner_id else None
    owner_name = None
    if guild.owner:
        owner_name = guild.owner.display_name
    elif owner_id:
        # Try to fetch if not cached
        try:
            owner = guild.get_member(guild.owner_id)
            if owner:
                owner_name = owner.display_name
        except:
            pass
    
    # Get server creation date
    server_created_at = guild.created_at.isoformat() if guild.created_at else None
    
    # Get other metadata
    description = guild.description if hasattr(guild, 'description') else None
    member_count = guild.member_count if guild.member_count else None
    icon_url = str(guild.icon.url) if guild.icon else None
    banner_url = str(guild.banner.url) if guild.banner else None
    verification_level = guild.verification_level.value if guild.verification_level else None
    premium_tier = guild.premium_tier if hasattr(guild, 'premium_tier') else None
    premium_subscription_count = guild.premium_subscription_count if hasattr(guild, 'premium_subscription_count') else None
    features = list(guild.features) if hasattr(guild, 'features') and guild.features else None
    vanity_url_code = guild.vanity_url_code if hasattr(guild, 'vanity_url_code') and guild.vanity_url_code else None
    preferred_locale = str(guild.preferred_locale) if hasattr(guild, 'preferred_locale') else None
    nsfw_level = guild.nsfw_level.value if hasattr(guild, 'nsfw_level') else None
    
    return {
        "owner_id": owner_id,
        "owner_name": owner_name,
        "server_created_at": server_created_at,
        "description": description,
        "member_count": member_count,
        "icon_url": icon_url,
        "banner_url": banner_url,
        "verification_level": verification_level,
        "premium_tier": premium_tier,
        "premium_subscription_count": premium_subscription_count,
        "features": features,
        "vanity_url_code": vanity_url_code,
        "preferred_locale": preferred_locale,
        "nsfw_level": nsfw_level
    }

def register_guild_with_metadata(guild: discord.Guild, status: str):
    """Extract metadata and register/update guild in database."""
    metadata = extract_guild_metadata(guild)
    astra_db_ops.register_or_update_guild(
        guild.id, guild.name, status,
        owner_id=metadata["owner_id"],
        owner_name=metadata["owner_name"],
        server_created_at=metadata["server_created_at"],
        description=metadata["description"],
        member_count=metadata["member_count"],
        icon_url=metadata["icon_url"],
        banner_url=metadata["banner_url"],
        verification_level=metadata["verification_level"],
        premium_tier=metadata["premium_tier"],
        premium_subscription_count=metadata["premium_subscription_count"],
        features=metadata["features"],
        vanity_url_code=metadata["vanity_url_code"],
        preferred_locale=metadata["preferred_locale"],
        nsfw_level=metadata["nsfw_level"]
    )

@bot.event
async def on_guild_join(guild: discord.Guild):
    logging.info(f"Joined new guild: {guild.name} ({guild.id})")
    register_guild_with_metadata(guild, "JOINED")
    # Track for first user heuristic
    newly_joined_guilds.add(str(guild.id))

@bot.event
async def on_interaction(interaction: discord.Interaction):
    """Handle interactions (slash commands) for first user heuristic and daily command tracking."""
    if interaction.type == discord.InteractionType.application_command and interaction.guild:
        # First user heuristic
        if str(interaction.guild_id) in newly_joined_guilds:
            newly_joined_guilds.discard(str(interaction.guild_id))
            astra_db_ops.update_guild_added_by(
                str(interaction.guild_id),
                str(interaction.user.id),
                interaction.user.display_name
            )
        
        # Track daily command count for all slash commands
        astra_db_ops.increment_daily_request_count(
            interaction.user.id,
            str(interaction.guild_id),
            interaction.guild.name if interaction.guild else None,
            interaction.user.display_name
        )

@bot.event
async def on_guild_remove(guild: discord.Guild):
    logging.info(f"Left guild: {guild.name} ({guild.id})")
    # Remove from tracking if still there
    newly_joined_guilds.discard(str(guild.id))
    register_guild_with_metadata(guild, "LEFT")

@bot.event
async def on_reaction_add(reaction, user):
    """Handle emoji reactions for Truth/Dare feedback."""
    if user.bot:
        return  # Ignore bot reactions
    
    if reaction.emoji in ["👍", "👎"]:
        try:
            # Get message metadata
            message_data = astra_db_ops.get_truth_dare_message_metadata(str(reaction.message.id))
            if message_data:
                # Update feedback counter
                feedback_type = "positive" if reaction.emoji == "👍" else "negative"
                astra_db_ops.record_question_feedback(message_data["question_id"], feedback_type)
                logging.debug(f"Recorded {feedback_type} feedback for question {message_data['question_id']} from user {user.id}")
        except Exception as e:
            logging.error(f"Error handling reaction: {e}")

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
    if isinstance(error, commands.CommandNotFound):
        # Silently ignore unknown commands to prevent spam
        return
    elif isinstance(error, commands.CommandOnCooldown):
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
