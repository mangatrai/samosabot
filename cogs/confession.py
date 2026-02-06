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

import math
import re
import discord
from discord.ext import commands
from discord import app_commands
import logging
from utils import astra_db_ops
from utils import error_handler
from utils.sentiment_analyzer import ConfessionSentimentAnalyzer
from utils.interaction_helpers import get_interaction_message

# Column widths for confession history table (code block)
_HIST_ID_W = 4
_HIST_STATUS_W = 12
_HIST_BY_W = 14
_HIST_SENT_W = 10
_HIST_PREVIEW_W = 28
_HIST_DATE_W = 10

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
        await interaction.response.defer()
        await self.cog._do_approve(self.confession_id, self.guild_id, interaction)
    
    @discord.ui.button(label="❌ Reject", style=discord.ButtonStyle.danger, custom_id="confession_reject")
    async def reject_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Handle confession rejection."""
        await interaction.response.defer()
        await self.cog._do_reject(self.confession_id, self.guild_id, interaction)


def _parse_confession_id_from_message(message: discord.Message) -> int | None:
    """Parse confession ID from embed footer (e.g. 'Confession ID: #123' or '... | Confession ID: #123')."""
    if not message.embeds:
        return None
    footer = (message.embeds[0].footer.text or "").strip()
    match = re.search(r"Confession ID: #(\d+)", footer)
    return int(match.group(1)) if match else None


class PersistentConfessionApprovalView(discord.ui.View):
    """Persistent view so approve/reject buttons work after bot restart. Parses confession_id from message footer."""

    def __init__(self, cog_instance):
        super().__init__(timeout=None)
        self.cog = cog_instance

    @discord.ui.button(label="✅ Approve", style=discord.ButtonStyle.success, custom_id="confession_approve")
    async def approve_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._handle(interaction, "approve")

    @discord.ui.button(label="❌ Reject", style=discord.ButtonStyle.danger, custom_id="confession_reject")
    async def reject_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._handle(interaction, "reject")

    async def _handle(self, interaction: discord.Interaction, action: str):
        try:
            await interaction.response.defer()
            msg = await get_interaction_message(interaction)
            if not msg:
                await interaction.followup.send("❌ Could not load message.", ephemeral=True)
                return
            confession_id = _parse_confession_id_from_message(msg)
            if confession_id is None:
                await interaction.followup.send("❌ Could not determine confession ID from this message.", ephemeral=True)
                return
            guild_id = str(interaction.guild_id) if interaction.guild_id else None
            if not guild_id:
                await interaction.followup.send("❌ Could not determine server.", ephemeral=True)
                return
            if action == "approve":
                await self.cog._do_approve(confession_id, guild_id, interaction)
            else:
                await self.cog._do_reject(confession_id, guild_id, interaction)
        except Exception as e:
            await error_handler.handle_error(e, interaction, "confession-persistent")


class ConfessionHistoryView(discord.ui.View):
    """Pagination view for confession history: First, Previous, Next, Last.
    Uses @discord.ui.button decorators so callbacks get (interaction, button) and _refresh always receives page.
    """

    def __init__(self, guild_id: str, current_page: int, total_pages: int, total_count: int,
                 page_size: int, user_id: int, cog_instance):
        super().__init__(timeout=120)
        self.guild_id = guild_id
        self.current_page = current_page
        self.total_pages = total_pages
        self.total_count = total_count
        self.page_size = page_size
        self.user_id = user_id
        self.cog = cog_instance

    def _do_page(self, interaction: discord.Interaction, page: int):
        """Build embed and new view for given page; used by all button callbacks."""
        if not interaction.user.guild_permissions.administrator:
            return None, "❌ Administrator only."
        if interaction.user.id != self.user_id:
            return None, "❌ Only the user who ran the command can use these buttons."
        embed = self.cog.build_confession_history_embed(
            self.guild_id, page, self.page_size, self.total_count
        )
        new_view = ConfessionHistoryView(
            self.guild_id, page, self.total_pages, self.total_count,
            self.page_size, self.user_id, self.cog
        )
        return new_view, embed

    @discord.ui.button(label="First", style=discord.ButtonStyle.primary, row=0, custom_id="confession_history_first")
    async def first_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.current_page <= 1:
            await interaction.response.defer()
            return
        view, embed = self._do_page(interaction, 1)
        if view is None:
            await interaction.response.send_message(embed, ephemeral=True)
            return
        await interaction.response.edit_message(embed=embed, view=view)

    @discord.ui.button(label="Previous", style=discord.ButtonStyle.primary, row=0, custom_id="confession_history_prev")
    async def prev_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.current_page <= 1:
            await interaction.response.defer()
            return
        view, embed = self._do_page(interaction, self.current_page - 1)
        if view is None:
            await interaction.response.send_message(embed, ephemeral=True)
            return
        await interaction.response.edit_message(embed=embed, view=view)

    @discord.ui.button(label="Next", style=discord.ButtonStyle.success, row=0, custom_id="confession_history_next")
    async def next_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.current_page >= self.total_pages:
            await interaction.response.defer()
            return
        view, embed = self._do_page(interaction, self.current_page + 1)
        if view is None:
            await interaction.response.send_message(embed, ephemeral=True)
            return
        await interaction.response.edit_message(embed=embed, view=view)

    @discord.ui.button(label="Last", style=discord.ButtonStyle.primary, row=0, custom_id="confession_history_last")
    async def last_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.current_page >= self.total_pages:
            await interaction.response.defer()
            return
        view, embed = self._do_page(interaction, self.total_pages)
        if view is None:
            await interaction.response.send_message(embed, ephemeral=True)
            return
        await interaction.response.edit_message(embed=embed, view=view)


class ConfessionCog(commands.Cog):
    """Cog for anonymous confession functionality."""
    
    def __init__(self, bot):
        self.bot = bot

    async def cog_load(self):
        """Register persistent view so approve/reject buttons work after bot restart."""
        self.bot.add_view(PersistentConfessionApprovalView(self))

    def build_confession_history_embed(
        self, guild_id: str, page: int, page_size: int, total_count: int
    ) -> discord.Embed:
        """Build paginated confession history embed with table (ID, Status, Submitted by, Sentiment, Preview, Submitted)."""
        skip = (page - 1) * page_size
        confessions = astra_db_ops.get_all_confessions(guild_id, limit=page_size, skip=skip)
        total_pages = max(1, math.ceil(total_count / page_size)) if total_count else 1

        # Header row (labels as first row)
        id_h = self._pad("ID", _HIST_ID_W)
        status_h = self._pad("Status", _HIST_STATUS_W)
        by_h = self._pad("Submitted by", _HIST_BY_W)
        sent_h = self._pad("Sentiment", _HIST_SENT_W)
        preview_h = self._pad("Preview", _HIST_PREVIEW_W)
        date_h = self._pad("Submitted", _HIST_DATE_W)
        header = f"```\n{id_h} {status_h} {by_h} {sent_h} {preview_h} {date_h}\n"
        sep = f"{'-' * _HIST_ID_W} {'-' * _HIST_STATUS_W} {'-' * _HIST_BY_W} {'-' * _HIST_SENT_W} {'-' * _HIST_PREVIEW_W} {'-' * _HIST_DATE_W}\n"
        body_lines = [header, sep]

        for c in confessions:
            cid = str(c.get("confession_id", "?"))
            status = (c.get("response") or "pending").replace("-", " ")
            by = (c.get("username") or "?")[: _HIST_BY_W]
            sent = (c.get("sentiment_category") or "—")[: _HIST_SENT_W]
            text = (c.get("question") or "").replace("\n", " ").strip()
            preview = (text[: _HIST_PREVIEW_W - 1] + "…") if len(text) > _HIST_PREVIEW_W else text
            ts = (c.get("timestamp") or "?")[:10]
            body_lines.append(
                f"{self._pad(cid, _HIST_ID_W)} {self._pad(status, _HIST_STATUS_W)} "
                f"{self._pad(by, _HIST_BY_W)} {self._pad(sent, _HIST_SENT_W)} "
                f"{self._pad(preview, _HIST_PREVIEW_W)} {self._pad(ts, _HIST_DATE_W)}\n"
            )
        body_lines.append("```")
        description = "".join(body_lines)

        embed = discord.Embed(
            title=f"Confession History — Page {page} of {total_pages}",
            color=discord.Color.blue(),
            description=description
        )
        embed.set_footer(text=f"Total: {total_count} confessions • {page_size} per page")
        return embed

    def _pad(self, s: str, w: int) -> str:
        s = (s or "")[:w]
        return s.ljust(w)
    
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
    
    async def _reply_ephemeral(self, interaction: discord.Interaction, text: str):
        """Send ephemeral reply; use followup if response already sent (e.g. after defer)."""
        if interaction.response.is_done():
            await interaction.followup.send(text, ephemeral=True)
        else:
            await interaction.response.send_message(text, ephemeral=True)
    
    async def _do_approve(self, confession_id: int, guild_id: str, interaction: discord.Interaction):
        """Run approval logic. Works for both in-memory and persistent views (handles deferred interaction)."""
        try:
            if not interaction.user.guild_permissions.administrator:
                await self._reply_ephemeral(interaction, "❌ You need administrator permissions to approve confessions.")
                return
            confession = astra_db_ops.get_confession_by_id(confession_id, guild_id)
            if not confession:
                await self._reply_ephemeral(interaction, "❌ Confession not found.")
                return
            current_status = confession.get("response", "pending")
            if current_status not in ["pending"]:
                status_display = current_status.replace("-", " ").title()
                await self._reply_ephemeral(interaction, f"❌ This confession has already been {status_display}.")
                return
            settings = astra_db_ops.get_confession_settings(int(guild_id))
            if not settings or not settings.get("confession_channel_id"):
                await self._reply_ephemeral(interaction, "❌ Confession channel not configured.")
                return
            confession_channel = interaction.guild.get_channel(int(settings["confession_channel_id"]))
            if not confession_channel:
                await self._reply_ephemeral(interaction, "❌ Confession channel not found.")
                return
            astra_db_ops.update_confession_status(
                confession_id, guild_id, "approved",
                admin_id=interaction.user.id,
                admin_username=interaction.user.display_name
            )
            confession_text = confession.get("question", "")
            await self.post_confession_to_channel(confession_id, confession_text, confession_channel)
            msg = await get_interaction_message(interaction)
            # Replace embed with minimal outcome only (no confession text/submitter/scores left visible)
            admin_embed = discord.Embed(
                description=f"✅ Confession **#{confession_id}** was approved by {interaction.user.display_name}.",
                color=discord.Color.green(),
            )
            admin_embed.set_footer(text=f"Confession ID: #{confession_id}")
            if interaction.response.is_done() and msg:
                await msg.edit(embed=admin_embed, view=None)
            else:
                await interaction.response.edit_message(embed=admin_embed, view=None)
            submitter_user_id = confession.get("user_id")
            if submitter_user_id:
                try:
                    user = await interaction.client.fetch_user(int(submitter_user_id))
                    if user:
                        await user.send(f"✅ Your confession #{confession_id} has been approved and posted.")
                except (discord.errors.Forbidden, Exception):
                    pass
            logging.info(f"Confession #{confession_id} approved by admin {interaction.user.display_name}")
        except Exception as e:
            await error_handler.handle_error(e, interaction, "confession-approve")
    
    async def _do_reject(self, confession_id: int, guild_id: str, interaction: discord.Interaction):
        """Run rejection logic. Works for both in-memory and persistent views (handles deferred interaction)."""
        try:
            if not interaction.user.guild_permissions.administrator:
                await self._reply_ephemeral(interaction, "❌ You need administrator permissions to reject confessions.")
                return
            confession = astra_db_ops.get_confession_by_id(confession_id, guild_id)
            if not confession:
                await self._reply_ephemeral(interaction, "❌ Confession not found.")
                return
            current_status = confession.get("response", "pending")
            if current_status not in ["pending"]:
                status_display = current_status.replace("-", " ").title()
                await self._reply_ephemeral(interaction, f"❌ This confession has already been {status_display}.")
                return
            astra_db_ops.update_confession_status(
                confession_id, guild_id, "rejected",
                admin_id=interaction.user.id,
                admin_username=interaction.user.display_name,
                rejection_reason="Rejected by administrator"
            )
            msg = await get_interaction_message(interaction)
            # Replace embed with minimal outcome only (no confession text/submitter/scores left visible)
            admin_embed = discord.Embed(
                description=f"❌ Confession **#{confession_id}** was rejected by {interaction.user.display_name}.",
                color=discord.Color.red(),
            )
            admin_embed.set_footer(text=f"Confession ID: #{confession_id}")
            if interaction.response.is_done() and msg:
                await msg.edit(embed=admin_embed, view=None)
            else:
                await interaction.response.edit_message(embed=admin_embed, view=None)
            submitter_user_id = confession.get("user_id")
            if submitter_user_id:
                try:
                    user = await interaction.client.fetch_user(int(submitter_user_id))
                    if user:
                        await user.send(
                            f"❌ Your confession #{confession_id} has been rejected.\n\n"
                            "If you have questions, please contact a server administrator."
                        )
                except (discord.errors.Forbidden, Exception):
                    pass
            logging.info(f"Confession #{confession_id} rejected by admin {interaction.user.display_name}")
        except Exception as e:
            await error_handler.handle_error(e, interaction, "confession-reject")
    
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
                
                # Minimal notification in admin channel so admins know what happened
                admin_channel_id = settings.get("confession_admin_channel_id")
                if admin_channel_id:
                    admin_channel = guild.get_channel(int(admin_channel_id))
                    if admin_channel:
                        score = sentiment_data.get("score", 0.0)
                        try:
                            auto_embed = discord.Embed(
                                description=f"✅ Confession **#{confession_id}** with positive sentiment ({score:.1f}) was Auto Approved.",
                                color=discord.Color.green(),
                            )
                            auto_embed.set_footer(text=f"Confession ID: #{confession_id}")
                            await admin_channel.send(embed=auto_embed)
                        except Exception as e:
                            logging.warning(f"Failed to send auto-approve notification to admin channel: {e}")
            
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

    @app_commands.command(name="confession-view", description="View a confession by ID (admin only)")
    @app_commands.describe(confession_id="Confession ID (e.g. 1, 2, 3)")
    @app_commands.checks.has_permissions(administrator=True)
    async def confession_view(self, interaction: discord.Interaction, confession_id: int):
        """Show full details of a confession. Admin only."""
        try:
            if not interaction.guild_id:
                await interaction.response.send_message("❌ Use this command in a server.", ephemeral=True)
                return
            guild_id = str(interaction.guild_id)
            confession = astra_db_ops.get_confession_by_id(confession_id, guild_id)
            if not confession:
                await interaction.response.send_message(
                    f"❌ No confession found with ID **#{confession_id}** in this server.",
                    ephemeral=True
                )
                return
            status = confession.get("response", "pending")
            status_display = status.replace("-", " ").title()
            embed = discord.Embed(
                title=f"Confession #{confession_id}",
                color=discord.Color.blue(),
                description=(confession.get("question") or "")[:4000]
            )
            embed.add_field(name="Status", value=status_display, inline=True)
            embed.add_field(name="Submitted by", value=f"{confession.get('username', '?')} (`{confession.get('user_id', '?')}`)", inline=True)
            embed.add_field(name="Guild", value=confession.get("guild_name", "?"), inline=True)
            embed.add_field(name="Submitted", value=confession.get("timestamp", "?"), inline=True)
            sentiment = confession.get("sentiment_category", "—")
            score = confession.get("sentiment_score")
            if score is not None:
                embed.add_field(name="Sentiment", value=f"{sentiment} (score: {score:.2f})", inline=True)
            else:
                embed.add_field(name="Sentiment", value=sentiment, inline=True)
            if status not in ["pending"]:
                admin_name = confession.get("admin_username") or confession.get("admin_id") or "—"
                embed.add_field(name="Reviewed by", value=admin_name, inline=True)
            await interaction.response.send_message(embed=embed, ephemeral=True)
        except app_commands.MissingPermissions:
            await interaction.response.send_message(
                "❌ You need administrator permissions to view confessions.",
                ephemeral=True
            )
        except Exception as e:
            await error_handler.handle_error(e, interaction, "confession-view")

    @app_commands.command(name="confession-history", description="List confession history for this server (admin only)")
    @app_commands.checks.has_permissions(administrator=True)
    async def confession_history(self, interaction: discord.Interaction):
        """List confessions for the guild with First/Previous/Next/Last buttons. Admin only."""
        try:
            if not interaction.guild_id:
                await interaction.response.send_message("❌ Use this command in a server.", ephemeral=True)
                return
            guild_id = str(interaction.guild_id)
            page_size = 10
            settings = astra_db_ops.get_confession_settings(interaction.guild_id) or {}
            total_count = settings.get("confession_counter", 0)
            if total_count == 0:
                await interaction.response.send_message("No confessions found.", ephemeral=True)
                return
            total_pages = max(1, math.ceil(total_count / page_size))
            embed = self.build_confession_history_embed(guild_id, 1, page_size, total_count)
            view = ConfessionHistoryView(
                guild_id, 1, total_pages, total_count, page_size,
                interaction.user.id, self
            )
            await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
        except app_commands.MissingPermissions:
            await interaction.response.send_message(
                "❌ You need administrator permissions to view confession history.",
                ephemeral=True
            )
        except Exception as e:
            await error_handler.handle_error(e, interaction, "confession-history")


async def setup(bot):
    """Setup function for cog loading"""
    await bot.add_cog(ConfessionCog(bot))
