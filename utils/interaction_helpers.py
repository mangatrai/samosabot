"""
Shared helpers for Discord component interactions.
Reusable by any cog that uses persistent buttons (e.g. confession approval).
"""
import discord


async def get_interaction_message(interaction: discord.Interaction) -> discord.Message | None:
    """
    Return the message that contained the component, fetching if partial.
    Use before reading interaction.message.embeds or other message content
    (e.g. after bot restart the message may be partial).
    """
    if not interaction.message:
        return None
    msg = interaction.message
    if getattr(msg, "partial", False) and msg.partial:
        try:
            msg = await msg.fetch()
        except Exception:
            return None
    return msg
