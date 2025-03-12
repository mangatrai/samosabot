import discord
from openai import OpenAI
import random
import asyncio
import os
from discord.ext import commands, tasks
from discord import app_commands
from discord.ui import Select, View
from dotenv import load_dotenv
import json

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

# Trivia Score Tracking
trivia_scores = {}
active_trivia_games = {}

# QOTD Schedule Tracking
qotd_channel_id = None  # Store the channel ID dynamically for scheduled QOTD
qotd_channels = {}  # Dictionary to store QOTD channel IDs per server  # Store the channel ID dynamically for scheduled QOTD

# QOTD prompt
qotd_prompt = "Generate an engaging Question of the Day for a Discord server. The question should be thought-provoking, fun, and suitable for group discussions. Don't add Question of the Day at beginning and also keep it single sentence. Example: 'What's the most useless talent you have?'"

#jokes prompt
joke_insult_prompt = f"Generate a witty and humorous insult joke. It should roast someone in a fun and clever way, making sure it's playful and not overly offensive. Format the joke strictly as follows: 'Setup sentence. Punchline sentence. Avoid generic responses and ensure it's unique."

joke_dad_prompt = f"Tell me a fresh and funny dad joke. Ensure it's unique and not a common one. Format the joke strictly as follows: 'Setup sentence. Punchline sentence.' Example: 'Why did the scarecrow win an award? Because he was outstanding in his field.' Here is a random number to force variation: {random.randint(1, 1000000)}. dont return the random number in response"

joke_gen_prompt = f"Tell me a fresh, unpredictable, and humorous joke. Use different topics like animals, professions, technology, relationships, and daily life. Do not repeat previous jokes. Format the joke strictly as follows: 'Setup sentence. Punchline sentence.' Example: 'Why don’t skeletons fight each other? They don’t have the guts.' Here is a random number to force variation: {random.randint(1, 1000000)}.dont return the random number in response"

# Function to generate OpenAI content
def format_joke(response_text):
    if '' in response_text:
        return response_text  # If already formatted correctly with a newline
    if '. ' in response_text:
        parts = response_text.split('. ', 1)
        return f"{parts[0]}.{parts[1]}"
    return response_text

# Trivia Logic (Handles Both Prefix & Slash Commands)
async def start_trivia(source, category: str = "general", num_questions: int = 5, is_slash: bool = False):
    guild_id = source.guild.id if isinstance(source, commands.Context) else source.guild_id

    if guild_id in active_trivia_games:
        if is_slash:
            await source.response.send_message("❌ A trivia game is already running in this server. Use `/trivia stop` to end it first.", ephemeral=True)
        else:
            await source.send("❌ A trivia game is already running in this server. Use `!trivia stop` to end it first.")
        return

    active_trivia_games[guild_id] = {
        "questions_asked": 0,
        "max_questions": num_questions,
        "scores": {}
    }

    if is_slash:
        await source.response.defer()  # Acknowledge interaction before sending multiple messages

    for _ in range(num_questions):
        content = generate_openai_prompt(
            f"Ask a trivia question in the category of {category} with four multiple-choice answers. "
            f"Provide four options labeled A, B, C, and D, and indicate the correct answer clearly in the response. "
            f"Do not include the category name in the question. "
            f"Ensure the questions are unique and not repeated. "
            f"Here is a random number to force variation: {random.randint(1, 1000000)} (do not return this number in the response). "
            f"Respond in a JSON format. Example: "
            f'{{"question": "What is the capital of France?", "options": ["A: Paris", "B: London", "C: Berlin", "D: Madrid"], "correct_answer": "A"}}'
        )

        try:
            trivia_data = json.loads(content)  # Convert JSON string to dictionary
            question = trivia_data["question"]
            options = "\n".join(trivia_data["options"])  # Format options as newline-separated
            correct_answer = trivia_data["correct_answer"]  # Extract correct answer

        except (json.JSONDecodeError, KeyError):
            await source.followup.send("⚠️ Error: Failed to parse trivia question. Skipping this round.", ephemeral=True)
            continue  # Skip this question if the response is malformed

        # Send the question properly based on command type
        if is_slash:
            await source.followup.send(f"🧠 **Trivia Question:** {question}\n{options}\nReply with A, B, C, or D to answer.")
        else:
            await source.send(f"🧠 **Trivia Question:** {question}\n{options}\nReply with A, B, C, or D to answer.")

        # Function to check user responses
        def check(m):
            if is_slash:
                return m.author.id == source.user.id and m.channel.id == source.channel_id and m.content.upper() in ["A", "B", "C", "D"]
            else:
                return m.author.id == source.author.id and m.channel.id == source.channel.id and m.content.upper() in ["A", "B", "C", "D"]

        while True:
            try:
                response = await bot.wait_for("message", check=check, timeout=30.0)
                user_answer = response.content.upper()

                user_id = response.author.id

                # Update and track user scores
                active_trivia_games[guild_id]["scores"][user_id] = active_trivia_games[guild_id]["scores"].get(user_id, 0) + (1 if user_answer == correct_answer else 0)

                if user_answer == correct_answer:
                    if is_slash:
                        await source.followup.send(f"✅ Correct! Your score: {active_trivia_games[guild_id]['scores'][user_id]}")
                    else:
                        await response.channel.send(f"✅ Correct! Your score: {active_trivia_games[guild_id]['scores'][user_id]}")
                    break  # Move to next question
                else:
                    if is_slash:
                        await source.followup.send(f"❌ Wrong! Try again! You have 30 seconds remaining.", ephemeral=True)
                    else:
                        await response.channel.send(f"❌ Wrong! Try again! You have 30 seconds remaining.")

            except asyncio.TimeoutError:
                await response.channel.send(f"⏳ Time's up! The correct answer was: {correct_answer}")
                break  # Move to next question

        if guild_id in active_trivia_games:
            active_trivia_games[guild_id]["questions_asked"] += 1

    # End game
    del active_trivia_games[guild_id]

    if is_slash:
        await source.followup.send("🎉 Trivia game over! Thanks for playing!")
    else:
        await source.send("🎉 Trivia game over! Thanks for playing!")


# Make call to OpenAI to generate Response
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

# Prefix Command for QOTD
@bot.command(name="qotd")
async def qotd(ctx):
    content = generate_openai_prompt(qotd_prompt)
    await ctx.send(f"🌟 **Question of the Day:** {content}")

# Prefix Command for Pick-up Line
@bot.command(name="pickup")
async def pickup(ctx):
    content = generate_openai_prompt("Give me a flirty pick-up line.")
    await ctx.send(f"💘 **Pick-up Line:** {content}")

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

# Prefix Command for Trivia (Start/Stop)
@bot.command(name="trivia")
async def trivia(ctx, action: str, category: str = None):
    guild_id = ctx.guild.id

    if action.lower() == "start":
        if not category:
            await ctx.send("❌ You must specify a category to start trivia. Example: `!trivia start History`")
            return
        await start_trivia(ctx, category, is_slash=False)

    elif action.lower() == "stop":
        if guild_id in active_trivia_games:
            del active_trivia_games[guild_id]
            await ctx.send("🛑 Trivia game has been stopped.")
        else:
            await ctx.send("❌ No active trivia game found.")

# Slash Command for Trivia (Start/Stop)
@tree.command(name="trivia", description="Start or stop a trivia game")
@app_commands.describe(action="Choose to start or stop a trivia game", category="Select a trivia category (required for start, optional for stop)")
@app_commands.choices(action=[
    app_commands.Choice(name="Start", value="start"),
    app_commands.Choice(name="Stop", value="stop")
])
@app_commands.choices(category=[
    app_commands.Choice(name="History", value="History"),
    app_commands.Choice(name="Science", value="Science"),
    app_commands.Choice(name="Geography", value="Geography"),
    app_commands.Choice(name="Sports", value="Sports"),
    app_commands.Choice(name="Movies", value="Movies"),
    app_commands.Choice(name="Animals", value="Animals")
])
async def slash_trivia(interaction: discord.Interaction, action: str, category: str = None):
    guild_id = interaction.guild_id

    if action == "start":
        if not category:
            await interaction.response.send_message("❌ You must specify a category to start trivia. Example: `/trivia start History`", ephemeral=True)
            return
        await start_trivia(interaction, category, is_slash=True)

    elif action == "stop":
        if guild_id in active_trivia_games:
            del active_trivia_games[guild_id]
            await interaction.response.send_message("🛑 Trivia game has been stopped.")
        else:
            await interaction.response.send_message("❌ No active trivia game found.")

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

# Slash Command with Pickup
@tree.command(name="pickup", description="Get a pick-up line")
async def slash_pickup(interaction: discord.Interaction):
    content = generate_openai_prompt("Give me a witty flirty pick-up line.")
    await interaction.response.send_message(f"💘 **Pick-up Line:** {content}")

@bot.event
async def on_ready():
    await bot.wait_until_ready()  # Ensure bot is ready before syncing
    print(f'Logged in as {bot.user}')
    try:
        await tree.sync(guild=None)
        print(f"[DEBUG] Synced {len(tree.get_commands())} slash commands globally")
    except Exception as e:
        print(f"[ERROR] Failed to sync commands globally: {e}")

    for guild in bot.guilds:
        try:
            await tree.sync(guild=guild)
            print(f"[DEBUG] Synced slash commands for {guild.name} ({guild.id})")
        except Exception as e:
            print(f"[ERROR] Failed to sync commands for {guild.name} ({guild.id}): {e}")
    await bot.wait_until_ready()  # Ensure bot is ready before syncing
    print(f'Logged in as {bot.user}')
    try:
        await tree.sync(guild=None)  # Ensure syncing globally
        print(f"[DEBUG] Synced {len(tree.get_commands())} slash commands globally")
    except Exception as e:
        print(f"[ERROR] Failed to sync commands: {e}")
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
