"""
ShipCog Module

Provides a ship compatibility command for fun pairing between two users.
Supports both prefix and slash commands.

Design notes:
- Stateless (no DB writes) beyond existing global daily counter + throttle hooks.
- Same-guild validation is enforced by using `discord.Member` parameters.
- Uses minimal image compositing (Pillow) for PixxieBot-style layout.
"""

import io
import logging
import random

import discord
import requests
from discord import app_commands
from discord.ext import commands
from PIL import Image, ImageDraw, ImageFont

from configs.ship_messages import SHIP_MESSAGES


class ShipCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def create_composite_image(
        self, user1: discord.Member, user2: discord.Member, percentage: int
    ) -> discord.File | None:
        """Create a composite image with two avatars and a vertical progress bar.

        Resource usage:
        - Memory: ~1-2MB peak (temporary, cleaned immediately)
        - CPU: <100ms for simple compositing
        - No disk I/O (all in-memory with BytesIO)

        Returns:
            discord.File if successful, None if image generation fails (falls back to embed-only).
        """
        try:
            # Download avatars (small size: 256x256 to minimize memory)
            avatar_size = 256
            composite_width = 600
            composite_height = 300

            # Download user1 avatar
            avatar1_response = requests.get(
                user1.display_avatar.url, timeout=5, params={"size": avatar_size}
            )
            avatar1_response.raise_for_status()
            avatar1_img = Image.open(io.BytesIO(avatar1_response.content))
            avatar1_img = avatar1_img.resize((avatar_size, avatar_size), Image.Resampling.LANCZOS)

            # Download user2 avatar
            avatar2_response = requests.get(
                user2.display_avatar.url, timeout=5, params={"size": avatar_size}
            )
            avatar2_response.raise_for_status()
            avatar2_img = Image.open(io.BytesIO(avatar2_response.content))
            avatar2_img = avatar2_img.resize((avatar_size, avatar_size), Image.Resampling.LANCZOS)

            # Create composite canvas
            composite = Image.new("RGB", (composite_width, composite_height), color=(32, 34, 37))  # Discord dark gray

            # Calculate positions (wider bar for better text readability and thicker text)
            padding = 20
            bar_width = 80  # Wider bar for better visibility and thicker text
            available_width = composite_width - (2 * padding) - bar_width
            avatar_spacing = (available_width - (2 * avatar_size)) // 3

            avatar1_x = padding + avatar_spacing
            bar_x = avatar1_x + avatar_size + avatar_spacing
            avatar2_x = bar_x + bar_width + avatar_spacing
            avatar_y = (composite_height - avatar_size) // 2

            # Paste avatars
            composite.paste(avatar1_img, (avatar1_x, avatar_y))
            composite.paste(avatar2_img, (avatar2_x, avatar_y))
            
            bar_y_start = avatar_y
            bar_height = avatar_size
            filled_height = int((percentage / 100) * bar_height)

            draw = ImageDraw.Draw(composite)

            # Bar background (dark)
            draw.rectangle(
                [(bar_x, bar_y_start), (bar_x + bar_width, bar_y_start + bar_height)],
                fill=(30, 32, 35),  # Darker background for better contrast
            )

            # Filled portion (color based on percentage)
            if percentage >= 70:
                bar_color = (46, 204, 113)  # Green
            elif percentage >= 40:
                bar_color = (241, 196, 15)  # Gold
            else:
                bar_color = (231, 76, 60)  # Red

            draw.rectangle(
                [
                    (bar_x, bar_y_start + bar_height - filled_height),
                    (bar_x + bar_width, bar_y_start + bar_height),
                ],
                fill=bar_color,
            )

            # Add percentage text on bar - ensure it fits within bar width
            try:
                text = f"{percentage}%"
                
                # Start with a larger, thicker font size for better visibility
                font_size = 36  # Larger for thicker, more prominent text
                font = None
                font_paths = [
                    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",  # Linux
                    "/System/Library/Fonts/Supplemental/Arial Bold.ttf",  # macOS
                    "C:/Windows/Fonts/arialbd.ttf",  # Windows
                ]
                
                # Try to load a font, scaling down if text doesn't fit
                max_attempts = 3
                for attempt in range(max_attempts):
                    for path in font_paths:
                        try:
                            font = ImageFont.truetype(path, font_size)
                            break
                        except (OSError, IOError):
                            continue
                    
                    if font is None:
                        # Fallback to default font
                        font = ImageFont.load_default()
                    
                    # Check if text fits within bar width (with some padding)
                    bbox = draw.textbbox((0, 0), text, font=font)
                    text_width = bbox[2] - bbox[0]
                    available_width = bar_width - 8  # Leave 4px padding on each side
                    
                    if text_width <= available_width:
                        break  # Text fits, use this font size
                    
                    # Text too wide, reduce font size and try again
                    font_size = int(font_size * 0.85)  # Reduce by 15%
                    font = None
                
                if font is None:
                    font = ImageFont.load_default()
                
                # Get final text dimensions and position
                bbox = draw.textbbox((0, 0), text, font=font)
                text_width = bbox[2] - bbox[0]
                text_height = bbox[3] - bbox[1]
                text_x = bar_x + (bar_width - text_width) // 2
                text_y = bar_y_start + (bar_height - text_height) // 2

                # Draw text with strong black outline for good contrast on all bar colors
                # White text with black outline works well on red, gold, and green
                outline_width = 2  # Stronger outline for better readability
                for adj_x in range(-outline_width, outline_width + 1):
                    for adj_y in range(-outline_width, outline_width + 1):
                        if adj_x != 0 or adj_y != 0:
                            draw.text((text_x + adj_x, text_y + adj_y), text, fill=(0, 0, 0), font=font)
                
                # White text on top - good contrast on red, gold, and green bars
                draw.text((text_x, text_y), text, fill=(255, 255, 255), font=font)
            except Exception as e:
                logging.warning(f"Failed to render text on bar: {e}")
                # If font rendering fails, skip text (bar still visible)
                pass

            # Convert to bytes
            img_bytes = io.BytesIO()
            composite.save(img_bytes, format="PNG", optimize=True)
            img_bytes.seek(0)

            return discord.File(img_bytes, filename="ship_compatibility.png")

        except Exception as e:
            logging.warning(f"Failed to create composite image, falling back to embed-only: {e}")
            return None

    def generate_compatibility(self) -> int:
        """Generate a random compatibility percentage (0-100)."""
        return random.randint(0, 100)

    def create_progress_bar(self, percentage: int) -> str:
        """Create a visual progress bar using Unicode blocks."""
        filled = int(percentage / 5)  # 20 blocks total, each block is 5%
        empty = 20 - filled
        bar = "█" * filled + "░" * empty
        return f"`{bar}` {percentage}%"

    def get_embed_color(self, percentage: int) -> discord.Color:
        """Return embed color based on compatibility percentage."""
        if percentage >= 70:
            return discord.Color.green()
        if percentage >= 40:
            return discord.Color.gold()
        return discord.Color.red()

    def get_heart_emoji(self, percentage: int) -> str:
        """Get dynamic heart emoji based on compatibility percentage."""
        if percentage >= 70:
            return "❤️"  # Red heart for high compatibility
        elif percentage >= 40:
            return "💛"  # Yellow heart for medium compatibility
        else:
            return "💔"  # Broken heart for low compatibility

    def get_clever_message(self, percentage: int) -> str:
        """Pick a message template based on compatibility percentage."""
        if percentage <= 30:
            category = "low"
        elif percentage <= 50:
            category = "medium_low"
        elif percentage <= 70:
            category = "medium"
        elif percentage <= 85:
            category = "high"
        else:
            category = "very_high"

        # Defensive fallback: if messages are missing, return a generic line
        messages = SHIP_MESSAGES.get(category) or []
        if not messages:
            return "The universe is thinking… try again! 🔄"
        return random.choice(messages)

    def create_ship_embed(
        self, user1: discord.Member, user2: discord.Member, percentage: int, has_image: bool = False
    ) -> discord.Embed:
        """Create the ship compatibility embed.

        Args:
            user1: First user
            user2: Second user
            percentage: Compatibility percentage (0-100)
            has_image: If True, composite image will be attached (don't show duplicate info in embed)
        """
        # Dynamic heart emoji based on percentage
        heart_emoji = self.get_heart_emoji(percentage)
        
        embed = discord.Embed(
            title="💕 Ship Compatibility 💕",
            description=f"**{user1.display_name}** {heart_emoji} **{user2.display_name}**",
            color=self.get_embed_color(percentage),
        )

        if has_image:
            # When image is present, only show the verdict (image shows the percentage)
            # Bold text with better spacing (no quote format)
            verdict_message = self.get_clever_message(percentage)
            embed.add_field(
                name="💬 The Verdict",
                value=f"**{verdict_message}**",
                inline=False,
            )
        else:
            # Fallback: show avatars and compatibility info if composite image failed
            embed.set_author(name=user1.display_name, icon_url=user1.display_avatar.url)
            embed.set_thumbnail(url=user2.display_avatar.url)
            
            # Show compatibility info when no image
            embed.add_field(
                name="❤️ Compatibility",
                value=f"**{percentage}%**\n{self.create_progress_bar(percentage)}",
                inline=False,
            )
            
            # Bold text with better spacing (no quote format)
            verdict_message = self.get_clever_message(percentage)
            embed.add_field(
                name="💬 The Verdict",
                value=f"**{verdict_message}**",
                inline=False,
            )

        embed.set_footer(text="🔄 Use the command again for a new result!")
        return embed

    async def _send_ship_embed(
        self,
        source: commands.Context | discord.Interaction,
        *,
        embed: discord.Embed,
        image_file: discord.File | None = None,
        is_slash: bool,
    ) -> None:
        """Send embed for either prefix context or interaction.

        Args:
            source: Command context or interaction
            embed: Discord embed to send
            image_file: Optional composite image file to attach
            is_slash: Whether this is a slash command
        """
        # Reference attached file in embed if present
        if image_file:
            embed.set_image(url=f"attachment://{image_file.filename}")

        if not is_slash:
            await source.send(embed=embed, file=image_file)  # type: ignore[attr-defined]
            return

        interaction: discord.Interaction = source  # type: ignore[assignment]
        if interaction.response.is_done():
            await interaction.followup.send(embed=embed, file=image_file)
        else:
            await interaction.response.send_message(embed=embed, file=image_file)

    async def handle_ship_request(
        self,
        source: commands.Context | discord.Interaction,
        user1: discord.Member,
        user2: discord.Member,
        *,
        is_slash: bool,
    ) -> None:
        """Shared handler for both prefix and slash ship commands."""
        try:
            percentage = self.generate_compatibility()

            # Try to create composite image (PixxieBot-style layout)
            image_file = await self.create_composite_image(user1, user2, percentage)
            has_image = image_file is not None

            embed = self.create_ship_embed(user1, user2, percentage, has_image=has_image)
            await self._send_ship_embed(source, embed=embed, image_file=image_file, is_slash=is_slash)
        except Exception as e:
            logging.error(f"Error in ship command: {e}", exc_info=True)
            error_msg = "❌ An error occurred while calculating compatibility. Try again later!"
            if not is_slash:
                await source.send(error_msg)  # type: ignore[attr-defined]
                return

            interaction: discord.Interaction = source  # type: ignore[assignment]
            if interaction.response.is_done():
                await interaction.followup.send(error_msg, ephemeral=True)
            else:
                await interaction.response.send_message(error_msg, ephemeral=True)

    @commands.command(name="ship", description="Check compatibility between two users.")
    async def prefix_ship(
        self,
        ctx: commands.Context,
        user1: discord.Member | None = None,
        user2: discord.Member | None = None,
    ):
        """Prefix command: !ship @user1 [@user2]

        If only one user is provided, the invoker is used as the second user.
        """
        if user1 is None:
            await ctx.send(f"❌ Usage: `{ctx.prefix}ship @user1 [@user2]`")
            return

        if user2 is None:
            user2 = ctx.author  # type: ignore[assignment]

        await self.handle_ship_request(ctx, user1, user2, is_slash=False)  # type: ignore[arg-type]

    @app_commands.command(name="ship", description="Check compatibility between two users.")
    @app_commands.describe(user1="First user", user2="Second user (optional)")
    async def slash_ship(
        self,
        interaction: discord.Interaction,
        user1: discord.Member,
        user2: discord.Member | None = None,
    ):
        """Slash command: /ship user1:@user1 user2:@user2

        If user2 is omitted, the invoker is used as the second user.
        """
        if user2 is None:
            # In guild context, interaction.user is a Member; default to invoker.
            user2 = interaction.user  # type: ignore[assignment]

        await self.handle_ship_request(interaction, user1, user2, is_slash=True)  # type: ignore[arg-type]


async def setup(bot: commands.Bot):
    await bot.add_cog(ShipCog(bot))

