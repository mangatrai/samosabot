"""
QOTDCog Module

Question of the Day: set channel, start schedule, one-off and slash QOTD.
"""

import logging
import discord
from discord.ext import commands, tasks
from discord import app_commands

from utils import astra_db_ops, openai_utils
from configs import prompts

qotd_prompt = prompts.qotd_prompt


def load_qotd_schedules():
    """Load scheduled QOTD channels from AstraDB."""
    return astra_db_ops.load_qotd_schedules()


class QOTDCog(commands.Cog):
    """QOTD commands and scheduled task."""

    def __init__(self, bot):
        self.bot = bot
        self.qotd_channels = load_qotd_schedules()

    def _save_qotd_schedules(self):
        """Save in-memory qotd_channels to AstraDB."""
        for guild_id, channel_id in self.qotd_channels.items():
            astra_db_ops.save_qotd_schedules({"guild_id": guild_id, "channel_id": channel_id})

    @tasks.loop(hours=24)
    async def scheduled_qotd(self):
        for guild_id, channel_id in self.qotd_channels.items():
            channel = self.bot.get_channel(channel_id)
            if channel:
                content = await openai_utils.generate_openai_response(qotd_prompt)
                await channel.send(f"🌟 **Question of the Day:** {content}")
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
        """Get a random AI-generated Question of the Day."""
        async with ctx.typing():
            content = await openai_utils.generate_openai_response(qotd_prompt)
            await ctx.send(f"🌟 **Question of the Day:** {content}")

    @app_commands.command(name="qotd", description="Get a Question of the Day")
    async def slash_qotd(self, interaction: discord.Interaction):
        try:
            await interaction.response.defer()
            content = await openai_utils.generate_openai_response(qotd_prompt)
            await interaction.followup.send(f"🌟 **Question of the Day:** {content}")
        except Exception as e:
            logging.error(f"Error in slash_qotd: {e}")
            await interaction.followup.send("❌ An error occurred while fetching the Question of the Day.")

    async def cog_load(self):
        """Refresh channels from DB when cog loads."""
        self.qotd_channels = load_qotd_schedules()


async def setup(bot):
    await bot.add_cog(QOTDCog(bot))
