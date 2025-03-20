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
    active_trivia_games[guild_id] = {"questions_asked": 1, "max_questions": num_questions, "scores": {}}
    if is_slash:
        await source.response.defer()
        await asyncio.sleep(1)
        await source.followup.send(f"🎉 {user_name} has started a {category} trivia game! First question in {TRIVIA_START_DELAY} seconds...")
    else:
        await source.send(f"🎉 {user_name} has started a {category} trivia game! First question in {TRIVIA_START_DELAY} seconds...")
    await asyncio.sleep(TRIVIA_START_DELAY)
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
    
    for question_data in questions_data:
        if guild_id not in active_trivia_games:
            return
        
        active_trivia_games[guild_id]["wrong_attempts"] = {}
        try:
            question = question_data["question"]
            options = "\n".join(question_data["options"])
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
        subtext = f"Question {question_number} of {num_questions} | Reply with A, B, C, or D.\nYou have {TRIVIA_ANSWER_TIME} seconds to answer."

        if is_slash:
            await source.channel.send(f"🧠 **Trivia Question {question_number}:** {question}\n{options}\n{subtext}")
        else:
            await source.send(f"🧠 **Trivia Question {question_number}:** {question}\n{options}\n{subtext}")
    
        def check(m):
            return (m.channel.id == (source.channel_id if is_slash else source.channel.id) and m.content.upper() in ["A", "B", "C", "D"])
    
        start_time = time.time()
        correct_answered = False
        while not correct_answered:
            try:
                remaining_time = TRIVIA_ANSWER_TIME - (time.time() - start_time)
                if remaining_time <= 0:
                    raise asyncio.TimeoutError
                
                response = await bot.wait_for("message", check=check, timeout=remaining_time)
                
                if guild_id not in active_trivia_games:
                    return
                user_answer = response.content.upper()
                user_id = response.author.id
                answering_user_name = response.author.display_name
                if user_answer == correct_answer:
                    active_trivia_games[guild_id]["scores"][user_id] = active_trivia_games[guild_id]["scores"].get(user_id, 0) + 1
                    astra_db_ops.update_user_stats(user_id, answering_user_name, correct_increment=1)
                    correct_answered = True
                    if is_slash:
                        await source.channel.send(f"✅ Correct! {answering_user_name} got it right! Your score: {active_trivia_games[guild_id]['scores'][user_id]}")
                    else:
                        await response.channel.send(f"✅ Correct! {answering_user_name} got it right! Your score: {active_trivia_games[guild_id]['scores'][user_id]}")
                    
                    if active_trivia_games[guild_id]["questions_asked"] < num_questions:
                        if is_slash:
                            await source.channel.send(f"⏳ Next question will appear in {TRIVIA_QUESTION_BREAK_TIME} seconds...")
                        else:
                            await source.send(f"⏳ Next question will appear in {TRIVIA_QUESTION_BREAK_TIME} seconds...")
                    break # Move to next question
                else:
                    if not active_trivia_games[guild_id].get("wrong_attempts", {}).get(user_id, False):
                        astra_db_ops.update_user_stats(user_id, answering_user_name, wrong_increment=1)
                        active_trivia_games[guild_id].setdefault("wrong_attempts", {})[user_id] = True
                    await response.channel.send(f"❌ Wrong Answer! {answering_user_name} Try again! ⏳ {round(remaining_time)} seconds remaining")
            except asyncio.TimeoutError:
                if guild_id not in active_trivia_games:
                    return
                if is_slash:
                    await source.channel.send(f"⏳ Time's up! The correct answer was: {correct_answer}")
                else:
                    await source.send(f"⏳ Time's up! The correct answer was: {correct_answer}")
                if active_trivia_games[guild_id]["questions_asked"] < num_questions:
                    if is_slash:
                        await source.channel.send(f"⏳ Next question will appear in {TRIVIA_QUESTION_BREAK_TIME} seconds...")
                    else:
                        await source.send(f"⏳ Next question will appear in {TRIVIA_QUESTION_BREAK_TIME} seconds...")
                break
        if guild_id not in active_trivia_games:
            return
        active_trivia_games[guild_id]["questions_asked"] += 1
        if active_trivia_games[guild_id]["questions_asked"] > num_questions:
            break
        await asyncio.sleep(TRIVIA_QUESTION_BREAK_TIME)
    if guild_id in active_trivia_games:
        await show_leaderboard(source, guild_id, bot)
    if is_slash:
        await source.channel.send("🎉 Trivia game over! Thanks for playing!")
    else:
        await source.send("🎉 Trivia game over! Thanks for playing!")

# Helper function to stop the trivia game
async def stop_trivia(source, guild_id, bot, is_slash = False):
    if guild_id in active_trivia_games:
        await show_leaderboard(source, guild_id, bot)
        active_trivia_games.pop(guild_id, None)
        if is_slash:
            await source.response.send_message("🛑 Trivia game has been stopped.")
        else:
            await source.send("🛑 Trivia game has been stopped.")
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
        sorted_scores = sorted(
            active_trivia_games[guild_id]["scores"].items(),
            key=lambda x: x[1],
            reverse=True
        )

        leaderboard_entries = []
        for user_id, score in sorted_scores:
            user = bot.get_user(user_id) or await bot.fetch_user(user_id)  # Fetch user safely
            if user:
                leaderboard_entries.append(f"🏆 {user.display_name}: {score} correct")
            else:
                leaderboard_entries.append(f"🏆 Unknown User ({user_id}): {score} correct")  # Safe fallback

        leaderboard = "\n".join(leaderboard_entries)

        if isinstance(source, commands.Context):  # Prefix command (!trivia stop)
            await source.send(f"🎉 Trivia game over! Here are the final results:\n{leaderboard}")
        else:  # Slash command (/trivia stop)
            await source.channel.send(f"🎉 Trivia game over! Here are the final results:\n{leaderboard}")

        # Remove the game session
        if guild_id in active_trivia_games:
            active_trivia_games.pop(guild_id, None)