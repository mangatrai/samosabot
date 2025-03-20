"""
AskCog Module

This module defines the AskCog cog for the Discord bot, enabling users to ask questions or request image generation
via both prefix commands and slash commands. It integrates with OpenAI's API to first check the intent and safety
of a user prompt and then generate an appropriate response—either text or image. Additionally, the module enforces
a daily request limit per user and logs each query and its corresponding response to AstraDB for tracking and statistics.

Features:
  - Provides two commands: the traditional prefix command (!asksamosa) and a modern slash command (/ask).
  - Utilizes the generate_openai_response function from openai_utils to perform intent checking and content generation.
  - Enforces daily limits using functions from astra_db_ops (get_daily_request_count, increment_daily_request_count, insert_user_request).
  - Sends responses as embedded messages in Discord, including image embedding if applicable.

Usage:
  Load this cog into your Discord bot to enable interactive question-answering features with built-in safety and logging.
"""

import discord
from discord.ext import commands
import logging
import os
from dotenv import load_dotenv
from discord import app_commands

from utils.astra_db_ops import (
    increment_daily_request_count,
    get_daily_request_count,
    insert_user_request
)

# Import the new generate_openai_response function
from utils.openai_utils import generate_openai_response

# Load environment variables
load_dotenv()

USER_DAILY_QUE_LIMIT = int(os.getenv("USER_DAILY_QUE_LIMIT", 30))

class AskCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def generate_response(self, prompt):
        try:
            # First, check the prompt's intent and if it's allowed.
            decision = generate_openai_response(prompt, intent="intent")
            if not decision.get("isAllowed", False):
                return "Your question contains sensitive content and is not allowed."
            
            determined_intent = decision.get("intent", "text")
            # Now, generate the actual response based on the determined intent.
            response = generate_openai_response(prompt, intent=determined_intent)
            return response
        except Exception as e:
            logging.error(f"Error generating response: {e}")
            return "An error occurred while generating the response."

    @commands.command(name="asksamosa")
    async def ask_samosa(self, ctx, *, question):
        await self.handle_request(ctx, question)

    @app_commands.command(name="ask", description="Ask a question or generate an image.")
    async def ask_slash(self, interaction: discord.Interaction, question: str):
        await self.handle_request(interaction, question)

    async def handle_request(self, interaction, question):
        user_id = interaction.user.id if isinstance(interaction, discord.Interaction) else interaction.author.id

        daily_count = get_daily_request_count(user_id)
        if daily_count >= USER_DAILY_QUE_LIMIT:
            message = f"You've reached your daily limit of {USER_DAILY_QUE_LIMIT} requests."
            if isinstance(interaction, discord.Interaction):
                await interaction.response.send_message(message)
            else:
                await interaction.send(message)
            return

        if isinstance(interaction, discord.Interaction):
            await interaction.response.defer()
        else:
            await interaction.defer()

        response = await self.generate_response(question)

        if response:
            embed = discord.Embed()
            if response.startswith("http"):
                embed.set_image(url=response)
            else:
                embed.description = response

            if isinstance(interaction, discord.Interaction):
                await interaction.followup.send(embed=embed)
            else:
                await interaction.send(embed=embed)

            increment_daily_request_count(user_id)
            insert_user_request(user_id, question, response)
        else:
            error_message = "Failed to generate a response."
            if isinstance(interaction, discord.Interaction):
                await interaction.followup.send(error_message)
            else:
                await interaction.send(error_message)

async def setup(bot):
    await bot.add_cog(AskCog(bot))
