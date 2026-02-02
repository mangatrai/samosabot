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
from discord.ext import commands, tasks
from discord import app_commands
from dotenv import load_dotenv
import logging
import math
import asyncio

from utils import astra_db_ops, keep_alive, throttle
from utils import error_handler
from configs import prompts
from configs.version import __version__

# Load environment variables
load_dotenv()
TOKEN = os.getenv("DISCORD_BOT_TOKEN")
PREFIX = os.getenv("BOT_PREFIX", "!")  # Default prefix if not set

EXTENSIONS = os.getenv("EXTENSIONS", "").split(",")

# Intents & Bot Setup
intents = discord.Intents.default()
intents.members = True  # Enable member intents
intents.messages = True
intents.guilds = True
intents.message_content = True  # Enable message content intent
bot = commands.Bot(command_prefix=PREFIX, intents=intents, help_command=None)  # Disable default help, using custom help
tree = bot.tree

# First user heuristic tracking
newly_joined_guilds = set()  # Track guilds that just joined for first user detection

# Global dictionary to track user command timestamps
user_command_timestamps = {}

# Prompts loading (used by bot.py commands)
joke_insult_prompt = prompts.joke_insult_prompt
joke_dad_prompt = prompts.joke_dad_prompt
joke_gen_prompt = prompts.joke_gen_prompt

@bot.event
async def on_ready():
    await bot.wait_until_ready()  # Ensure bot is fully ready before proceeding
    logging.info(f"🤖 SamosaBot Version: {__version__}")
    logging.info(f'Logged in as {bot.user}')

    for ext in EXTENSIONS:
        if not ext.strip():  # Skip empty extensions
            continue
        try:
            await bot.load_extension(ext.strip())
            logging.info(f"[SUCCESS] Loaded extension: {ext.strip()}")
        except commands.ExtensionAlreadyLoaded:
            logging.warning(f"Extension '{ext.strip()}' is already loaded. Skipping.")
        except Exception as e:
            logging.error(f"[ERROR] Failed to load extension '{ext.strip()}': {e}", exc_info=True)

    # Wait for cogs to fully register commands
    await asyncio.sleep(2)
    logging.info("Waiting for cogs to register commands...")

    # Log all registered commands for debugging
    all_commands = tree.get_commands()
    command_names = [cmd.name for cmd in all_commands]
    logging.info(f"[DEBUG] Registered commands ({len(command_names)}): {', '.join(sorted(command_names))}")

    # Sync slash commands globally with retry
    # NOTE: We use global-only sync (not per-guild) for the following reasons:
    # 1. Discord's recommended approach for production bots
    # 2. Simpler, more reliable - single sync point reduces failure modes
    # 3. Avoids conflicts where guild sync can override global commands
    # 4. Better rate limit handling - fewer API calls, global sync has higher limits
    # 5. Automatic propagation - new guilds get commands automatically (after ~1 hour propagation)
    # Trade-off: Commands may take up to 1 hour to appear in existing guilds after bot restart,
    # but this is acceptable for production stability and reliability.
    for attempt in range(3):
        try:
            synced = await tree.sync(guild=None)
            all_commands = tree.get_commands()
            command_names = [cmd.name for cmd in all_commands]
            logging.info(f"[SUCCESS] Synced {len(synced)} commands to Discord (registered: {len(command_names)})")
            logging.info(f"[DEBUG] Synced command names: {[cmd.name for cmd in synced]}")
            if len(synced) != len(command_names):
                missing = set(command_names) - {cmd.name for cmd in synced}
                logging.warning(f"[WARNING] {len(missing)} commands registered but not synced: {missing}")
            break
        except Exception as e:
            logging.error(f"[ERROR] Failed to sync commands globally (attempt {attempt + 1}/3): {e}", exc_info=True)
            if attempt < 2:
                await asyncio.sleep(2)

    # Register existing guilds with metadata (separate from command sync)
    for guild in bot.guilds:
        try:
            register_guild_with_metadata(guild, "JOINED")
            logging.info(f"[SUCCESS] Registered guild metadata for {guild.name} ({guild.id})")
        except Exception as e:
            logging.error(f"[ERROR] Failed to register guild metadata for {guild.name} ({guild.id}): {e}")

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
    """Handle interactions (slash commands) for throttling, first user heuristic, and daily command tracking."""
    if interaction.type == discord.InteractionType.application_command and interaction.guild:
        # Extract command name for throttling
        # For slash commands, command name is in interaction.data["name"]
        command_name = ""
        if hasattr(interaction, "data") and isinstance(interaction.data, dict):
            command_name = interaction.data.get("name", "")
        elif hasattr(interaction, "command") and interaction.command:
            command_name = interaction.command.name
        
        # Check throttling (same logic as prefix commands)
        retry_after = throttle.check_command_throttle(interaction.user.id, command_name)
        
        if retry_after > 0:
            # User is on cooldown - respond with ephemeral message
            try:
                if not interaction.response.is_done():
                    await interaction.response.send_message(
                        f"⏳ Slow down {interaction.user.mention}! Try again in {math.ceil(retry_after)} seconds.",
                        ephemeral=True
                    )
                else:
                    await interaction.followup.send(
                        f"⏳ Slow down {interaction.user.mention}! Try again in {math.ceil(retry_after)} seconds.",
                        ephemeral=True
                    )
            except Exception as e:
                logging.error(f"Error sending cooldown message: {e}")
            return  # Don't process the command
        
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
    Global error handler for prefix command errors.
    Points users to help command for guidance.
    """
    if isinstance(error, commands.CommandNotFound):
        await ctx.send(f"❌ Unknown command. Use `{ctx.prefix}help` to see all commands.")
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
    elif isinstance(error, commands.MissingRequiredArgument):
        command_name = ctx.command.name if ctx.command else "command"
        await ctx.send(f"❌ Missing required arguments. Use `{ctx.prefix}help {command_name}` for usage.")
    elif isinstance(error, (commands.BadArgument, commands.TooManyArguments)):
        command_name = ctx.command.name if ctx.command else "command"
        await ctx.send(f"❌ Invalid arguments. Use `{ctx.prefix}help {command_name}` for usage.")
    else:
        # Use standardized error handler for unknown errors
        command_name = ctx.command.name if ctx.command else "unknown"
        await error_handler.handle_error(error, ctx, command_name)

@tree.error
async def on_app_command_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
    """
    Global error handler for slash command errors.
    Uses standardized error handling framework.
    """
    # Extract command name if available
    command_name = ""
    if hasattr(interaction, "command") and interaction.command:
        command_name = interaction.command.name
    elif hasattr(interaction, "data") and isinstance(interaction.data, dict):
        command_name = interaction.data.get("name", "")
    
    # Use standardized error handler
    await error_handler.handle_error(error, interaction, command_name)

# Wrap bot.run in a try-except block to handle unexpected crashes
try:
    keep_alive.init_reload(bot)  # Register /reload endpoint (developer only; requires RELOAD_SECRET)
    keep_alive.keep_alive()  # Start the background web server
    bot.run(TOKEN)
except Exception as e:
    logging.error(f"[ERROR] Bot encountered an unexpected issue: {e}")
