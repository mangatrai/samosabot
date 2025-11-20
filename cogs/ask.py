"""
AskCog Module

This module defines the AskCog cog for the Discord bot, enabling users to ask questions or request image generation
via both prefix commands and slash commands. It integrates with OpenAI's API to first check the intent and safety
of a user prompt and then generate an appropriate response—either text or image. Additionally, the module enforces
a daily request limit per user and logs each query and its corresponding response to AstraDB for tracking and statistics.

This updated version also preprocesses the user’s prompt to replace any user mentions (e.g. <@123456789>) with the
corresponding display names. This works even if multiple users are mentioned in the prompt.
"""

import re
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

from utils.openai_utils import generate_openai_response

# Load environment variables
load_dotenv()
USER_DAILY_QUE_LIMIT = int(os.getenv("USER_DAILY_QUE_LIMIT", 30))

def replace_mentions_with_username(prompt, ctx_or_interaction):
    """
    Replace all Discord user mention patterns in the prompt with the corresponding display names.

    Args:
        prompt (str): The original prompt string containing user mentions in the format <@UserID> or <@!UserID>.
        ctx_or_interaction (commands.Context or discord.Interaction): The context from which to retrieve guild members.

    Returns:
        str: The prompt with all user mentions replaced by their display names. If a user is not found,
             the original mention is left unchanged.
    """
    pattern = r"<@!?(\d+)>"

    def replacer(match):
        user_id = int(match.group(1))
        # If guild context is available, get the member from the guild
        if hasattr(ctx_or_interaction, "guild") and ctx_or_interaction.guild:
            member = ctx_or_interaction.guild.get_member(user_id)
        else:
            member = ctx_or_interaction.bot.get_user(user_id)
        return member.display_name if member else match.group(0)

    return re.sub(pattern, replacer, prompt)

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
        """
        Ask the AI a question or request image generation (prefix command).
        
        Features:
            - Daily request limit per user (default: 30)
            - Intent detection and safety checking
            - Image generation support
            - User mention replacement with display names
        
        All requests are logged to AstraDB for tracking.
        """
        # Preprocess the question to replace any user mentions with display names.
        question = replace_mentions_with_username(question, ctx)
        await self.handle_request(ctx, question)

    @app_commands.command(name="ask", description="Ask a question or generate an image.")
    async def ask_slash(self, interaction: discord.Interaction, question: str):
        """
        Ask the AI a question or request image generation (slash command).
        
        Features:
            - Daily request limit per user (default: 30)
            - Intent detection and safety checking
            - Image generation support
            - User mention replacement with display names
        
        All requests are logged to AstraDB for tracking.
        """
        # Preprocess the question to replace any user mentions with display names.
        question = replace_mentions_with_username(question, interaction)
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
            try:
                await interaction.response.defer()
            except discord.errors.NotFound:
                logging.warning("Interaction not found or already responded to.")
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