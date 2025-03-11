import discord
from openai import OpenAI
import random
import asyncio
import os
from discord.ext import commands, tasks
from discord import app_commands
from discord.ui import Select, View
from dotenv import load_dotenv

# Load environment variables
load_dotenv()
TOKEN = os.getenv("DISCORD_BOT_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
PREFIX = '!'

client = OpenAI(api_key=OPENAI_API_KEY)

# Intents & Bot Setup
intents = discord.Intents.default()
intents.messages = True
intents.guilds = True
intents.message_content = True  # Ensure message content intent is enabled
bot = commands.Bot(command_prefix=PREFIX, intents=intents)
tree = bot.tree

# Scheduled QOTD Task
@tasks.loop(hours=24)
async def scheduled_qotd():
    for guild_id, channel_id in qotd_channels.items():
        channel = bot.get_channel(channel_id)
        if channel:
            content = generate_openai_prompt(qotd_prompt)
            await channel.send(f"🌟 **Question of the Day:** {content}")
        else:
            print(f"[ERROR] QOTD channel {channel_id} not found for server {guild_id}")

@bot.command(name="setqotdchannel")
async def set_qotd_channel(ctx, channel_id: int = None):
    if channel_id is None:
        channel_id = ctx.channel.id  # Default to the current channel if none is provided
    qotd_channels[ctx.guild.id] = channel_id
    await ctx.send(f"✅ Scheduled QOTD channel set to <#{channel_id}> for this server.")

@bot.command(name="startqotd")
async def start_qotd(ctx):
    if ctx.guild.id not in qotd_channels:
        await ctx.send("[ERROR] No scheduled QOTD channel set for this server. Use !setqotdchannel <channel_id>")
    else:
        if not scheduled_qotd.is_running():
            scheduled_qotd.start()
        await ctx.send("✅ Scheduled QOTD started for this server!")

# Trivia Score Tracking
trivia_scores = {}
qotd_channel_id = None  # Store the channel ID dynamically for scheduled QOTD
qotd_channels = {}  # Dictionary to store QOTD channel IDs per server  # Store the channel ID dynamically for scheduled QOTD

# QOTD prompt
qotd_prompt = "Generate an engaging Question of the Day for a Discord server. The question should be thought-provoking, fun, and suitable for group discussions. Don't add Question of the Day at beginning and also keep it single sentence. Example: 'What's the most useless talent you have?'"


#jokes prompt
joke_insult_prompt = f"Generate a witty and humorous insult joke. It should roast someone in a fun and clever way, making sure it's playful and not offensive. Format the joke strictly as follows: 'Setup sentence. Punchline sentence.' Example: 'Why do programmers prefer dark mode? Because light attracts bugs.' Avoid generic responses and ensure it's unique."

joke_dad_prompt = f"Tell me a fresh and funny dad joke. Ensure it's unique and not a common one. Format the joke strictly as follows: 'Setup sentence. Punchline sentence.' Example: 'Why did the scarecrow win an award? Because he was outstanding in his field.' Here is a random number to force variation: {random.randint(1, 10000)}."

joke_gen_prompt = f"Tell me a fresh, unpredictable, and humorous joke. Use different topics like animals, professions, technology, relationships, and daily life. Do not repeat previous jokes. Format the joke strictly as follows: 'Setup sentence. Punchline sentence.' Example: 'Why don’t skeletons fight each other? They don’t have the guts.' Here is a random number to force variation: {random.randint(1, 10000)}."

# Function to generate OpenAI content
def format_joke(response_text):
    if '' in response_text:
        return response_text  # If already formatted correctly with a newline
    if '. ' in response_text:
        parts = response_text.split('. ', 1)
        return f"{parts[0]}.{parts[1]}"
    return response_text

def generate_openai_prompt(prompt):
    print(f"[DEBUG] Sending prompt to OpenAI: {prompt}")
    try:
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "system", "content": prompt}],
            temperature=1.5,
            top_p=0.9
        )
        generated_text = response.choices[0].message.content.strip()
        formatted_text = format_joke(generated_text)
        print(f"[DEBUG] OpenAI Response: {formatted_text}")
        return formatted_text
    except Exception as e:
        print(f"[ERROR] OpenAI API call failed: {e}")
        return "[ERROR] Unable to generate response. Please try again later."

# Prefix Command for QOTD
@bot.command(name="qotd")
async def qotd(ctx):
    content = generate_openai_prompt(qotd_prompt)
    await ctx.send(f"🌟 **Question of the Day:** {content}")

# Prefix Command for Jokes
@bot.command(name="joke")
async def joke(ctx, category: str = "general"):
    if category == "insult":
        content = generate_openai_prompt(
            joke_insult_prompt
        )
    elif category == "dad":
        content = generate_openai_prompt(
            joke_dad_prompt
        )
    else:
        content = generate_openai_prompt(
            joke_gen_prompt
        )
    await ctx.send(f"🤣 **Joke:** {content}")

# Prefix Command for Trivia
@bot.command(name="trivia")
async def trivia(ctx, category: str = "general"):
    content = generate_openai_prompt(f"Ask a {category} trivia question with four multiple-choice answers.")
    await ctx.send(f"🧠 **Trivia Question:** {content}")

# Prefix Command for Pick-up Line
@bot.command(name="pickup")
async def pickup(ctx):
    content = generate_openai_prompt("Give me a flirty pick-up line.")
    await ctx.send(f"💘 **Pick-up Line:** {content}")

# Slash Command for QOTD
@tree.command(name="qotd", description="Get a Question of the Day")
async def slash_qotd(interaction: discord.Interaction):
    content = generate_openai_prompt(qotd_prompt)
    await interaction.response.send_message(f"🌟 **Question of the Day:** {content}")

# Slash Command with Joke Category Auto-Completion
@tree.command(name="joke", description="Get a joke")
@app_commands.choices(category=[
    app_commands.Choice(name="Dad Joke", value="dad"),
    app_commands.Choice(name="Insult", value="insult"),
    app_commands.Choice(name="General", value="general")
])
async def slash_joke(interaction: discord.Interaction, category: str):
    if category == "insult":
        content = generate_openai_prompt(
            joke_insult_prompt
        )
    elif category == "dad":
        content = generate_openai_prompt(
            joke_dad_prompt
        )
    else:
        content = generate_openai_prompt(
            joke_gen_prompt
        )
    await interaction.response.send_message(f"🤣 **Joke:** {content}")

@tree.command(name="trivia", description="Get a trivia question")
@app_commands.choices(category=[
    app_commands.Choice(name="History", value="History"),
    app_commands.Choice(name="Science", value="Science"),
    app_commands.Choice(name="Geography", value="Geography"),
    app_commands.Choice(name="Sports", value="Sports"),
    app_commands.Choice(name="Movies", value="Movies"),
    app_commands.Choice(name="Animals", value="Animals")
])
async def slash_trivia(interaction: discord.Interaction, category: str):
    content = generate_openai_prompt(f"Ask a {category} trivia question with four multiple-choice answers.")
    await interaction.response.send_message(f"🧠 **Trivia Question:** {content}")

@tree.command(name="pickup", description="Get a pick-up line")
async def slash_pickup(interaction: discord.Interaction):
    content = generate_openai_prompt("Give me a flirty pick-up line.")
    await interaction.response.send_message(f"💘 **Pick-up Line:** {content}")

@bot.event
async def on_ready():
    print(f'Logged in as {bot.user}')
    try:
        for guild in bot.guilds:
            await tree.sync()
            print(f"[DEBUG] Synced slash commands for {guild.name} ({guild.id})")
            print(f"[DEBUG] Synced {len(bot.tree.get_commands())} slash commands")
    except Exception as e:
        print(f"[ERROR] Failed to sync commands: {e}")

# Wrap bot.run in a try-except block to handle unexpected crashes
try:
    bot.run(TOKEN)
except Exception as e:
    print(f"[ERROR] Bot encountered an unexpected issue: {e}")
