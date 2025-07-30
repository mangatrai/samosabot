"""
Member Events Cog

This cog handles member-related events such as:
- Member leaves
"""

import discord
from discord.ext import commands
import logging
from utils import astra_db_ops
import asyncio
from datetime import datetime, timedelta

class MemberEventsCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.verification_cog = None
        logging.info("MemberEventsCog initialized")

    async def cog_load(self):
        """Initialize the cog."""
        logging.info("Loading MemberEventsCog...")
        # Get reference to VerificationCog
        self.verification_cog = self.bot.get_cog("VerificationCog")

    async def cog_unload(self):
        """Clean up when the cog is unloaded."""
        logging.info("Unloading MemberEventsCog...")

    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member):
        """Handle member leaves."""
        try:
            logging.info(f"Member left: {member.name} (ID: {member.id}) in guild: {member.guild.name} (ID: {member.guild.id})")
            
            # Get member's roles from Discord API
            roles = [role for role in member.roles if role.name != "@everyone"]
            
            # Handle verification cleanup if member was in verification process
            if self.verification_cog:
                verification_data = self.verification_cog.get_verification_data(member.id, member.guild.id)
                if verification_data:
                    # Delete verification channel if it exists
                    channel = member.guild.get_channel(verification_data["channel_id"])
                    if channel:
                        try:
                            await channel.delete()
                            logging.debug(f"Deleted verification channel for {member.name}")
                        except Exception as e:
                            logging.error(f"Failed to delete verification channel for {member.name}: {e}")
                    
                    # Clean up verification data
                    self.verification_cog.delete_verification_data(member.id, member.guild.id)
                    logging.debug(f"Cleaned up verification data for {member.name}")
            
            # Notify admins about member leaving (regardless of verification status)
            if self.verification_cog:
                settings = self.verification_cog.get_guild_settings(member.guild.id)
                if isinstance(settings, dict):
                    admin_channel_name = settings.get("admin_channel_name")
                    if admin_channel_name:
                        admin_channel = discord.utils.get(member.guild.channels, name=admin_channel_name)
                        if admin_channel:
                            embed = discord.Embed(
                                title="👋 Member Left",
                                description=(
                                    f"**User:** {member.mention}\n"
                                    f"**ID:** {member.id}\n"
                                    f"**Roles:** {', '.join(role.name for role in roles) if roles else 'None'}\n"
                                    f"**Time:** {discord.utils.format_dt(discord.utils.utcnow(), 'R')}"
                                ),
                                color=discord.Color.orange()
                            )
                            await admin_channel.send(embed=embed)
                
        except Exception as e:
            logging.error(f"Error in on_member_remove for {member.name}: {e}")

async def setup(bot):
    """Add the cog to the bot."""
    await bot.add_cog(MemberEventsCog(bot)) 