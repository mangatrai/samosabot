"""
Jen Trigger System - Discord Cog
Triggers animal facts when "Jen" or variations are mentioned in text or @ mentions
"""

import discord
from discord.ext import commands
import logging
import time
import random
from difflib import SequenceMatcher
import re
from cogs.facts import FactsCog

# Configuration
JEN_FUZZY_THRESHOLD = 0.8   # Fuzzy matching threshold (same as Jeremy)
JEN_COOLDOWN_MINUTES = 10   # Cooldown between triggers per channel
JEN_GUILD_ID = 1310795271692750909  # Only trigger in this specific guild

# Track last trigger time per channel
last_triggered = {}

def fuzzy_match(text, target, threshold=JEN_FUZZY_THRESHOLD):
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

def is_on_cooldown(channel_id, cooldown_minutes=JEN_COOLDOWN_MINUTES):
    """Check if channel is on cooldown"""
    if channel_id not in last_triggered:
        return False
    
    time_since_last = time.time() - last_triggered[channel_id]
    return time_since_last < (cooldown_minutes * 60)

def update_cooldown(channel_id):
    """Update cooldown timestamp for channel"""
    last_triggered[channel_id] = time.time()

# Global facts cog instance (will be initialized in setup)
facts_cog = None

def check_text_for_jen(text):
    """Check if text contains Jen or variations using fuzzy matching"""
    jen_variations = ["jen", "jennifer", "jenny", "jenn","jenticles","jenkin"]
    
    # Check for exact matches first (for hyphenated names)
    text_lower = text.lower()
    for variation in jen_variations:
        if variation in text_lower:
            return True, variation, 1.0
    
    # Use fuzzy matching for all variations
    for variation in jen_variations:
        match_found, matched_word, similarity = fuzzy_match(text, variation)
        if match_found:
            return True, matched_word, similarity
    
    return False, None, 0

def check_mentions_for_jen(message):
    """Check if any mentioned users match Jen"""
    jen_variations = ["jen", "jennifer", "jenny", "j-dawg", "jenn"]
    
    for user in message.mentions:
        # Check display name
        for variation in jen_variations:
            if variation in user.display_name.lower():
                return True, user.display_name, 1.0
            match_found, matched_word, similarity = fuzzy_match(user.display_name, variation)
            if match_found:
                return True, matched_word, similarity
        
        # Check username
        for variation in jen_variations:
            if variation in user.name.lower():
                return True, user.name, 1.0
            match_found, matched_word, similarity = fuzzy_match(user.name, variation)
            if match_found:
                return True, matched_word, similarity
    
    return False, None, 0

async def handle_jen_trigger(message):
    """Main handler for Jen triggers"""
    # Skip bot messages
    if message.author.bot:
        return
    
    # Only trigger in specific guild
    if message.guild is None or message.guild.id != JEN_GUILD_ID:
        return
    
    # Check text content first
    text_match, matched_word, similarity = check_text_for_jen(message.content)
    if text_match:
        logging.info(f"Jen trigger word '{matched_word}' found in text (similarity: {similarity:.2f}) by {message.author.name} in channel {message.channel.id}")
        
        # Check cooldown
        if is_on_cooldown(message.channel.id):
            logging.info(f"Jen trigger blocked by cooldown in channel {message.channel.id}")
            return
        
        await trigger_jen_animal_fact(message, matched_word, similarity, "text")
        return
    
    # Check mentions
    mention_match, matched_word, similarity = check_mentions_for_jen(message)
    if mention_match:
        logging.info(f"Jen trigger word '{matched_word}' found in mention (similarity: {similarity:.2f}) by {message.author.name} in channel {message.channel.id}")
        
        # Check cooldown
        if is_on_cooldown(message.channel.id):
            logging.info(f"Jen trigger blocked by cooldown in channel {message.channel.id}")
            return
        
        await trigger_jen_animal_fact(message, matched_word, similarity, "mention")
        return

async def trigger_jen_animal_fact(message, matched_word, similarity, source_type):
    """Trigger animal fact for Jen mention"""
    try:
        # Get animal fact using facts cog
        if facts_cog is None:
            logging.error("Facts cog not initialized")
            return
            
        fact = facts_cog.get_animal_fact()
        if not fact:
            logging.warning("Failed to get animal fact for Jen trigger")
            return
        
        # Fun, punchy responses that match Jen's personality
        if similarity < 1.0:
            # Fuzzy match - playful acknowledgment
            responses = [
                f"Ooh, I heard '{matched_word}' - that's close enough to Jen! 🐾 {fact}",
                f"'{matched_word}'? Close enough! Jen would love this! 🐕 {fact}",
                f"Did someone say '{matched_word}'? That sounds like Jen! 🐱 {fact}"
            ]
        else:
            # Exact match - direct and fun
            responses = [
                f"Jen detected! Time for an animal fact! 🐾 {fact}",
                f"Ah, Jen! The animal lover herself! 🐕 {fact}",
                f"Jen's here! Let's honor her with a furry fact! 🐱 {fact}",
                f"Jen spotted! Time to channel her inner animal lover! 🐾 {fact}"
            ]
        
        # Pick a random response
        response = random.choice(responses)
        
        # Send response
        await message.channel.send(response)
        
        # Update cooldown
        update_cooldown(message.channel.id)
        
        logging.info(f"Jen trigger activated in channel {message.channel.id} by {message.author.name} (source: {source_type}, matched: '{matched_word}', similarity: {similarity:.2f})")
        
    except Exception as e:
        logging.error(f"Error triggering Jen animal fact: {e}")

def get_jen_trigger_status():
    """Get current status of Jen trigger system"""
    return {
        "threshold": JEN_FUZZY_THRESHOLD,
        "cooldown_minutes": JEN_COOLDOWN_MINUTES,
        "active_channels": len(last_triggered)
    }

class JenTriggerCog(commands.Cog):
    """Jen Trigger System Cog"""
    
    def __init__(self, bot):
        self.bot = bot
        global facts_cog
        facts_cog = FactsCog(bot)  # Initialize facts cog
        logging.info("Jen Trigger Cog loaded")
    
    @commands.Cog.listener()
    async def on_message(self, message):
        """Handle Jen triggers"""
        await handle_jen_trigger(message)

async def setup(bot):
    """Setup function for cog loading"""
    await bot.add_cog(JenTriggerCog(bot))
