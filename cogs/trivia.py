"""
TriviaCog Module

This module defines the TriviaCog for the SamosaBot Discord bot. It provides trivia game functionalities, including:
  - Starting a trivia game in a specified category.
  - Stopping an ongoing trivia game.
  - Displaying the trivia leaderboard.
  - Retrieving individual user trivia statistics.

The cog supports both traditional prefix commands (using discord.ext.commands) and modern slash commands (using discord.app_commands). Trivia game logic is managed via the external module 'trivia_game', while user statistics and leaderboard data are handled through 'astra_db_ops'.

Usage:
  Simply load this cog into your Discord bot to enable interactive trivia commands for your server.
"""
import discord
from discord.ext import commands
from discord import app_commands
from utils import astra_db_ops
from games import trivia_game

class TriviaCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="trivia")
    async def trivia(self, ctx, action: str, category: str = None, speed: str = "slow"):
        """
        Start, stop, or view trivia game leaderboard.
        
        Actions:
            start: Start a trivia game (requires category)
            stop: Stop current trivia game
            leaderboard: View top players
        
        Categories: History, Science, Geography, Sports, Movies, Animals, Music, Video Games,
                   Technology, Literature, Mythology, Food & Drink, Celebrities, Riddles,
                   Space, Cars, Marvel & DC, Holidays
        
        Speed: slow (default) or fast
        Uses interactive buttons for answering questions.
        """
        guild_id = ctx.guild.id

        if action.lower() == "start":
            if not category:
                await ctx.send(
                    "❌ You must specify a category to start trivia. Example: `!trivia start History`"
                )
                return
            await trivia_game.start_trivia(ctx, category, self.bot, is_slash=False, speed=speed)

        elif action.lower() == "stop":
            await trivia_game.stop_trivia(ctx, guild_id, self.bot)

        elif action.lower() == "leaderboard":
            await ctx.send(trivia_game.create_trivia_leaderboard())

    @commands.command(name="mystats")
    async def my_stats(self, ctx):
        """View your personal trivia statistics (correct and wrong answers)."""
        user_id = ctx.author.id
        stats = astra_db_ops.get_user_stats(user_id)

        await ctx.send(
            f"📊 **{ctx.author.display_name}'s Trivia Stats:**\n✅ Correct Answers: {stats['correct']}\n❌ Wrong Answers: {stats['wrong']}"
        )

    @app_commands.command(name="trivia", description="Start or stop a trivia game")
    async def slash_trivia(self, interaction: discord.Interaction, action: str, category: str = None, speed: str = "slow"):
        """
        Start, stop, or view trivia game leaderboard (slash command).
        
        Uses interactive buttons for answering questions.
        Tracks scores and maintains leaderboards.
        """
    @app_commands.describe(
        action="Choose to start or stop a trivia game",
        category="Select a trivia category (required for start, optional for stop)",
        speed="Choose the pace of the trivia game (slow or fast)"
    )
    @app_commands.choices(action=[
        app_commands.Choice(name="Start", value="start"),
        app_commands.Choice(name="Stop", value="stop"),
        app_commands.Choice(name="Leaderboard", value="leaderboard")
    ])
    @app_commands.choices(speed=[
        app_commands.Choice(name="Slow", value="slow"),
        app_commands.Choice(name="Fast", value="fast")
    ])
    @app_commands.choices(category=[
        app_commands.Choice(name="History", value="History"),
        app_commands.Choice(name="Science", value="Science"),
        app_commands.Choice(name="Geography", value="Geography"),
        app_commands.Choice(name="Sports", value="Sports"),
        app_commands.Choice(name="Movies", value="Movies"),
        app_commands.Choice(name="Animals", value="Animals"),
        app_commands.Choice(name="Music", value="Music"),
        app_commands.Choice(name="Video Games", value="Video Games"),
        app_commands.Choice(name="Technology", value="Technology"),
        app_commands.Choice(name="Literature", value="Literature"),
        app_commands.Choice(name="Mythology", value="Mythology"),
        app_commands.Choice(name="Food & Drink", value="Food & Drink"),
        app_commands.Choice(name="Celebrities", value="Celebrities"),
        app_commands.Choice(name="Riddles & Brain Teasers", value="Riddles"),
        app_commands.Choice(name="Space & Astronomy", value="Space"),
        app_commands.Choice(name="Cars & Automobiles", value="Cars"),
        app_commands.Choice(name="Marvel & DC", value="Comics"),
        app_commands.Choice(name="Holidays & Traditions", value="Holidays")
    ])
    async def slash_trivia(self, interaction: discord.Interaction, action: str, category: str = None, speed: str = "slow"):
        guild_id = interaction.guild_id

        if action == "start":
            if not category:
                await interaction.response.send_message(
                    "❌ You must specify a category to start trivia. Example: `/trivia start History`",
                    ephemeral=True)
                return
            await trivia_game.start_trivia(interaction, category, self.bot, is_slash=True, speed=speed)

        elif action == "stop":
            await trivia_game.stop_trivia(interaction, guild_id, self.bot, is_slash=True)
        elif action == "leaderboard":
            await interaction.response.send_message(trivia_game.create_trivia_leaderboard())

async def setup(bot):
    await bot.add_cog(TriviaCog(bot))