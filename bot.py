import discord
import os
from discord.ext import commands, tasks
from discord import app_commands
from dotenv import load_dotenv
import json
import logging

import astra_db_ops
import openai_utils
import trivia_game
import prompts

# Load environment variables
load_dotenv()
TOKEN = os.getenv("DISCORD_BOT_TOKEN")
PREFIX = os.getenv("BOT_PREFIX", "!")  # Default prefix if not set
# Load environment variables for AstraDB
ASTRA_API_ENDPOINT = os.getenv("ASTRA_API_ENDPOINT")  # AstraDB API endpoint
ASTRA_NAMESPACE = os.getenv("ASTRA_NAMESPACE")  # Your namespace (like a database)
ASTRA_API_TOKEN = os.getenv("ASTRA_API_TOKEN")  # API authentication token
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")  # LOG_LEVEL for logging

# Intents & Bot Setup
intents = discord.Intents.default()
intents.messages = True
intents.guilds = True
intents.message_content = True  # Ensure message content intent is enabled
bot = commands.Bot(command_prefix=PREFIX, intents=intents)
tree = bot.tree

# Convert LOG_LEVEL string to logging level constant
try:
    log_level = getattr(logging, LOG_LEVEL.upper())
except AttributeError:
    print(f"WARNING: Invalid LOG_LEVEL '{LOG_LEVEL}'. Defaulting to INFO.")
    log_level = logging.INFO

# Configure logging
logging.basicConfig(level=log_level, format='%(asctime)s - %(levelname)s - %(message)s')

# QOTD Schedule Tracking
qotd_channels = {}  # Dictionary to store QOTD channel IDs per server  # Store the channel ID dynamically for scheduled QOTD

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

import json

def format_joke(response_text):
    """Parses and formats jokes properly, ensuring setup and punchline appear on separate lines."""
    try:
         # Remove markdown JSON formatting if present
        if response_text.startswith("```json"):
            response_text = response_text.strip("```json").strip("```")
        # ✅ Attempt to parse as JSON
        joke_data = json.loads(response_text)
        setup = joke_data.get("setup", "").strip()
        punchline = joke_data.get("punchline", "").strip()

        # ✅ Ensure both setup & punchline exist
        if setup and punchline:
            return f"🤣 **Joke:**\n{setup}\n{punchline}"

    except json.JSONDecodeError:
        logging.warn(f"[WARNING] Failed to parse JSON: {response_text}")

    # Fallback: If not JSON, attempt to split by first period + space
    if '. ' in response_text:
        parts = response_text.split('. ', 1)
        return f"🤣 **Joke:**\n{parts[0]}.\n{parts[1]}"

    return f"🤣 **Joke:**\n{response_text.strip()}"  # Final fallback to raw text

# Scheduled QOTD Task
@tasks.loop(hours=24)
async def scheduled_qotd():
    for guild_id, channel_id in qotd_channels.items():
        channel = bot.get_channel(channel_id)
        if channel:
            content = openai_utils.generate_openai_prompt(qotd_prompt)
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
    content = openai_utils.generate_openai_prompt(qotd_prompt)
    await ctx.send(f"🌟 **Question of the Day:** {content}")


# Prefix Command for Pick-up Line
@bot.command(name="pickup")
async def pickup(ctx):
    content = openai_utils.generate_openai_prompt(pickup_prompt)
    await ctx.send(f"💘 **Pick-up Line:** {content}")


#Roast Machine
@bot.command(name="roast")
async def roast(ctx, user: discord.Member = None):
    """Generate a witty roast for a user."""
    target = user.display_name if user else ctx.author.display_name
    prompt = f"Generate a witty and humorous roast for {target}. Keep it fun and lighthearted."
    content = openai_utils.generate_openai_prompt(prompt)
    await ctx.send(f"🔥 {content}")

#Compliment Machine
@bot.command(name="compliment")
async def compliment(ctx, user: discord.Member = None):
    """Generate a compliment for a user."""
    target = user.display_name if user else ctx.author.display_name
    prompt = f"Generate a wholesome and genuine compliment for {target}."
    content = openai_utils.generate_openai_prompt(prompt)
    await ctx.send(f"💖 {content}")

#AI-Powered Fortune Teller
@bot.command(name="fortune")
async def fortune(ctx):
    """Give a user their AI-powered fortune."""
    prompt = "Generate a fun, unpredictable, and mystical fortune-telling message. Keep it engaging and lighthearted."
    content = openai_utils.generate_openai_prompt(prompt)
    await ctx.send(f"🔮 **Your fortune:** {content}")

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
        content = openai_utils.generate_openai_prompt(qotd_prompt)
        await interaction.followup.send(f"🌟 **Question of the Day:** {content}")
    except Exception as e:
        logging.error(f"Error in slash_qotd: {e}")
        await interaction.followup.send("❌ An error occurred while fetching the Question of the Day.")

# Slash Command with Pickup
@tree.command(name="pickup", description="Get a pick-up line")
async def slash_pickup(interaction: discord.Interaction):
    content = openai_utils.generate_openai_prompt(pickup_prompt)
    await interaction.response.send_message(f"💘 **Pick-up Line:** {content}")


@bot.event
async def on_ready():
    await bot.wait_until_ready()  # Ensure bot is fully ready before proceeding
    logging.info(f'Logged in as {bot.user}')

    await bot.load_extension("joke_cog")
    await bot.load_extension("trivia_cog")
    await bot.load_extension("utils_cog")
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
            logging.debug(f"[DEBUG] Synced slash commands for {guild.name} ({guild.id})")
        except Exception as e:
            logging.error(f"[ERROR] Failed to sync commands for {guild.name} ({guild.id}): {e}")

@bot.event
async def on_command_error(ctx, error):
    logging.error(f"Command error: {error}")
    await ctx.send(f"An error occurred: {error}")

# Wrap bot.run in a try-except block to handle unexpected crashes
try:
    from keep_alive import keep_alive  # Import keep_alive function
    keep_alive()  # Start the background web server
    bot.run(TOKEN)
except Exception as e:
    logging.error(f"[ERROR] Bot encountered an unexpected issue: {e}")
