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
            
            # Remove all roles from the member
            for role in roles:
                try:
                    await member.remove_roles(role)
                    logging.debug(f"Removed role {role.name} from {member.name}")
                except Exception as e:
                    logging.error(f"Failed to remove role {role.name} from {member.name}: {e}")
            
            # Scenario 1: Clean up verification state if member was in verification process
            if self.verification_cog and member.id in self.verification_cog.active_verifications:
                verification_data = self.verification_cog.active_verifications[member.id]
                
                # Delete verification channel if it exists
                channel = member.guild.get_channel(verification_data["channel_id"])
                if channel:
                    try:
                        await channel.delete()
                        logging.debug(f"Deleted verification channel for {member.name}")
                    except Exception as e:
                        logging.error(f"Failed to delete verification channel for {member.name}: {e}")
                
                # Remove from active verifications
                del self.verification_cog.active_verifications[member.id]
                logging.debug(f"Removed verification state for {member.name}")
            
            # Scenario 2: Notify admins about verified member leaving
            else:
                # Get admin channel from guild settings
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