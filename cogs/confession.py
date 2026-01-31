"""
ConfessionCog Module

This module provides anonymous confession functionality for Discord servers.
Users can submit confessions that are analyzed for sentiment and either
auto-approved (if positive) or queued for admin review.

Features:
- Anonymous confession submission
- Sentiment analysis using VADER (always on)
- Auto-approval for positive confessions (configurable)
- Admin review with approve/reject buttons
- Thread creation for all approved confessions
- Full audit trail in database
"""

import discord
from discord.ext import commands
from discord import app_commands
import logging
from utils import astra_db_ops
from utils import error_handler
from utils.sentiment_analyzer import ConfessionSentimentAnalyzer

# Initialize sentiment analyzer (singleton)
sentiment_analyzer = ConfessionSentimentAnalyzer()


class ConfessionApprovalView(discord.ui.View):
    """View with approve/reject buttons for confession review."""
    
    def __init__(self, confession_id: int, guild_id: str, cog_instance):
        super().__init__(timeout=None)  # No timeout - buttons work indefinitely
        self.confession_id = confession_id
        self.guild_id = guild_id
        self.cog = cog_instance
    
    @discord.ui.button(label="✅ Approve", style=discord.ButtonStyle.success, custom_id="confession_approve")
    async def approve_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Handle confession approval."""
        try:
            # Check admin permissions
            if not interaction.user.guild_permissions.administrator:
                await interaction.response.send_message(
                    "❌ You need administrator permissions to approve confessions.",
                    ephemeral=True
                )
                return
            
            # Get confession data
            confession = astra_db_ops.get_confession_by_id(self.confession_id, self.guild_id)
            if not confession:
                await interaction.response.send_message(
                    "❌ Confession not found.",
                    ephemeral=True
                )
                return
            
            # Check if already processed (handle both "approved" and "auto-approved")
            current_status = confession.get("response", "pending")
            if current_status not in ["pending"]:
                status_display = current_status.replace("-", " ").title()
                await interaction.response.send_message(
                    f"❌ This confession has already been {status_display}.",
                    ephemeral=True
                )
                return
            
            # Get settings
            settings = astra_db_ops.get_confession_settings(int(self.guild_id))
            if not settings or not settings.get("confession_channel_id"):
                await interaction.response.send_message(
                    "❌ Confession channel not configured.",
                    ephemeral=True
                )
                return
            
            # Get confession channel
            confession_channel = interaction.guild.get_channel(int(settings["confession_channel_id"]))
            if not confession_channel:
                await interaction.response.send_message(
                    "❌ Confession channel not found.",
                    ephemeral=True
                )
                return
            
            # Update status
            astra_db_ops.update_confession_status(
                self.confession_id,
                self.guild_id,
                "approved",
                admin_id=interaction.user.id,
                admin_username=interaction.user.display_name
            )
            
            # Post to confession channel and create thread (ALWAYS create thread)
            confession_text = confession.get("question", "")
            await self.cog.post_confession_to_channel(
                self.confession_id,
                confession_text,
                confession_channel
            )
            
            # Update admin message
            admin_embed = interaction.message.embeds[0] if interaction.message.embeds else discord.Embed()
            admin_embed.color = discord.Color.green()
            admin_embed.set_footer(text=f"✅ Approved by {interaction.user.display_name} | Confession ID: #{self.confession_id}")
            
            # Remove buttons
            self.clear_items()
            await interaction.response.edit_message(embed=admin_embed, view=None)
            
            # Try to DM the confession submitter (NOT the admin)
            submitter_user_id = confession.get("user_id")
            admin_user_id = str(interaction.user.id)
            
            if not submitter_user_id:
                logging.error(f"Confession #{self.confession_id} has no user_id field - cannot send DM")
            else:
                try:
                    logging.info(f"Sending approval DM to confession submitter (user_id: {submitter_user_id}), admin is {admin_user_id}")
                    user = await interaction.client.fetch_user(int(submitter_user_id))
                    if user:
                        await user.send(f"✅ Your confession #{self.confession_id} has been approved and posted.")
                        logging.info(f"Successfully sent approval DM to user {submitter_user_id}")
                    else:
                        logging.warning(f"Could not fetch user {submitter_user_id} for DM")
                except discord.errors.Forbidden:
                    logging.warning(f"Could not send DM to user {submitter_user_id}: User has DMs disabled")
                except Exception as e:
                    logging.warning(f"Could not send DM to confession submitter {submitter_user_id}: {e}")
            
            logging.info(f"Confession #{self.confession_id} approved by admin {interaction.user.display_name} (ID: {admin_user_id})")
            
        except Exception as e:
            await error_handler.handle_error(e, interaction, "confession-approve")
    
    @discord.ui.button(label="❌ Reject", style=discord.ButtonStyle.danger, custom_id="confession_reject")
    async def reject_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Handle confession rejection."""
        try:
            # Check admin permissions
            if not interaction.user.guild_permissions.administrator:
                await interaction.response.send_message(
                    "❌ You need administrator permissions to reject confessions.",
                    ephemeral=True
                )
                return
            
            # Get confession data
            confession = astra_db_ops.get_confession_by_id(self.confession_id, self.guild_id)
            if not confession:
                await interaction.response.send_message(
                    "❌ Confession not found.",
                    ephemeral=True
                )
                return
            
            # Check if already processed (handle both "approved" and "auto-approved")
            current_status = confession.get("response", "pending")
            if current_status not in ["pending"]:
                status_display = current_status.replace("-", " ").title()
                await interaction.response.send_message(
                    f"❌ This confession has already been {status_display}.",
                    ephemeral=True
                )
                return
            
            # Update status
            astra_db_ops.update_confession_status(
                self.confession_id,
                self.guild_id,
                "rejected",
                admin_id=interaction.user.id,
                admin_username=interaction.user.display_name,
                rejection_reason="Rejected by administrator"
            )
            
            # Update admin message
            admin_embed = interaction.message.embeds[0] if interaction.message.embeds else discord.Embed()
            admin_embed.color = discord.Color.red()
            admin_embed.set_footer(text=f"❌ Rejected by {interaction.user.display_name} | Confession ID: #{self.confession_id}")
            
            # Remove buttons
            self.clear_items()
            await interaction.response.edit_message(embed=admin_embed, view=None)
            
            # Try to DM the confession submitter (NOT the admin)
            submitter_user_id = confession.get("user_id")
            admin_user_id = str(interaction.user.id)
            
            if not submitter_user_id:
                logging.error(f"Confession #{self.confession_id} has no user_id field - cannot send DM")
            else:
                try:
                    logging.info(f"Sending rejection DM to confession submitter (user_id: {submitter_user_id}), admin is {admin_user_id}")
                    user = await interaction.client.fetch_user(int(submitter_user_id))
                    if user:
                        await user.send(
                            f"❌ Your confession #{self.confession_id} has been rejected.\n\n"
                            "If you have questions, please contact a server administrator."
                        )
                        logging.info(f"Successfully sent rejection DM to user {submitter_user_id}")
                    else:
                        logging.warning(f"Could not fetch user {submitter_user_id} for DM")
                except discord.errors.Forbidden:
                    logging.warning(f"Could not send DM to user {submitter_user_id}: User has DMs disabled")
                except Exception as e:
                    logging.warning(f"Could not send DM to confession submitter {submitter_user_id}: {e}")
            
            logging.info(f"Confession #{self.confession_id} rejected by admin {interaction.user.display_name} (ID: {admin_user_id})")
            
        except Exception as e:
            await error_handler.handle_error(e, interaction, "confession-reject")


class ConfessionCog(commands.Cog):
    """Cog for anonymous confession functionality."""
    
    def __init__(self, bot):
        self.bot = bot
    
    async def post_confession_to_channel(self, confession_id: int, confession_text: str, 
                                        channel: discord.TextChannel) -> discord.Message:
        """
        Post confession to channel and create thread.
        ALWAYS creates thread for every confession post.
        """
        embed = discord.Embed(
            description=f"**Confession #{confession_id}**\n\n{confession_text}\n\n─────────────────────\n💬 Please use thread to reply",
            color=discord.Color.blue()
        )
        
        message = await channel.send(embed=embed)
        
        # ALWAYS create thread for every confession
        await message.create_thread(
            name=f"Confession #{confession_id} Discussion",
            auto_archive_duration=4320  # 3 days
        )
        
        return message
    
    async def handle_confession_submission(self, interaction: discord.Interaction, confession_text: str):
        """
        Handle confession submission logic (slash command only).
        
        Args:
            interaction: discord.Interaction from slash command
            confession_text: Confession content
        """
        guild_id = interaction.guild_id
        user_id = interaction.user.id
        username = interaction.user.display_name
        guild = interaction.guild
        channel_id = str(interaction.channel_id) if interaction.channel_id else None
        
        # DEFER FIRST (before ANY validation that might respond)
        # This ensures we can always send followup messages reliably
        try:
            if not interaction.response.is_done():
                await interaction.response.defer(ephemeral=True)
                logging.debug(f"Deferred interaction for confession submission by user {user_id}")
        except discord.errors.NotFound:
            logging.warning("Interaction not found, cannot defer.")
            return
        except Exception as e:
            logging.error(f"Error deferring interaction: {e}")
            # Try to respond directly if defer fails
            try:
                await interaction.response.send_message("❌ An error occurred. Please try again.", ephemeral=True)
            except:
                pass
            return
        
        if not guild:
            await interaction.followup.send("❌ Confessions can only be submitted in servers.", ephemeral=True)
            return
        
        guild_name = guild.name
        
        # Get settings
        settings = astra_db_ops.get_confession_settings(guild_id)
        if not settings or not settings.get("confession_enabled"):
            await interaction.followup.send(
                "❌ Confessions are not enabled in this server. Contact an administrator.",
                ephemeral=True
            )
            return
        
        # Validate length
        if len(confession_text) > 2000:
            await interaction.followup.send(
                "❌ Confession is too long! Please keep it under 2000 characters.",
                ephemeral=True
            )
            return
        
        if len(confession_text.strip()) < 10:
            await interaction.followup.send(
                "❌ Confession is too short! Please provide at least 10 characters.",
                ephemeral=True
            )
            return
        
        # Get next confession ID
        confession_id = astra_db_ops.get_next_confession_id(guild_id)
        
        # Run sentiment analysis (ALWAYS)
        sentiment_data = sentiment_analyzer.analyze(confession_text)
        
        # Save confession
        doc_id = astra_db_ops.save_confession(
            user_id=str(user_id),
            username=username,
            guild_id=str(guild_id),
            guild_name=guild_name,
            confession_text=confession_text,
            confession_id=confession_id,
            sentiment_data=sentiment_data,
            channel_id=channel_id
        )
        
        if not doc_id:
            await interaction.followup.send(
                "❌ Failed to save confession. Please try again later.",
                ephemeral=True
            )
            return
        
        # Decision logic
        approval_required = settings.get("confession_approval_required", False)  # Default: False
        auto_approve_enabled = settings.get("confession_auto_approve_enabled", False)
        
        if not approval_required:
            # No approval needed - post directly
            confession_channel_id = settings.get("confession_channel_id")
            if not confession_channel_id:
                await interaction.followup.send(
                    "❌ Confession channel not configured. Contact an administrator.",
                    ephemeral=True
                )
                return
            
            confession_channel = guild.get_channel(int(confession_channel_id))
            if not confession_channel:
                await interaction.followup.send(
                    "❌ Confession channel not found. Contact an administrator.",
                    ephemeral=True
                )
                return
            
            # Post to channel and create thread
            await self.post_confession_to_channel(confession_id, confession_text, confession_channel)
            
            # Update status
            astra_db_ops.update_confession_status(confession_id, str(guild_id), "approved")
            
            # Send confirmation
            await interaction.followup.send(
                f"✅ Your confession #{confession_id} has been posted!",
                ephemeral=True
            )
        
        elif approval_required:
            # Approval required
            if auto_approve_enabled and sentiment_data.get("auto_approve"):
                # Auto-approve positive sentiment
                confession_channel_id = settings.get("confession_channel_id")
                if not confession_channel_id:
                    await interaction.followup.send(
                        "❌ Confession channel not configured. Contact an administrator.",
                        ephemeral=True
                    )
                    return
                
                confession_channel = guild.get_channel(int(confession_channel_id))
                if not confession_channel:
                    await interaction.followup.send(
                        "❌ Confession channel not found. Contact an administrator.",
                        ephemeral=True
                    )
                    return
                
                # Update status FIRST (before posting) to ensure DB is updated
                astra_db_ops.update_confession_status(
                    confession_id,
                    str(guild_id),
                    "auto-approved",  # Use "auto-approved" to distinguish from manual approval
                    admin_id=None,  # Auto-approved
                    admin_username="Auto-Approved (Positive Sentiment)"
                )
                
                # Post to channel and create thread
                await self.post_confession_to_channel(confession_id, confession_text, confession_channel)
                
                # Send confirmation
                await interaction.followup.send(
                    f"✅ Your confession #{confession_id} has been auto-approved and posted!",
                    ephemeral=True
                )
            
            else:
                # Queue for admin review
                admin_channel_id = settings.get("confession_admin_channel_id")
                if not admin_channel_id:
                    await interaction.followup.send(
                        "❌ Admin review channel not configured. Contact an administrator.",
                        ephemeral=True
                    )
                    return
                
                admin_channel = guild.get_channel(int(admin_channel_id))
                if not admin_channel:
                    await interaction.followup.send(
                        "❌ Admin review channel not found. Contact an administrator.",
                        ephemeral=True
                    )
                    return
                
                # Create admin review embed
                sentiment_category = sentiment_data.get("category", "neutral")
                sentiment_score = sentiment_data.get("score", 0.0)
                
                # Determine color and title based on sentiment
                if sentiment_category == "concerning":
                    color = discord.Color.red()
                    title = f"🚨 URGENT: Confession #{confession_id} - CONCERNING"
                elif sentiment_category == "negative":
                    color = discord.Color.orange()
                    title = f"🔒 Confession #{confession_id} - NEGATIVE - Pending Review"
                else:
                    color = discord.Color.yellow()
                    title = f"🔒 Confession #{confession_id} - {sentiment_category.upper()} - Pending Review"
                
                embed = discord.Embed(
                    title=title,
                    color=color,
                    description=confession_text
                )
                embed.add_field(name="Sentiment", value=f"{sentiment_category.title()} (Score: {sentiment_score:.2f})", inline=True)
                embed.add_field(name="Category", value=sentiment_category.title(), inline=True)
                embed.add_field(name="Submitted by", value=f"{username} ({user_id})", inline=False)
                embed.add_field(name="Guild", value=guild_name, inline=True)
                embed.add_field(name="Submitted", value=f"<t:{int(discord.utils.utcnow().timestamp())}:R>", inline=True)
                
                if sentiment_category == "concerning":
                    embed.set_footer(text=f"⚠️ High priority review required | Confession ID: #{confession_id}")
                else:
                    embed.set_footer(text=f"Confession ID: #{confession_id}")
                
                # Send confirmation to user FIRST (before posting to admin channel)
                # This ensures user always gets feedback even if admin channel posting fails
                logging.info(f"Sending pending review confirmation for confession #{confession_id} to user {user_id}")
                confirmation_sent = False
                try:
                    # Ensure interaction is deferred before using followup
                    if interaction.response.is_done():
                        logging.warning(f"Interaction already responded for confession #{confession_id}, trying followup anyway")
                    await interaction.followup.send(
                        f"✅ Your confession #{confession_id} has been submitted and is pending review.",
                        ephemeral=True
                    )
                    confirmation_sent = True
                    logging.info(f"Successfully sent pending review confirmation (slash) for confession #{confession_id}")
                except Exception as e:
                    logging.error(f"Failed to send confirmation to user (slash) for confession #{confession_id}: {e}", exc_info=True)
                
                if not confirmation_sent:
                    logging.error(f"CRITICAL: Confirmation message NOT sent for confession #{confession_id} - user will not be notified!")
                    # Try one more time as a last resort via DM
                    try:
                        user_obj = guild.get_member(user_id) or await guild.fetch_member(user_id)
                        if user_obj:
                            await user_obj.send(f"✅ Your confession #{confession_id} has been submitted and is pending review.")
                            logging.info(f"Sent pending review confirmation via DM fallback for confession #{confession_id}")
                    except Exception as e2:
                        logging.error(f"Failed to send DM fallback for confession #{confession_id}: {e2}")
                
                # Create view with buttons and post to admin channel
                view = ConfessionApprovalView(confession_id, str(guild_id), self)
                
                try:
                    await admin_channel.send(embed=embed, view=view)
                    logging.info(f"Successfully posted confession #{confession_id} to admin channel")
                except Exception as e:
                    logging.error(f"Failed to post confession to admin channel: {e}")
                    # Try to notify user about the error (only if confirmation wasn't already sent)
                    if not confirmation_sent:
                        try:
                            await interaction.followup.send(
                                f"⚠️ Your confession #{confession_id} was received but there was an error posting it for review. Please contact an administrator.",
                                ephemeral=True
                            )
                        except:
                            pass
    
    @app_commands.command(name="confession", description="Submit an anonymous confession")
    @app_commands.describe(confession="Your confession (10-2000 characters)")
    async def confession_slash(self, interaction: discord.Interaction, confession: str):
        """
        Submit an anonymous confession (slash command).
        
        Confessions are analyzed for sentiment and either auto-approved
        (if positive) or queued for admin review.
        """
        try:
            await self.handle_confession_submission(interaction, confession)
        except Exception as e:
            await error_handler.handle_error(e, interaction, "confession")
    
    @app_commands.command(name="confession-setup", description="Configure confession settings (admin only)")
    @app_commands.describe(
        action="Action to perform",
        confession_channel="Channel where confessions will be posted",
        admin_channel="Channel where confessions are reviewed (required if approval enabled)",
        approval_required="Whether confessions need admin approval (default: false)",
        auto_approve="Auto-approve positive confessions (default: false, only works if approval enabled)"
    )
    @app_commands.choices(action=[
        app_commands.Choice(name="Enable", value="enable"),
        app_commands.Choice(name="Disable", value="disable"),
        app_commands.Choice(name="View Settings", value="view")
    ])
    @app_commands.checks.has_permissions(administrator=True)
    async def confession_setup(self, interaction: discord.Interaction, 
                               action: str,
                               confession_channel: discord.TextChannel = None,
                               admin_channel: discord.TextChannel = None,
                               approval_required: bool = None,
                               auto_approve: bool = None):
        """Configure confession settings for the server."""
        try:
            
            guild_id = interaction.guild_id
            settings = astra_db_ops.get_confession_settings(guild_id) or {}
            
            if action == "enable":
                # Build update dict with provided values
                update_data = {"confession_enabled": True}
                
                if confession_channel:
                    update_data["confession_channel_id"] = str(confession_channel.id)
                
                if admin_channel:
                    update_data["confession_admin_channel_id"] = str(admin_channel.id)
                
                # Set approval_required (default: False if not provided)
                if approval_required is not None:
                    update_data["confession_approval_required"] = approval_required
                elif "confession_approval_required" not in settings:
                    # First time setup - default to False
                    update_data["confession_approval_required"] = False
                
                # Set auto_approve (default: False if not provided)
                if auto_approve is not None:
                    update_data["confession_auto_approve_enabled"] = auto_approve
                elif "confession_auto_approve_enabled" not in settings:
                    # First time setup - default to False
                    update_data["confession_auto_approve_enabled"] = False
                
                # Validate: if approval_required is True, we need admin_channel
                if update_data.get("confession_approval_required", settings.get("confession_approval_required", False)):
                    if not admin_channel and not settings.get("confession_admin_channel_id"):
                        await interaction.response.send_message(
                            "❌ Admin channel is required when approval is enabled. Please provide `admin_channel` parameter.",
                            ephemeral=True
                        )
                        return
                
                # Validate: if auto_approve is True, approval must be enabled
                if update_data.get("confession_auto_approve_enabled", False):
                    if not update_data.get("confession_approval_required", settings.get("confession_approval_required", False)):
                        await interaction.response.send_message(
                            "❌ Auto-approve only works when approval is required. Set `approval_required: true` first.",
                            ephemeral=True
                        )
                        return
                
                # Update settings
                astra_db_ops.update_confession_settings(guild_id, update_data)
                
                # Build confirmation message
                msg_parts = ["✅ Confessions enabled!"]
                if confession_channel:
                    msg_parts.append(f"Confession channel: {confession_channel.mention}")
                if admin_channel:
                    msg_parts.append(f"Admin channel: {admin_channel.mention}")
                if approval_required is not None:
                    msg_parts.append(f"Approval required: {'Yes' if approval_required else 'No'}")
                if auto_approve is not None:
                    msg_parts.append(f"Auto-approve: {'Yes' if auto_approve else 'No'}")
                
                await interaction.response.send_message("\n".join(msg_parts), ephemeral=True)
            
            elif action == "disable":
                astra_db_ops.update_confession_settings(guild_id, {"confession_enabled": False})
                await interaction.response.send_message("✅ Confessions disabled!", ephemeral=True)
            
            elif action == "view":
                embed = discord.Embed(
                    title="Confession Settings",
                    color=discord.Color.blue()
                )
                embed.add_field(
                    name="Enabled",
                    value="✅ Yes" if settings.get("confession_enabled") else "❌ No",
                    inline=True
                )
                
                confession_channel_id = settings.get("confession_channel_id")
                if confession_channel_id:
                    channel_mention = f"<#{confession_channel_id}>"
                else:
                    channel_mention = "Not set"
                embed.add_field(name="Confession Channel", value=channel_mention, inline=True)
                
                admin_channel_id = settings.get("confession_admin_channel_id")
                if admin_channel_id:
                    admin_mention = f"<#{admin_channel_id}>"
                else:
                    admin_mention = "Not set"
                embed.add_field(name="Admin Channel", value=admin_mention, inline=True)
                
                embed.add_field(
                    name="Approval Required",
                    value="✅ Yes" if settings.get("confession_approval_required", False) else "❌ No",
                    inline=True
                )
                
                auto_approve = settings.get("confession_auto_approve_enabled", False)
                if settings.get("confession_approval_required", False):
                    embed.add_field(
                        name="Auto-Approve Positive",
                        value="✅ Yes" if auto_approve else "❌ No",
                        inline=True
                    )
                else:
                    embed.add_field(
                        name="Auto-Approve Positive",
                        value="N/A (approval disabled)",
                        inline=True
                    )
                
                embed.add_field(
                    name="Total Confessions",
                    value=str(settings.get("confession_counter", 0)),
                    inline=True
                )
                
                await interaction.response.send_message(embed=embed, ephemeral=True)
            
        except app_commands.MissingPermissions:
            # This should not happen due to the decorator, but handle it gracefully
            await interaction.response.send_message(
                "❌ You need administrator permissions to configure confessions.",
                ephemeral=True
            )
        except Exception as e:
            await error_handler.handle_error(e, interaction, "confession-setup")


async def setup(bot):
    """Setup function for cog loading"""
    await bot.add_cog(ConfessionCog(bot))
