"""
Trivia Game Module

This module implements the interactive trivia game functionality for the Discord bot.
It handles the creation, execution, and termination of trivia game sessions, supporting
both prefix and slash commands. Key features include:

  - Dynamically generating a set of unique trivia questions via OpenAI.
  - Managing the state of an active trivia game per Discord server (guild).
  - Handling user responses with a time limit for each question.
  - Tracking and updating user scores, including correct and wrong attempts.
  - Creating and displaying a trivia leaderboard based on stored statistics.
  - Integrating with AstraDB for persistent storage of user stats and trivia leaderboards.

Configuration parameters (loaded from environment variables):
  - TRIVIA_QUESTION_BREAK_TIME: Delay (in seconds) between trivia questions.
  - TRIVIA_START_DELAY: Delay before the first trivia question is asked.
  - TRIVIA_ANSWER_TIME: Time (in seconds) allowed for users to answer each question.
  - TRIVIA_QUESTION_COUNT: Total number of questions in each trivia session.

Primary functions:
  - start_trivia(source, category, bot, num_questions, is_slash): Starts a trivia game session.
  - stop_trivia(source, guild_id, bot, is_slash): Stops an active trivia game session.
  - create_trivia_leaderboard(): Retrieves and formats the trivia leaderboard from AstraDB.
  - show_leaderboard(source, guild_id, bot): Displays the final trivia game results.

Usage:
  This module is intended to be imported and used as part of the SamosaBot Discord bot's
  command handling system. The trivia game is triggered via user commands, and it utilizes
  asynchronous operations to manage the game flow and user interactions.

Example:
  To start a trivia game, the bot command (or slash command) calls the start_trivia() function,
  which generates trivia questions, sends them to the channel, collects user responses, updates scores,
  and eventually shows a leaderboard upon game completion.
"""

import discord
import json
import asyncio
import time
import random
from utils import astra_db_ops,openai_utils
from discord.ext import commands
import logging
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

TRIVIA_QUESTION_BREAK_TIME = int(os.getenv("TRIVIA_QUESTION_BREAK_TIME", 15))
TRIVIA_START_DELAY = int(os.getenv("TRIVIA_START_DELAY", 30))
TRIVIA_ANSWER_TIME = int(os.getenv("TRIVIA_ANSWER_TIME", 30))
TRIVIA_QUESTION_COUNT = int(os.getenv("TRIVIA_QUESTION_COUNT", 10))

active_trivia_games = {}

async def get_user_display_name(bot, user_id, guild_id):
    """Helper function to safely get user display name."""
    try:
        # First try to get user from bot's cache
        user = bot.get_user(user_id)
        if user:
            return user.display_name
        
        # If not in cache, try to fetch from Discord
        user = await bot.fetch_user(user_id)
        if user:
            return user.display_name
        
        # If still not found, try to get from guild members
        guild = bot.get_guild(guild_id)
        if guild:
            member = guild.get_member(user_id)
            if member:
                return member.display_name
        
        # If all else fails, return a fallback name
        return f"User {user_id}"
    except Exception as e:
        logging.error(f"Error getting user display name for {user_id}: {e}")
        return f"User {user_id}"

class TriviaView(discord.ui.View):
    def __init__(self, question_data, correct_answer, timeout=30):
        super().__init__(timeout=timeout)
        self.question_data = question_data
        self.correct_answer = correct_answer
        self.answered_users = set()  # Track who has answered
        self.correct_users = set()   # Track who got it right
        self.wrong_users = set()     # Track who got it wrong
        self.user_answers = {}       # Track each user's answer
        self.user_buttons = {}       # Track which button each user selected
        self.message = None          # Store the message for later updates
        
        # Create buttons for each option
        for option in question_data["options"]:
            button = discord.ui.Button(
                label=option,
                style=discord.ButtonStyle.primary,
                custom_id=f"answer_{option[0]}"  # Use first letter (A, B, C, D) as custom_id
            )
            button.callback = lambda interaction, ans=option[0]: self.answer_callback(interaction, ans)
            self.add_item(button)

    async def answer_callback(self, interaction: discord.Interaction, answer: str):
        # Prevent multiple answers from the same user
        if interaction.user.id in self.answered_users:
            await interaction.response.defer()
            return

        self.answered_users.add(interaction.user.id)
        self.user_answers[interaction.user.id] = answer

        # Track correct/wrong answers
        if answer == self.correct_answer:
            self.correct_users.add(interaction.user.id)
        else:
            self.wrong_users.add(interaction.user.id)

        # Find and disable only the button this user selected
        for item in self.children:
            if isinstance(item, discord.ui.Button):
                if item.custom_id == f"answer_{answer}":
                    # Store the button for this user
                    self.user_buttons[interaction.user.id] = item
                    # Disable only this button
                    item.disabled = True
                    # Set style to blurple (nice purple color that works in both themes)
                    item.style = discord.ButtonStyle.blurple
                    # Update the button's appearance
                    item.emoji = "✋"  # Add a hand emoji to make it more visible

        # Update the message with the new button state
        if self.message:
            await self.message.edit(view=self)
        await interaction.response.edit_message(view=self)

    async def on_timeout(self):
        # When time is up, show final state
        for item in self.children:
            if isinstance(item, discord.ui.Button):
                # Show correct answer in green
                if item.custom_id == f"answer_{self.correct_answer}":
                    item.style = discord.ButtonStyle.success
                    item.emoji = "✅"  # Add checkmark for correct answer
                # Show wrong answers in red
                elif item.custom_id in [f"answer_{answer}" for answer in set(self.user_answers.values())]:
                    item.style = discord.ButtonStyle.danger
                    item.emoji = "❌"  # Add cross for wrong answers
                # Disable all remaining buttons
                item.disabled = True

        # Update the message with the final state
        if self.message:
            await self.message.edit(view=self)
            
        # Wait 10 seconds to show the final state
        await asyncio.sleep(10)

# Trivia Logic (Handles Both Prefix & Slash Commands)
async def start_trivia(source, category: str = "general", bot=None, num_questions: int = TRIVIA_QUESTION_COUNT, is_slash: bool = False):
    guild_id = source.guild.id if isinstance(source, discord.ext.commands.Context) else source.guild_id
    user_name = source.user.display_name if is_slash else source.author.display_name
    
    if guild_id in active_trivia_games:
        if is_slash:
            await source.response.send_message("❌ A trivia game is already running in this server. Use `/trivia stop` to end it first.", ephemeral=True)
        else:
            await source.send("❌ A trivia game is already running in this server. Use `!trivia stop` to end it first.")
        return

    # Initialize game with state
    active_trivia_games[guild_id] = {
        "questions_asked": 1,
        "max_questions": num_questions,
        "scores": {},  # Track correct answers
        "wrong_answers": {},  # Track wrong answers
        "category": category,
        "state": "initializing"  # Track game state
    }

    if is_slash:
        await source.response.defer()
        await asyncio.sleep(1)
        await source.followup.send(f"🎉 {user_name} has started a {category} trivia game! First question in {TRIVIA_START_DELAY} seconds...")
    else:
        await source.send(f"🎉 {user_name} has started a {category} trivia game! First question in {TRIVIA_START_DELAY} seconds...")

    # Split the initial delay into smaller chunks to check for stop command
    for _ in range(TRIVIA_START_DELAY):
        if guild_id not in active_trivia_games:
            return
        await asyncio.sleep(1)

    # Update state to indicate we're generating questions
    if guild_id not in active_trivia_games:
        return
    active_trivia_games[guild_id]["state"] = "generating_questions"

    # Generate questions
    content = openai_utils.generate_openai_response(
        f"Generate {num_questions} unique and engaging trivia questions in the category of {category}. "
        f"The question must be fresh and not a duplicate of any previous trivia session. "
        f"Avoid generic or frequently used trivia questions—ensure variety by using diverse topics within the category. "
        f"Vary question structures, wording, and difficulty level to prevent repetitiveness. "
        f"Provide four multiple-choice answers labeled A, B, C, and D. "
        f"Ensure only one correct answer is included, and indicate it clearly. "
        f"Do not mention the category name in the question. "
        f"Do not reuse questions, phrasing, or concepts from recent requests. "
        f"Here is a random seed to force uniqueness: {random.randint(1, 1000000)} (do not return this number in the response). "
        f"Respond in a JSON array format, where each object has 'question', 'options', and 'correct_answer' keys. "
        f"Example: [{{\"question\": \"...\", \"options\": [\"A: ...\", \"B: ...\", ...], \"correct_answer\": \"A\"}}, ...]"
    )

    # Check if game was stopped during question generation
    if guild_id not in active_trivia_games:
        return

    if content.startswith("```json"):
        content = content.strip("```json").strip("```")

    try:
        questions_data = json.loads(content)
    except (json.JSONDecodeError, KeyError, Exception) as e:
        logging.error(f"Error generating trivia questions: {e}")
        if is_slash:
            await source.followup.send("⚠️ Error: Failed to generate trivia questions. Please try again later.", ephemeral=True)
        else:
            await source.send("⚠️ Error: Failed to generate trivia questions. Please try again later.")
        return

    # Update state to indicate we're playing
    if guild_id not in active_trivia_games:
        return
    active_trivia_games[guild_id]["state"] = "playing"

    for question_data in questions_data:
        if guild_id not in active_trivia_games:
            return

        try:
            question = question_data["question"]
            options = question_data["options"]
            correct_answer = question_data["correct_answer"]
        except (KeyError, TypeError) as e:
            logging.error(f"Error parsing question data: {e}")
            if is_slash:
                await source.followup.send("⚠️ Error: Failed to parse a trivia question. Skipping this round.", ephemeral=True)
            else:
                await source.send("⚠️ Error: Failed to parse a trivia question. Skipping this round.")
            continue

        if guild_id not in active_trivia_games:
            return

        question_number = active_trivia_games[guild_id]["questions_asked"]
        
        # Create embed for the question
        embed = discord.Embed(
            title=f"Question {question_number} of {num_questions}",
            description=question,
            color=discord.Color.blue()
        )
        embed.set_footer(text=f"Category: {category} | Time: {TRIVIA_ANSWER_TIME} seconds")

        # Create view with buttons
        view = TriviaView(question_data, correct_answer, timeout=TRIVIA_ANSWER_TIME)

        # Send the question
        if is_slash:
            message = await source.channel.send(embed=embed, view=view)
        else:
            message = await source.send(embed=embed, view=view)

        # Store the message in the view for later updates
        view.message = message

        # Wait for the view to timeout
        await view.wait()

        # Check if game was stopped during the question
        if guild_id not in active_trivia_games:
            return

        # Add a small delay to ensure the final state is visible
        await asyncio.sleep(1)

        # Create result embed
        result_embed = discord.Embed(
            title=f"Question {question_number} Results",
            description=f"**Question:** {question}\n**Correct Answer:** {correct_answer}",
            color=discord.Color.green()
        )

        # Add correct answers section
        if view.correct_users:
            correct_users_text = "\n".join([
                f"✅ {await get_user_display_name(bot, user_id, guild_id)}" 
                for user_id in view.correct_users
            ])
            result_embed.add_field(name="Correct Answers", value=correct_users_text, inline=False)
            
            # Update scores and stats for correct answers
            for user_id in view.correct_users:
                user_name = await get_user_display_name(bot, user_id, guild_id)
                active_trivia_games[guild_id]["scores"][user_id] = active_trivia_games[guild_id]["scores"].get(user_id, 0) + 1
                astra_db_ops.update_user_stats(user_id, user_name, correct_increment=1)

        # Add wrong answers section
        if view.wrong_users:
            wrong_users_text = "\n".join([
                f"❌ {await get_user_display_name(bot, user_id, guild_id)}" 
                for user_id in view.wrong_users
            ])
            result_embed.add_field(name="Wrong Answers", value=wrong_users_text, inline=False)
            
            # Update stats for wrong answers
            for user_id in view.wrong_users:
                user_name = await get_user_display_name(bot, user_id, guild_id)
                active_trivia_games[guild_id]["wrong_answers"][user_id] = active_trivia_games[guild_id]["wrong_answers"].get(user_id, 0) + 1
                astra_db_ops.update_user_stats(user_id, user_name, wrong_increment=1)

        # Add no answer section if applicable
        if not view.answered_users:
            result_embed.add_field(name="No Answers", value="No one answered this question!", inline=False)

        # Send results
        await message.edit(embed=result_embed, view=None)

        # Update question counter
        active_trivia_games[guild_id]["questions_asked"] += 1
        
        # Break if we've reached the max questions
        if active_trivia_games[guild_id]["questions_asked"] > num_questions:
            break

        # Split the break time into smaller chunks to check for stop command
        for _ in range(TRIVIA_QUESTION_BREAK_TIME):
            if guild_id not in active_trivia_games:
                return
            await asyncio.sleep(1)

    # Show final leaderboard
    if guild_id in active_trivia_games:
        await show_leaderboard(source, guild_id, bot)
        # Remove the game after showing leaderboard
        active_trivia_games.pop(guild_id, None)
    
    if is_slash:
        await source.channel.send("🎉 Trivia game over! Thanks for playing!")
    else:
        await source.send("🎉 Trivia game over! Thanks for playing!")

# Helper function to stop the trivia game
async def stop_trivia(source, guild_id, bot, is_slash = False):
    if guild_id in active_trivia_games:
        try:
            # Get the game data
            game_data = active_trivia_games[guild_id]
            game_state = game_data.get("state", "unknown")
            
            # Create a result embed
            embed = discord.Embed(
                title="🎮 Trivia Game Stopped",
                description=f"Game in category: {game_data.get('category', 'general')}",
                color=discord.Color.red()
            )
            
            # Add state information
            if game_state == "initializing":
                embed.description += "\nGame was stopped before questions were generated."
            elif game_state == "generating_questions":
                embed.description += "\nGame was stopped while generating questions."
            elif game_state == "playing":
                embed.description += "\nGame was stopped during play."
            
            # Add current scores if any
            if game_data.get("scores") or game_data.get("wrong_answers"):
                scores_text = []
                # Add users with correct answers
                for user_id, score in game_data.get("scores", {}).items():
                    try:
                        user_name = await get_user_display_name(bot, user_id, guild_id)
                        wrong_count = game_data.get("wrong_answers", {}).get(user_id, 0)
                        scores_text.append(f"{user_name}: ✅ {score} | ❌ {wrong_count}")
                    except Exception as e:
                        logging.error(f"Error getting user name for {user_id}: {e}")
                        continue
                
                # Add users with only wrong answers
                for user_id, wrong_count in game_data.get("wrong_answers", {}).items():
                    if user_id not in game_data.get("scores", {}):
                        try:
                            user_name = await get_user_display_name(bot, user_id, guild_id)
                            scores_text.append(f"{user_name}: ❌ {wrong_count}")
                        except Exception as e:
                            logging.error(f"Error getting user name for {user_id}: {e}")
                            continue
                
                if scores_text:
                    embed.add_field(
                        name="Current Scores",
                        value="\n".join(scores_text),
                        inline=False
                    )
            
            # Send the embed
            if is_slash:
                await source.response.send_message(embed=embed)
            else:
                await source.send(embed=embed)
            
            # Remove the game from active games
            active_trivia_games.pop(guild_id, None)
            
        except Exception as e:
            logging.error(f"Error stopping trivia game: {e}")
            error_message = "An error occurred while stopping the trivia game."
            if is_slash:
                await source.response.send_message(error_message, ephemeral=True)
            else:
                await source.send(error_message)
    else:
        if is_slash:
            await source.response.send_message("❌ No active trivia game found.")
        else:
            await source.send("❌ No active trivia game found.")

# Helper function to create a trivia leaderboard
def create_trivia_leaderboard():
    leaderboard_data = astra_db_ops.get_trivia_leaderboard()

    if leaderboard_data:
        # Define fixed column widths for better alignment and presentation
        col_rank = 6
        col_user = 20
        col_correct = 10
        
        # Build header with emojis for each column
        header = f"{'🏆 Rank':<{col_rank}} {'👤 User':<{col_user}} {'✅ Correct':<{col_correct}}"
        # Use a decorative separator (em-dash)
        separator = "─" * (col_rank + col_user + col_correct +  3)
        table_rows = [header, separator]
        
        # Build each row with fixed width formatting
        for rank, entry in enumerate(leaderboard_data, start=1):
            username = entry['username'][:col_user]  # Truncate username if it's too long
            row = f"{rank:<{col_rank}} {username:<{col_user}} {entry['total_correct']:<{col_correct}}"
            table_rows.append(row)
        
        leaderboard_table = "\n".join(table_rows)
        return f"📊 **Trivia Leaderboard:**\n```{leaderboard_table}```"
    else:
        return "📊 **Trivia Leaderboard:**\nNo scores yet!"

# Helper function to show the leaderboard
async def show_leaderboard(source, guild_id, bot):
    if guild_id in active_trivia_games:
        try:
            game_data = active_trivia_games[guild_id]
            
            # Create an embed for the final results
            embed = discord.Embed(
                title="🎮 Final Trivia Results",
                description=f"Category: {game_data.get('category', 'general')}",
                color=discord.Color.gold()
            )
            
            # Sort scores by points
            sorted_scores = sorted(
                game_data["scores"].items(),
                key=lambda x: x[1],
                reverse=True
            )
            
            if sorted_scores or game_data.get("wrong_answers"):
                # Create a formatted leaderboard for correct answers
                correct_scores_text = []
                for rank, (user_id, score) in enumerate(sorted_scores, 1):
                    user_name = await get_user_display_name(bot, user_id, guild_id)
                    wrong_count = game_data["wrong_answers"].get(user_id, 0)
                    correct_scores_text.append(f"{rank}. {user_name}: ✅ {score} | ❌ {wrong_count}")
                
                if correct_scores_text:
                    embed.add_field(
                        name="🏆 Final Scores",
                        value="\n".join(correct_scores_text),
                        inline=False
                    )
                
                # Add users who only got wrong answers
                wrong_only_users = []
                for user_id, wrong_count in game_data.get("wrong_answers", {}).items():
                    if user_id not in game_data["scores"]:
                        user_name = await get_user_display_name(bot, user_id, guild_id)
                        wrong_only_users.append(f"{user_name}: ❌ {wrong_count}")
                
                if wrong_only_users:
                    embed.add_field(
                        name="❌ Wrong Answers Only",
                        value="\n".join(wrong_only_users),
                        inline=False
                    )
            else:
                embed.add_field(
                    name="No Scores",
                    value="No one participated in this game.",
                    inline=False
                )
            
            # Send the embed
            if isinstance(source, commands.Context):  # Prefix command (!trivia stop)
                await source.send(embed=embed)
            else:  # Slash command (/trivia stop)
                await source.channel.send(embed=embed)
                
        except Exception as e:
            logging.error(f"Error showing leaderboard: {e}")
            error_message = "An error occurred while showing the leaderboard."
            if isinstance(source, commands.Context):
                await source.send(error_message)
            else:
                await source.channel.send(error_message)