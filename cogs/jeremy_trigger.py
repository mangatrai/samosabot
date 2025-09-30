"""
Jeremy Trigger System - Discord Cog
Triggers dad jokes when "Jeremy" or variations are mentioned in text or @ mentions
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
JEREMY_COOLDOWN_MINUTES = 10   # Cooldown between triggers per channel
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

def check_mentions_for_jeremy(message):
    """Check if any mentioned users match Jeremy"""
    jeremy_variations = ["jeremy", "jerry", "jerm", "j-dawg", "jere"]
    
    for user in message.mentions:
        # Check display name
        for variation in jeremy_variations:
            if variation in user.display_name.lower():
                return True, user.display_name, 1.0
            # Check fuzzy match
            match_found, matched_word, similarity = fuzzy_match(user.display_name, variation)
            if match_found:
                return True, matched_word, similarity
        
        # Check username
        for variation in jeremy_variations:
            if variation in user.name.lower():
                return True, user.name, 1.0
            # Check fuzzy match
            match_found, matched_word, similarity = fuzzy_match(user.name, variation)
            if match_found:
                return True, matched_word, similarity
    
    return False, None, 0

async def handle_jeremy_trigger(message):
    """Main handler for Jeremy triggers"""
    # Skip bot messages
    if message.author.bot:
        return
    
    # Only trigger in specific guild
    if message.guild is None or message.guild.id != JEREMY_GUILD_ID:
        return
    
    # Check text content first
    text_match, matched_word, similarity = check_text_for_jeremy(message.content)
    if text_match:
        logging.info(f"Jeremy trigger word '{matched_word}' found in text (similarity: {similarity:.2f}) by {message.author.name} in channel {message.channel.id}")
        
        # Check cooldown
        if is_on_cooldown(message.channel.id):
            logging.info(f"Jeremy trigger blocked by cooldown in channel {message.channel.id}")
            return
        
        await trigger_jeremy_joke(message, matched_word, similarity, "text")
        return
    
    # Check mentions
    mention_match, matched_word, similarity = check_mentions_for_jeremy(message)
    if mention_match:
        logging.info(f"Jeremy trigger word '{matched_word}' found in mention (similarity: {similarity:.2f}) by {message.author.name} in channel {message.channel.id}")
        
        # Check cooldown
        if is_on_cooldown(message.channel.id):
            logging.info(f"Jeremy trigger blocked by cooldown in channel {message.channel.id}")
            return
        
        await trigger_jeremy_joke(message, matched_word, similarity, "mention")
        return

async def trigger_jeremy_joke(message, matched_word, similarity, source_type):
    """Trigger dad joke for Jeremy mention"""
    try:
        # Get dad joke
        joke = get_dad_joke()
        if not joke:
            logging.warning("Failed to get dad joke for Jeremy trigger")
            return
        
        # Fun, punchy responses that match Jeremy's personality
        if similarity < 1.0:
            # Fuzzy match - playful acknowledgment
            responses = [
                f"Ooh, I heard '{matched_word}' - that's close enough to Jeremy! 🎯 {joke}",
                f"'{matched_word}'? Close enough! Jeremy would be proud! 😄 {joke}",
                f"Did someone say '{matched_word}'? That sounds like Jeremy! 🎭 {joke}"
            ]
        else:
            # Exact match - direct and fun
            responses = [
                f"Jeremy detected! Time for a dad joke! 🎪 {joke}",
                f"Ah, Jeremy! The dad joke master himself! 🎭 {joke}",
                f"Jeremy's here! Let's honor him with a classic! 🎯 {joke}",
                f"Jeremy spotted! Time to channel his inner dad! 😄 {joke}"
            ]
        
        # Pick a random response
        import random
        response = random.choice(responses)
        
        # Send response
        await message.channel.send(response)
        
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
