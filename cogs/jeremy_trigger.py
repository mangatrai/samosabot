"""
Jeremy Trigger System - Discord Cog
Triggers dad jokes when "Jeremy" or variations are detected in message text
"""

import discord
from discord.ext import commands
import logging
import time
from difflib import SequenceMatcher
import re
from cogs.joke import get_dad_joke

# Configuration
JEREMY_FUZZY_THRESHOLD = 0.8   # Fuzzy matching threshold (increased to reduce false positives)
JEREMY_COOLDOWN_MINUTES = 15   # Cooldown between triggers per channel
JEREMY_GUILD_ID = 1310795271692750909  # Only trigger in this specific guild

# Track last trigger time per channel
last_triggered = {}

def fuzzy_match(text, target, threshold=JEREMY_FUZZY_THRESHOLD):
    """Check if text contains a fuzzy match for target"""
    # Use regex that handles hyphens and other word characters
    words = re.findall(r'\b[\w-]+\b', text.lower())
    for word in words:
        # Skip very short words to reduce false positives
        if len(word) < 3:
            continue
        similarity = SequenceMatcher(None, word, target.lower()).ratio()
        if similarity >= threshold:
            return True, word, similarity
    return False, None, 0

def is_on_cooldown(channel_id, cooldown_minutes=JEREMY_COOLDOWN_MINUTES):
    """Check if channel is on cooldown"""
    if channel_id not in last_triggered:
        return False
    
    time_since_last = time.time() - last_triggered[channel_id]
    return time_since_last < (cooldown_minutes * 60)

def update_cooldown(channel_id):
    """Update cooldown timestamp for channel"""
    last_triggered[channel_id] = time.time()

def check_text_for_jeremy(text):
    """Check if text contains Jeremy or variations using fuzzy matching"""
    jeremy_variations = ["jeremy", "jerry", "jerm", "j-dawg", "jere"]
    
    # Check for exact matches first (for hyphenated names)
    text_lower = text.lower()
    for variation in jeremy_variations:
        if variation in text_lower:
            return True, variation, 1.0
    
    # Use fuzzy matching for all variations
    for variation in jeremy_variations:
        match_found, matched_word, similarity = fuzzy_match(text, variation)
        if match_found:
            return True, matched_word, similarity
    
    return False, None, 0


async def handle_jeremy_trigger(message):
    """Main handler for Jeremy triggers - text detection only"""
    # Skip bot messages
    if message.author.bot:
        return
    
    # Only trigger in specific guild
    if message.guild is None or message.guild.id != JEREMY_GUILD_ID:
        return
    
    # Check text content for Jeremy variations
    text_match, matched_word, similarity = check_text_for_jeremy(message.content)
    if text_match:
        logging.info(f"Jeremy trigger word '{matched_word}' found in text (similarity: {similarity:.2f}) by {message.author.name} in channel {message.channel.id}")
        
        # Check cooldown
        if is_on_cooldown(message.channel.id):
            logging.info(f"Jeremy trigger blocked by cooldown in channel {message.channel.id}")
            return
        
        await trigger_jeremy_joke(message, matched_word, similarity, "text")
        return

async def trigger_jeremy_joke(message, matched_word, similarity, source_type):
    """Trigger dad joke for Jeremy text detection"""
    try:
        # Get dad joke with new return format
        result = get_dad_joke()
        if not result or not result[0]:
            logging.warning("Failed to get dad joke for Jeremy trigger")
            return
        
        content, source, joke_id, submitted_by = result
        
        # Fun, punchy responses that match Jeremy's personality
        if similarity < 1.0:
            # Fuzzy match - playful acknowledgment
            trigger_messages = [
                f"Ooh, I heard '{matched_word}' - that's close enough to Jeremy! 🎯",
                f"'{matched_word}'? Close enough! Jeremy would be proud! 😄",
                f"Did someone say '{matched_word}'? That sounds like Jeremy! 🎭"
            ]
        else:
            # Exact match - direct and fun
            trigger_messages = [
                f"Jeremy detected! Time for a dad joke! 🎪",
                f"Ah, Jeremy! The dad joke master himself! 🎭",
                f"Jeremy's here! Let's honor him with a classic! 🎯",
                f"Jeremy spotted! Time to channel his inner dad! 😄"
            ]
        
        # Pick a random trigger message
        import random
        trigger_message = random.choice(trigger_messages)
        
        # Create embed for consistent presentation
        embed = discord.Embed(
            title="😄 Jeremy's Dad Joke",
            description=f"### {content}",
            color=discord.Color.orange()
        )
        
        # Add fields for better information display
        embed.add_field(name="🎯 Trigger", value=trigger_message, inline=False)
        embed.add_field(name="📋 Type", value="Dad Joke", inline=True)
        embed.add_field(name="🔗 Source", value=source.title() if source else "API", inline=True)
        
        # Handle feedback collection for database content
        if joke_id:
            embed.add_field(name="👤 Submitted by", value=submitted_by, inline=True)
            embed.add_field(name="📊 Community Joke", value="React with 👍 if you like this joke, 👎 if you don't!", inline=False)
            
            # Send message with embed
            sent_message = await message.channel.send(embed=embed)
            
            # Add emoji reactions for feedback collection
            await sent_message.add_reaction("👍")
            await sent_message.add_reaction("👎")
            
            # Save message metadata for reaction tracking
            from utils import astra_db_ops
            astra_db_ops.add_message_metadata(joke_id, str(sent_message.id), str(message.guild.id), str(message.channel.id))
        else:
            # Regular embed for API content
            embed.add_field(name="💡 Tip", value="Use `/joke-submit` to share your own jokes!", inline=False)
            await message.channel.send(embed=embed)
        
        # Update cooldown
        update_cooldown(message.channel.id)
        
        logging.info(f"Jeremy trigger activated in channel {message.channel.id} by {message.author.name} (source: {source_type}, matched: '{matched_word}', similarity: {similarity:.2f})")
        
    except Exception as e:
        logging.error(f"Error triggering Jeremy joke: {e}")

def get_jeremy_trigger_status():
    """Get current status of Jeremy trigger system"""
    return {
        "threshold": JEREMY_FUZZY_THRESHOLD,
        "cooldown_minutes": JEREMY_COOLDOWN_MINUTES,
        "active_channels": len(last_triggered)
    }

class JeremyTriggerCog(commands.Cog):
    """Jeremy Trigger System Cog"""
    
    def __init__(self, bot):
        self.bot = bot
        logging.info("Jeremy Trigger Cog loaded")
    
    @commands.Cog.listener()
    async def on_message(self, message):
        """Handle Jeremy triggers"""
        await handle_jeremy_trigger(message)

async def setup(bot):
    """Setup function for cog loading"""
    await bot.add_cog(JeremyTriggerCog(bot))
