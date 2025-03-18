import discord
from discord.ext import commands
import logging
import os
from dotenv import load_dotenv
from discord import app_commands

from astra_db_ops import (
    increment_daily_request_count,
    get_daily_request_count,
    insert_user_request
)

from openai_utils import generate_openai_response

# Load environment variables
load_dotenv()

LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
USER_DAILY_QUE_LIMIT = int(os.getenv("USER_DAILY_QUE_LIMIT", 30))

try:
    log_level = getattr(logging, LOG_LEVEL.upper())
except AttributeError:
    print(f"WARNING: Invalid LOG_LEVEL '{LOG_LEVEL}'. Defaulting to INFO.")
    log_level = logging.INFO

logging.basicConfig(level=log_level, format='%(asctime)s - %(levelname)s - %(message)s')

class AskCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def generate_response(self, prompt):
        try:
            response = generate_openai_response(prompt)
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
            if isinstance(interaction, discord.Interaction):
                await interaction.response.send_message(f"You've reached your daily limit of {USER_DAILY_QUE_LIMIT} requests.")
            else:
                await interaction.send(f"You've reached your daily limit of {USER_DAILY_QUE_LIMIT} requests.") # change here.
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
                await interaction.send(embed=embed) # change here.

            increment_daily_request_count(user_id)
            insert_user_request(user_id, question, response)
        else:
            if isinstance(interaction, discord.Interaction):
                await interaction.followup.send("Failed to generate a response.")
            else:
                await interaction.send("Failed to generate a response.") # change here.

async def setup(bot):
    await bot.add_cog(AskCog(bot))