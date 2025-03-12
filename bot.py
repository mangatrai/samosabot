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
from replit import db  # Import Replit Database

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
qotd_channels = {
}  # Dictionary to store QOTD channel IDs per server  # Store the channel ID dynamically for scheduled QOTD

# QOTD prompt
qotd_prompt = "Generate an engaging Question of the Day for a Discord server. The question should be thought-provoking, fun, and suitable for group discussions. Don't add Question of the Day at beginning and also keep it single sentence. Example: 'What's the most useless talent you have?'"

#jokes prompt
joke_insult_prompt = f"Generate a witty and humorous insult joke. It should roast someone in a fun and clever way, making sure it's playful and not overly offensive. Format the joke strictly as follows: 'Setup sentence. Punchline sentence. Avoid generic responses and ensure it's unique."

joke_dad_prompt = f"Tell me a fresh and funny dad joke. Ensure it's unique and not a common one. Format the joke strictly as follows: 'Setup sentence. Punchline sentence.' Example: 'Why did the scarecrow win an award? Because he was outstanding in his field.' Here is a random number to force variation: {random.randint(1, 1000000)}. dont return the random number in response"

joke_gen_prompt = f"Tell me a fresh, unpredictable, and humorous joke. Use different topics like animals, professions, technology, relationships, and daily life. Do not repeat previous jokes. Format the joke strictly as follows: 'Setup sentence. Punchline sentence.' Example: 'Why don’t skeletons fight each other? They don’t have the guts.' Here is a random number to force variation: {random.randint(1, 1000000)}.dont return the random number in response"

# Pickup prompt
pickup_prompt = (
    f"Generate a highly flirty, witty, and playful pick-up line. "
    f"The line should be humorous but never offensive, misogynistic, or inappropriate. "
    f"Ensure every response is **completely unique**—avoid using common or overused themes. "
    f"Mix up different styles, including wordplay, pop culture references, unexpected twists, and creative metaphors. "
    f"Each pick-up line should sound **fresh and original**, not a slight variation of previous ones. "
    f"Here is a random number to force variation: {random.randint(1, 1000000)} (do not return this number in the response). "
    f"Example: 'Are you a magician? Because whenever I look at you, everyone else disappears.' "
)


# Load scheduled QOTD channels from Replit DB
def load_qotd_schedules():
    if "qotd_channels" in db:
        return dict(db["qotd_channels"])  # Convert from Replit DB format
    return {}


# Save scheduled QOTD channels to Replit DB
def save_qotd_schedules():
    db["qotd_channels"] = qotd_channels  # Store in Replit DB


# Initialize QOTD storage from Replit DB
qotd_channels = load_qotd_schedules()


# Function to generate OpenAI content
def format_joke(response_text):
    if '' in response_text:
        return response_text  # If already formatted correctly with a newline
    if '. ' in response_text:
        parts = response_text.split('. ', 1)
        return f"{parts[0]}.{parts[1]}"
    return response_text


# Trivia Logic (Handles Both Prefix & Slash Commands)
async def start_trivia(source,
                       category: str = "general",
                       num_questions: int = 10,
                       is_slash: bool = False):
    guild_id = source.guild.id if isinstance(
        source, commands.Context) else source.guild_id
    user_name = source.user.display_name if is_slash else source.author.display_name  # Get the user's name

    if guild_id in active_trivia_games:
        if is_slash:
            await source.response.send_message(
                "❌ A trivia game is already running in this server. Use `/trivia stop` to end it first.",
                ephemeral=True)
        else:
            await source.send(
                "❌ A trivia game is already running in this server. Use `!trivia stop` to end it first."
            )
        return

    active_trivia_games[guild_id] = {
        "questions_asked": 0,
        "max_questions": num_questions,
        "scores": {}
    }

    #if is_slash:
    #    await source.response.defer()  # Acknowledge interaction before sending multiple messages

    # ✅ **Acknowledge that the game has started**
    if is_slash:
        await source.response.defer(
        )  # Acknowledge command to prevent "Application did not respond"
        await asyncio.sleep(1)  # Short delay to ensure defer is processed
        await source.followup.send(
            f"🎉 {user_name} has started a {category} trivia game! First question in 30 seconds..."
        )
    else:
        await source.send(
            f"🎉 {user_name} has started a {category} trivia game! First question in 30 seconds..."
        )

    # ✅ **Wait 30 seconds before posting the first question**
    await asyncio.sleep(30)

    for _ in range(num_questions):
        # **Check if trivia was stopped before generating a new question**
        if guild_id not in active_trivia_games:
            return  # Exit loop if the game was stopped
        
        # **Reset wrong attempts for the new question**
        active_trivia_games[guild_id]["wrong_attempts"] = {}

        content = generate_openai_prompt(
            f"Generate a unique and engaging trivia question in the category of {category}. "
            f"The question must be fresh and not a duplicate of any previous trivia session. "
            f"Avoid generic or frequently used trivia questions—ensure variety by using diverse topics within the category. "
            f"Vary question structures, wording, and difficulty level to prevent repetitiveness. "
            f"Provide four multiple-choice answers labeled A, B, C, and D. "
            f"Ensure only one correct answer is included, and indicate it clearly. "
            f"Do not mention the category name in the question. "
            f"Do not reuse questions, phrasing, or concepts from recent requests. "
            f"Here is a random seed to force uniqueness: {random.randint(1, 1000000)} (do not return this number in the response). "
            f"Respond in a JSON format. Example: "
            f'{{"question": "Which planet is known as the Red Planet?", '
            f'"options": ["A: Mars", "B: Venus", "C: Jupiter", "D: Saturn"], "correct_answer": "A"}}'
        )

        # Remove markdown JSON formatting if present
        if content.startswith("```json"):
            content = content.strip("```json").strip("```")

        try:
            trivia_data = json.loads(
                content)  # Convert JSON string to dictionary
            question = trivia_data["question"]
            options = "\n".join(
                trivia_data["options"])  # Format options as newline-separated
            correct_answer = trivia_data[
                "correct_answer"]  # Extract correct answer

        except (json.JSONDecodeError, KeyError):
            await source.followup.send(
                "⚠️ Error: Failed to parse trivia question. Skipping this round.",
                ephemeral=True)
            continue  # Skip this question if the response is malformed

        # **Check if trivia was stopped before sending the question**
        if guild_id not in active_trivia_games:
            return  # Exit loop if the game was stopped

        question_number = active_trivia_games[guild_id]["questions_asked"] + 1
        subtext = f"Question {question_number} of {num_questions} | Reply with A, B, C, or D."

        # Send the question properly based on command type
        if is_slash:
            await source.channel.send(
                f"🧠 **Trivia Question {question_number}:** {question}\n{options}\n{subtext}"
            )
        else:
            await source.send(
                f"🧠 **Trivia Question {question_number}:** {question}\n{options}\n{subtext}"
            )

        # Function to check user responses
        def check(m):
            return (m.channel.id
                    == (source.channel_id if is_slash else source.channel.id)
                    and m.content.upper() in ["A", "B", "C", "D"])

        correct_answered = False
        while not correct_answered:
            try:
                response = await bot.wait_for("message",
                                              check=check,
                                              timeout=30.0)

                # **Check if trivia was stopped during user response wait**
                if guild_id not in active_trivia_games:
                    return  # Exit loop if the game was stopped

                user_answer = response.content.upper()
                user_id = response.author.id

                # Initialize user stats in Replit DB if not present
                if f"user_stats_{user_id}" not in db:
                    db[f"user_stats_{user_id}"] = {"correct": 0, "wrong": 0}

                # Retrieve user's stats
                user_stats = db[f"user_stats_{user_id}"]

                if user_answer == correct_answer:
                    active_trivia_games[guild_id]["scores"][
                        user_id] = active_trivia_games[guild_id]["scores"].get(
                            user_id, 0) + 1
                    # Update persistent stats in Replit DB
                    user_stats["correct"] += 1
                    db[f"user_stats_{user_id}"] = user_stats  # Save back to DB
                    correct_answered = True  # Exit loop only if the correct answer is given

                    answering_user_name = response.author.display_name  # Get actual user who answered

                    if is_slash:
                        await source.channel.send(
                            f"✅ Correct! {answering_user_name} got it right! Your score: {active_trivia_games[guild_id]['scores'][user_id]}"
                        )
                    else:
                        await response.channel.send(
                            f"✅ Correct! {answering_user_name} got it right! Your score: {active_trivia_games[guild_id]['scores'][user_id]}"
                        )

                    # **Show next question message immediately**
                    if is_slash:
                        await source.channel.send(
                            "⏳ Next question will appear in 15 seconds...")
                    else:
                        await source.send(
                            "⏳ Next question will appear in 15 seconds...")

                    break  # Move to next question
                else:
                    if not active_trivia_games[guild_id].get("wrong_attempts", {}).get(user_id, False):
                        user_stats["wrong"] += 1  # Count wrong answer only once per question
                        db[f"user_stats_{user_id}"] = user_stats  # Save back to DB
                        active_trivia_games[guild_id].setdefault("wrong_attempts", {})[user_id] = True
                    await response.channel.send(
                        f"❌ Wrong! Try again! You have 30 seconds remaining.")

            except asyncio.TimeoutError:
                # **Check if trivia was stopped during timeout**
                if guild_id not in active_trivia_games:
                    return  # Exit loop if the game was stopped

                # If no response is received, send timeout message directly in the channel
                if is_slash:
                    await source.channel.send(
                        f"⏳ Time's up! The correct answer was: {correct_answer}"
                    )
                else:
                    await source.send(
                        f"⏳ Time's up! The correct answer was: {correct_answer}"
                    )

                # **Show next question message immediately**
                if is_slash:
                    await source.channel.send(
                        "⏳ Next question will appear in 15 seconds...")
                else:
                    await source.send(
                        "⏳ Next question will appear in 15 seconds...")

                break  # Move to next question

        # **Check if trivia was stopped before incrementing question count**
        if guild_id not in active_trivia_games:
            return  # Exit loop if the game was stopped

        active_trivia_games[guild_id]["questions_asked"] += 1

        # **Wait for 15 seconds before the next question**
        await asyncio.sleep(15)

    # **Check if trivia was stopped before ending the game**
    if guild_id in active_trivia_games:
        await show_leaderboard(source, guild_id)  # Show results at the end

    if is_slash:
        await source.channel.send("🎉 Trivia game over! Thanks for playing!")
    else:
        await source.send("🎉 Trivia game over! Thanks for playing!")

# Helper function to show the leaderboard
async def show_leaderboard(source, guild_id):
    if guild_id in active_trivia_games:
        sorted_scores = sorted(
            active_trivia_games[guild_id]["scores"].items(),
            key=lambda x: x[1],
            reverse=True
        )

        leaderboard_entries = []
        for user_id, score in sorted_scores:
            user = bot.get_user(user_id) or await bot.fetch_user(user_id)  # Fetch user if not in cache
            leaderboard_entries.append(f"🏆 {user.display_name}: {score} correct")

        leaderboard = "\n".join(leaderboard_entries)

        if isinstance(source, commands.Context):  # Prefix command (!trivia stop)
            await source.send(f"🎉 Trivia game over! Here are the final results:\n{leaderboard}")
        else:  # Slash command (/trivia stop)
            await source.channel.send(f"🎉 Trivia game over! Here are the final results:\n{leaderboard}")

        # Remove the game session
        del active_trivia_games[guild_id]

# Make call to OpenAI to generate Response
def generate_openai_prompt(prompt):
    #print(f"[DEBUG] Sending prompt to OpenAI: {prompt}")
    try:
        response = client.chat.completions.create(model="gpt-4o",
                                                  messages=[{
                                                      "role": "system",
                                                      "content": prompt
                                                  }],
                                                  temperature=1.5,
                                                  top_p=0.9)
        generated_text = response.choices[0].message.content.strip()
        formatted_text = format_joke(generated_text)
        #print(f"[DEBUG] OpenAI Response: {formatted_text}")
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
            print(
                f"[ERROR] QOTD channel {channel_id} not found for server {guild_id}"
            )


@bot.command(name="setqotdchannel")
async def set_qotd_channel(ctx, channel_id: int = None):
    if channel_id is None:
        channel_id = ctx.channel.id  # Default to the current channel if none is provided

    qotd_channels[ctx.guild.id] = channel_id  # Store in memory
    save_qotd_schedules()  # Save to Replit DB

    await ctx.send(
        f"✅ Scheduled QOTD channel set to <#{channel_id}> for this server.")


@bot.command(name="startqotd")
async def start_qotd(ctx):
    if ctx.guild.id not in qotd_channels:
        await ctx.send(
            "[ERROR] No scheduled QOTD channel set for this server. Use !setqotdchannel <channel_id>"
        )
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
    content = generate_openai_prompt(pickup_prompt)
    await ctx.send(f"💘 **Pick-up Line:** {content}")


# Prefix Command for Jokes
@bot.command(name="joke")
async def joke(ctx, category: str = "general"):
    if category == "insult":
        content = generate_openai_prompt(joke_insult_prompt)
    elif category == "dad":
        content = generate_openai_prompt(joke_dad_prompt)
    else:
        content = generate_openai_prompt(joke_gen_prompt)
    await ctx.send(f"🤣 **Joke:** {content}")


# Prefix Command for Trivia (Start/Stop)
@bot.command(name="trivia")
async def trivia(ctx, action: str, category: str = None):
    guild_id = ctx.guild.id

    if action.lower() == "start":
        if not category:
            await ctx.send(
                "❌ You must specify a category to start trivia. Example: `!trivia start History`"
            )
            return
        await start_trivia(ctx, category, is_slash=False)

    elif action.lower() == "stop":
        if guild_id in active_trivia_games:
            await show_leaderboard(ctx, guild_id)  # Show leaderboard before stopping
            await ctx.send("🛑 Trivia game has been stopped.")
        else:
            await ctx.send("❌ No active trivia game found.")

# Prefix Command for Trivia Stats
@bot.command(name="mystats")
async def my_stats(ctx):
    user_id = ctx.author.id

    if f"user_stats_{user_id}" in db:
        stats = db[f"user_stats_{user_id}"]
        await ctx.send(f"📊 **{ctx.author.display_name}'s Trivia Stats:**\n✅ Correct Answers: {stats['correct']}\n❌ Wrong Answers: {stats['wrong']}")
    else:
        await ctx.send(f"📊 **{ctx.author.display_name}'s Trivia Stats:**\nNo trivia history found.")


# Slash Command for Trivia (Start/Stop)
@tree.command(name="trivia", description="Start or stop a trivia game")
@app_commands.describe(
    action="Choose to start or stop a trivia game",
    category="Select a trivia category (required for start, optional for stop)"
)
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
async def slash_trivia(interaction: discord.Interaction,
                       action: str,
                       category: str = None):
    guild_id = interaction.guild_id

    if action == "start":
        if not category:
            await interaction.response.send_message(
                "❌ You must specify a category to start trivia. Example: `/trivia start History`",
                ephemeral=True)
            return
        await start_trivia(interaction, category, is_slash=True)

    elif action == "stop":
        if guild_id in active_trivia_games:
            await show_leaderboard(interaction, guild_id)  # Show leaderboard before stopping
            await interaction.response.send_message(
                "🛑 Trivia game has been stopped.")
        else:
            await interaction.response.send_message(
                "❌ No active trivia game found.")


# Slash Command for QOTD
@tree.command(name="qotd", description="Get a Question of the Day")
async def slash_qotd(interaction: discord.Interaction):
    content = generate_openai_prompt(qotd_prompt)
    await interaction.response.send_message(
        f"🌟 **Question of the Day:** {content}")


# Slash Command with Joke Category Auto-Completion
@tree.command(name="joke", description="Get a joke")
@app_commands.choices(category=[
    app_commands.Choice(name="Dad Joke", value="dad"),
    app_commands.Choice(name="Insult", value="insult"),
    app_commands.Choice(name="General", value="general")
])
async def slash_joke(interaction: discord.Interaction, category: str):
    if category == "insult":
        content = generate_openai_prompt(joke_insult_prompt)
    elif category == "dad":
        content = generate_openai_prompt(joke_dad_prompt)
    else:
        content = generate_openai_prompt(joke_gen_prompt)
    await interaction.response.send_message(f"🤣 **Joke:** {content}")


# Slash Command with Pickup
@tree.command(name="pickup", description="Get a pick-up line")
async def slash_pickup(interaction: discord.Interaction):
    content = generate_openai_prompt(pickup_prompt)
    await interaction.response.send_message(f"💘 **Pick-up Line:** {content}")


@bot.event
async def on_ready():
    await bot.wait_until_ready()  # Ensure bot is ready before syncing
    print(f'Logged in as {bot.user}')
    global qotd_channels
    qotd_channels = load_qotd_schedules()  # Reload QOTD schedules on restart
    print(f"[DEBUG] Loaded QOTD schedules from Replit DB: {qotd_channels}")

    try:
        await tree.sync(guild=None)
        print(
            f"[DEBUG] Synced {len(tree.get_commands())} slash commands globally"
        )
    except Exception as e:
        print(f"[ERROR] Failed to sync commands globally: {e}")

    for guild in bot.guilds:
        try:
            await tree.sync(guild=guild)
            print(
                f"[DEBUG] Synced slash commands for {guild.name} ({guild.id})")
        except Exception as e:
            print(
                f"[ERROR] Failed to sync commands for {guild.name} ({guild.id}): {e}"
            )
    await bot.wait_until_ready()  # Ensure bot is ready before syncing
    print(f'Logged in as {bot.user}')
    try:
        await tree.sync(guild=None)  # Ensure syncing globally
        print(
            f"[DEBUG] Synced {len(tree.get_commands())} slash commands globally"
        )
    except Exception as e:
        print(f"[ERROR] Failed to sync commands: {e}")
    print(f'Logged in as {bot.user}')
    try:
        for guild in bot.guilds:
            await tree.sync()
            print(
                f"[DEBUG] Synced slash commands for {guild.name} ({guild.id})")
            print(
                f"[DEBUG] Synced {len(bot.tree.get_commands())} slash commands"
            )
    except Exception as e:
        print(f"[ERROR] Failed to sync commands: {e}")


# Wrap bot.run in a try-except block to handle unexpected crashes
try:
    from keep_alive import keep_alive  # Import keep_alive function
    keep_alive()  # Start the background web server
    bot.run(TOKEN)
except Exception as e:
    print(f"[ERROR] Bot encountered an unexpected issue: {e}")
