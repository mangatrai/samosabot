"""
FunCog Module

Pickup lines, compliments, and fortune commands (RizzAPI + OpenAI fallback).
"""

import os
import random
import logging
import requests
import discord
from discord.ext import commands
from discord import app_commands

from utils import openai_utils
from configs import prompts

RIZZAPI_URL = os.getenv("RIZZAPI_URL")
pickup_prompt = prompts.pickup_prompt


def get_rizzapi_pickup():
    """Get pickup line from RizzAPI, return None if fails"""
    try:
        response = requests.get(RIZZAPI_URL, timeout=5)
        if response.status_code == 200:
            data = response.json()
            return data.get("text", None)
    except Exception as e:
        logging.warning(f"RizzAPI failed: {e}")
    return None


class FunCog(commands.Cog):
    """Pickup, compliment, and fortune commands."""

    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="pickup", description="Get a pick-up line")
    async def pickup(self, ctx):
        """Get a fun pickup line from RizzAPI or AI fallback."""
        async with ctx.typing():
            content = get_rizzapi_pickup()
            if content is None:
                prompt = pickup_prompt + " Random variation: " + str(random.randint(1, 1000000))
                content = await openai_utils.generate_openai_response(prompt)
            await ctx.send(f"💘 **Pick-up Line:** {content}")

    @commands.command(name="compliment", description="Generate a compliment")
    async def compliment(self, ctx, user: discord.Member = None):
        """Generate a compliment for a user."""
        async with ctx.typing():
            target = user.display_name if user else ctx.author.display_name
            prompt = f"Generate a wholesome and genuine compliment for {target}."
            content = await openai_utils.generate_openai_response(prompt)
            await ctx.send(f"💖 {content}")

    @commands.command(name="fortune", description="Get AI-generated fortune")
    async def fortune(self, ctx):
        """Give a user their AI-powered fortune."""
        async with ctx.typing():
            prompt = "Generate a fun, unpredictable, and mystical fortune-telling message. Keep it engaging and lighthearted."
            content = await openai_utils.generate_openai_response(prompt)
            await ctx.send(f"🔮 **Your fortune:** {content}")

    @app_commands.command(name="pickup", description="Get a pick-up line")
    async def slash_pickup(self, interaction: discord.Interaction):
        await interaction.response.defer()
        content = get_rizzapi_pickup()
        if content is None:
            prompt = pickup_prompt + " Random variation: " + str(random.randint(1, 1000000))
            content = await openai_utils.generate_openai_response(prompt)
        await interaction.followup.send(f"💘 **Pick-up Line:** {content}")


async def setup(bot):
    await bot.add_cog(FunCog(bot))
