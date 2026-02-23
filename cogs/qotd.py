"""
QOTDCog Module

Question of the Day: set channel, start schedule, one-off and slash QOTD.
Uses 50% REST API (qotd.dev) and 50% AI generation, with fallback to AI if API fails.
"""

import logging
import os
import random
import discord
import requests
from discord.ext import commands, tasks
from discord import app_commands
from dotenv import load_dotenv

from utils import astra_db_ops, openai_utils
from configs import prompts

load_dotenv()


def load_qotd_schedules():
    """Load scheduled QOTD channels from AstraDB."""
    return astra_db_ops.load_qotd_schedules()


class QOTDCog(commands.Cog):
    """QOTD commands and scheduled task."""

    def __init__(self, bot):
        self.bot = bot
        self.qotd_channels = load_qotd_schedules()
        self.qotd_api_url = os.getenv("QOTD_API_URL", "https://qotd.dev/api/q?random=true")
        self._qotd_max_chars = 250  # Reject overly long API questions (e.g. facilitator-style paragraphs)

    def _get_qotd_from_api(self):
        """Get a random question from the QOTD REST API. Returns question text or None."""
        try:
            if not self.qotd_api_url:
                return None
            response = requests.get(self.qotd_api_url, timeout=10)
            if response.status_code == 200:
                data = response.json()
                q = data.get("q")
                if q:
                    q_clean = q.strip()
                    if len(q_clean) <= self._qotd_max_chars:
                        logging.debug(f"QOTD API response: {q_clean}")
                        return q_clean
                    logging.debug(f"QOTD API: rejected (too long, {len(q_clean)} chars), fall back to AI")
            else:
                logging.warning(f"QOTD API returned status {response.status_code}")
        except requests.exceptions.Timeout:
            logging.error("Error getting QOTD from API: request timeout")
        except Exception as e:
            logging.error(f"Error getting QOTD from API: {e}")
        return None

    async def _get_qotd_from_ai(self):
        """Get a question from AI (QOTD-specific intent). Returns question text or None."""
        try:
            # Per-request random seed so the model sees a different prompt each time
            user_message = prompts.qotd_prompt + " Random seed: " + str(random.randint(1, 1000000)) + ". Output only the question."
            content = await openai_utils.generate_openai_response(user_message, intent="qotd")
            if content:
                logging.debug(f"QOTD AI response: {content}")
                return content
        except Exception as e:
            logging.error(f"Error getting QOTD from AI: {e}")
        return None

    async def _get_qotd_content(self):
        """Get QOTD: 50% API, 50% AI. If API is chosen and fails, fall back to AI."""
        rand = random.random()
        if rand < 0.5:
            q = self._get_qotd_from_api()
            if q:
                return q
            # API failed, fall back to AI
        return await self._get_qotd_from_ai()

    def _save_qotd_schedules(self):
        """Save in-memory qotd_channels to AstraDB."""
        for guild_id, channel_id in self.qotd_channels.items():
            astra_db_ops.save_qotd_schedules({"guild_id": guild_id, "channel_id": channel_id})

    @tasks.loop(hours=24)
    async def scheduled_qotd(self):
        for guild_id, channel_id in self.qotd_channels.items():
            channel = self.bot.get_channel(channel_id)
            if channel:
                content = await self._get_qotd_content()
                if content:
                    await channel.send(f"🌟 **Question of the Day:** {content}")
                else:
                    logging.warning("QOTD: API and AI both failed, skipping scheduled post")
            else:
                logging.warning(f"QOTD channel {channel_id} not found for server {guild_id}")

    @commands.command(name="setqotdchannel", description="Set channel for scheduled QOTD")
    async def set_qotd_channel(self, ctx, channel_id: int = None):
        if channel_id is None:
            channel_id = ctx.channel.id
        self.qotd_channels = load_qotd_schedules()
        self.qotd_channels[ctx.guild.id] = channel_id
        self._save_qotd_schedules()
        await ctx.send(f"✅ Scheduled QOTD channel set to <#{channel_id}> for this server.")

    @commands.command(name="startqotd", description="Start daily QOTD schedule")
    async def start_qotd(self, ctx):
        self.qotd_channels = load_qotd_schedules()
        if ctx.guild.id not in self.qotd_channels or not self.qotd_channels[ctx.guild.id]:
            await ctx.send("[ERROR] No scheduled QOTD channel set for this server. Use `!setqotdchannel <channel_id>`")
            return
        if not self.scheduled_qotd.is_running():
            self.scheduled_qotd.start()
            await ctx.send("✅ Scheduled QOTD started for this server!")
        else:
            await ctx.send("⚠️ QOTD is already running!")

    @commands.command(name="qotd", description="Get a Question of the Day")
    async def qotd(self, ctx):
        """Get a Question of the Day (50% API, 50% AI)."""
        async with ctx.typing():
            content = await self._get_qotd_content()
            if content:
                await ctx.send(f"🌟 **Question of the Day:** {content}")
            else:
                await ctx.send("❌ Could not fetch a question right now. Please try again later.")

    @app_commands.command(name="qotd", description="Get a Question of the Day")
    async def slash_qotd(self, interaction: discord.Interaction):
        try:
            await interaction.response.defer()
            content = await self._get_qotd_content()
            if content:
                await interaction.followup.send(f"🌟 **Question of the Day:** {content}")
            else:
                await interaction.followup.send("❌ Could not fetch a question right now. Please try again later.")
        except Exception as e:
            logging.error(f"Error in slash_qotd: {e}")
            await interaction.followup.send("❌ An error occurred while fetching the Question of the Day.")

    async def cog_load(self):
        """Refresh channels from DB when cog loads."""
        self.qotd_channels = load_qotd_schedules()


async def setup(bot):
    await bot.add_cog(QOTDCog(bot))
