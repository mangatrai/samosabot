"""
JokeCog Module

This module provides a Discord cog for delivering jokes through both traditional prefix
commands and modern slash commands. It integrates with OpenAI via the openai_utils module
and utilizes predefined prompts from the prompts module to generate jokes.

Features:
  - Supports multiple joke categories such as "General", "Dad Joke", "Insult", "Dark", and "Spooky".
  - Provides both a text-based command (!joke) and a slash command (/joke) interface.
  - Dynamically generates jokes using OpenAI's API with fallback to external APIs.
  - Database support for dad jokes with feedback collection.
  - Standardized return format across all joke functions for consistency.

Usage:
  Load this cog into your Discord bot to allow users to request jokes by invoking the
  respective commands.
"""

import discord
from discord.ext import commands
from discord import app_commands
from utils import openai_utils
from configs import prompts
import json
import logging
import os
import requests
from dotenv import load_dotenv

load_dotenv()

# API functions
def get_dad_joke():
    """Get dad joke with priority: API (70%) -> Database (20%) -> AI (10%)"""
    import random
    from utils import astra_db_ops
    
    # Add randomization: 70% API, 20% Database, 10% AI
    rand = random.random()
    
    if rand < 0.7:
        # Try API first (70% chance)
        try:
            response = requests.get(os.getenv("ICANHAZDADJOKE_URL"), headers={"Accept": "application/json"}, timeout=5)
            if response.status_code == 200:
                joke = response.json().get('joke')
                logging.debug(f"Dad joke API response: {joke}")
                return joke, "api", None, None
        except Exception as e:
            logging.error(f"Error getting dad joke from API: {e}")
    
    if rand < 0.9:
        # Try database (20% chance)
        try:
            joke_data = astra_db_ops.get_random_truth_dare_question("dad_joke", "PG")
            if joke_data:
                joke = joke_data.get('question')
                joke_id = str(joke_data.get('_id'))
                submitted_by = joke_data.get('submitted_by', 'Community')
                logging.debug(f"Dad joke from database: {joke}")
                return joke, "database", joke_id, submitted_by
        except Exception as e:
            logging.error(f"Error getting dad joke from database: {e}")
    
    # Fallback to AI (10% chance or if others fail)
    try:
        joke_response = openai_utils.generate_openai_response(prompts.joke_dad_prompt)
        if joke_response:
            # Parse JSON response and format as two-step joke
            try:
                import json
                # Remove markdown formatting if present
                if joke_response.startswith("```json"):
                    joke_response = joke_response.strip("```json").strip("```").strip()
                elif joke_response.startswith("```"):
                    joke_response = joke_response.strip("```").strip()
                
                joke_data = json.loads(joke_response)
                setup = joke_data.get("setup", "")
                punchline = joke_data.get("punchline", "")
                joke = f"{setup}\n\n{punchline}"
                
                # Store AI-generated joke in database for future use
                joke_id = astra_db_ops.save_truth_dare_question(
                    guild_id="system",
                    user_id="ai",
                    question=joke,
                    question_type="dad_joke",
                    rating="PG",
                    source="llm",
                    submitted_by="AI"
                )
                logging.debug(f"AI-generated dad joke: {joke}")
                logging.debug(f"AI-generated joke_id: {joke_id}")
                return joke, "llm", joke_id, "AI"
            except (json.JSONDecodeError, KeyError) as e:
                logging.error(f"Failed to parse AI joke JSON: {joke_response}. Error: {e}")
                # Fallback to treating as single joke
                joke = joke_response
                joke_id = astra_db_ops.save_truth_dare_question(
                    guild_id="system",
                    user_id="ai",
                    question=joke,
                    question_type="dad_joke",
                    rating="PG",
                    source="llm",
                    submitted_by="AI"
                )
                logging.debug(f"AI-generated dad joke (fallback): {joke}")
                logging.debug(f"AI-generated joke_id: {joke_id}")
                return joke, "llm", joke_id, "AI"
    except Exception as e:
        logging.error(f"Error generating AI dad joke: {e}")
    
    # If all fail, try API as final fallback
    try:
        response = requests.get(os.getenv("ICANHAZDADJOKE_URL"), headers={"Accept": "application/json"}, timeout=5)
        if response.status_code == 200:
            joke = response.json().get('joke')
            logging.debug(f"Dad joke API fallback: {joke}")
            return joke, "api", None, None
    except:
        pass
    
    return None, None, None, None

def get_insult_joke():
    """Get insult joke with priority: API -> AI fallback"""
    try:
        response = requests.get(os.getenv("EVILINSULT_URL"), timeout=5)
        if response.status_code == 200:
            insult = response.json().get('insult')
            logging.debug(f"Insult joke API response: {insult}")
            return insult, "api", None, None
    except Exception as e:
        logging.error(f"Error getting insult joke from API: {e}")
    return None, None, None, None

def get_general_joke():
    """Get general joke with priority: API -> AI fallback"""
    try:
        url = f"{os.getenv('JOKEAPI_URL')}Any?blacklistFlags=nsfw,racist,sexist,explicit"
        response = requests.get(url, timeout=5)
        if response.status_code == 200:
            data = response.json()
            if data.get('type') == 'single':
                joke = data.get('joke')
                logging.debug(f"General joke API response: {joke}")
                return joke, "api", None, None
            elif data.get('type') == 'twopart':
                setup = data.get('setup', '')
                delivery = data.get('delivery', '')
                joke = f"{setup}\n\n{delivery}"
                logging.debug(f"General joke API response: {joke}")
                return joke, "api", None, None
    except Exception as e:
        logging.error(f"Error getting general joke from API: {e}")
    return None, None, None, None

def get_dark_joke():
    """Get dark joke with priority: API -> AI fallback"""
    try:
        url = f"{os.getenv('JOKEAPI_URL')}Dark?blacklistFlags=racist"
        response = requests.get(url, timeout=5)
        if response.status_code == 200:
            data = response.json()
            if data.get('type') == 'single':
                joke = data.get('joke')
                logging.debug(f"Dark joke API response: {joke}")
                return joke, "api", None, None
            elif data.get('type') == 'twopart':
                setup = data.get('setup', '')
                delivery = data.get('delivery', '')
                joke = f"{setup}\n\n{delivery}"
                logging.debug(f"Dark joke API response: {joke}")
                return joke, "api", None, None
    except Exception as e:
        logging.error(f"Error getting dark joke from API: {e}")
    return None, None, None, None

def get_spooky_joke():
    """Get spooky joke with priority: API -> AI fallback"""
    try:
        url = f"{os.getenv('JOKEAPI_URL')}Spooky?blacklistFlags=racist"
        response = requests.get(url, timeout=5)
        if response.status_code == 200:
            data = response.json()
            if data.get('type') == 'single':
                joke = data.get('joke')
                logging.debug(f"Spooky joke API response: {joke}")
                return joke, "api", None, None
            elif data.get('type') == 'twopart':
                setup = data.get('setup', '')
                delivery = data.get('delivery', '')
                joke = f"{setup}\n\n{delivery}"
                logging.debug(f"Spooky joke API response: {joke}")
                return joke, "api", None, None
    except Exception as e:
        logging.error(f"Error getting spooky joke from API: {e}")
    return None, None, None, None

def format_joke_content(content: str) -> str:
    """Format joke content with proper markdown for single or multi-line jokes."""
    if not content:
        return content
    
    # Check if joke has multiple lines
    if '\n' in content:
        # Multi-line joke - format each line separately
        lines = content.split('\n')
        formatted_lines = []
        for i, line in enumerate(lines):
            line = line.strip()
            if line:  # Only format non-empty lines
                if i == 0:
                    # First line gets the heading format
                    formatted_lines.append(f"### **{line}**")
                else:
                    # Subsequent lines get bold format
                    formatted_lines.append(f"**{line}**")
        return '\n'.join(formatted_lines)
    else:
        # Single-line joke - simple format
        return f"### **{content}**"

class JokeCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def handle_joke_request(self, source, category: str, is_slash: bool = False):
        """Shared handler for both prefix and slash joke commands."""
        content = None
        joke_id = None
        source_type = None
        submitted_by = None
        
        if category == "insult":
            result = get_insult_joke()
            if result and result[0]:
                content, source_type, joke_id, submitted_by = result
            else:
                # AI fallback
                content = openai_utils.generate_openai_response(prompts.joke_insult_prompt)
        elif category == "dad":
            result = get_dad_joke()
            if result and result[0]:
                content, source_type, joke_id, submitted_by = result
            else:
                # AI fallback - store in database for feedback
                content = openai_utils.generate_openai_response(prompts.joke_dad_prompt)
                if content:
                    from utils import astra_db_ops
                    joke_id = astra_db_ops.save_truth_dare_question(
                        guild_id=str(source.guild.id) if hasattr(source, 'guild') else str(source.guild_id),
                        user_id="ai",
                        question=content,
                        question_type="dad_joke",
                        rating="PG",
                        source="llm",
                        submitted_by="AI"
                    )
                    source_type = "llm"
                    submitted_by = "AI"
        elif category == "dark":
            result = get_dark_joke()
            if result and result[0]:
                content, source_type, joke_id, submitted_by = result
            else:
                # AI fallback
                content = openai_utils.generate_openai_response(prompts.joke_gen_prompt)
        elif category == "spooky":
            result = get_spooky_joke()
            if result and result[0]:
                content, source_type, joke_id, submitted_by = result
            else:
                # AI fallback
                content = openai_utils.generate_openai_response(prompts.joke_gen_prompt)
        else:  # general
            result = get_general_joke()
            if result and result[0]:
                content, source_type, joke_id, submitted_by = result
            else:
                # AI fallback
                content = openai_utils.generate_openai_response(prompts.joke_gen_prompt)
        
        if not content:
            error_msg = "❌ Sorry, I couldn't generate a joke right now. Try again later!"
            if is_slash:
                await source.followup.send(error_msg, ephemeral=True)
            else:
                await source.send(error_msg)
            return
        
        # Handle feedback collection for database content (including AI-generated)
        if joke_id:
            # Create embed for database content
            embed = discord.Embed(
                title="😄 Joke",
                description=format_joke_content(content),
                color=discord.Color.orange()
            )
                     
            # Send message with embed
            if is_slash:
                message = await source.followup.send(embed=embed)
            else:
                message = await source.send(embed=embed)
            
            # Add emoji reactions for feedback collection
            await message.add_reaction("👍")
            await message.add_reaction("👎")
            
            # Save message metadata for reaction tracking
            from utils import astra_db_ops
            guild_id = source.guild.id if hasattr(source, 'guild') else source.guild_id
            channel_id = source.channel.id if hasattr(source, 'channel') else source.channel_id
            astra_db_ops.add_message_metadata(joke_id, str(message.id), str(guild_id), str(channel_id))
        else:
            # Regular joke display for API/AI content with embed
            embed = discord.Embed(
                title="😄 Joke",
                description=format_joke_content(content),
                color=discord.Color.green()
            )
            
            # Add fields for better information display
            embed.add_field(name="💡 Tip", value="Use `/joke-submit` to share your own jokes!", inline=False)
            
            if is_slash:
                await source.followup.send(embed=embed)
            else:
                await source.send(embed=embed)

    @commands.command(name="joke")
    async def joke(self, ctx, category: str = "general"):
        """
        Get a joke from various categories.
        
        Categories: dad, insult, general, dark, spooky
        Shows typing indicator while generating.
        """
        async with ctx.typing():
            await self.handle_joke_request(ctx, category, is_slash=False)

    @app_commands.command(name="joke", description="Get a joke")
    @app_commands.choices(category=[
        app_commands.Choice(name="Dad Joke", value="dad"),
        app_commands.Choice(name="Insult", value="insult"),
        app_commands.Choice(name="General", value="general"),
        app_commands.Choice(name="Dark", value="dark"),
        app_commands.Choice(name="Spooky", value="spooky")
    ])
    async def slash_joke(self, interaction: discord.Interaction, category: str):
        """
        Get a joke from various categories (slash command).
        
        Categories: Dad Joke, Insult, General, Dark, Spooky
        Dad jokes support community feedback via reactions.
        """
        await interaction.response.defer()
        await self.handle_joke_request(interaction, category, is_slash=True)

    @app_commands.command(name="joke-submit", description="Submit your own dad joke")
    @app_commands.choices(rating=[
        app_commands.Choice(name="Family Friendly", value="PG"),
        app_commands.Choice(name="Adult Only", value="PG13")
    ])
    async def slash_joke_submit(self, interaction: discord.Interaction, joke: str, rating: str = "PG"):
        """
        Submit your own dad joke to the community database.
        
        Args:
            joke: Your joke (max 200 characters)
            rating: Family Friendly (PG) or Adult Only (PG13)
        """
        try:
            # Validate joke length first
            if len(joke) > 200:
                await interaction.response.send_message("❌ Joke is too long! Please keep it under 200 characters.", ephemeral=True)
                return
            
            # Acknowledge interaction immediately to prevent timeout
            await interaction.response.defer(ephemeral=True)
            
            # Import here to avoid circular imports
            from utils import astra_db_ops
            
            # Save to database
            joke_id = astra_db_ops.save_truth_dare_question(
                guild_id=str(interaction.guild.id),
                user_id=str(interaction.user.id),
                question=joke,
                question_type="dad_joke",
                rating=rating,
                source="user",
                submitted_by=interaction.user.display_name
            )
            
            if joke_id:
                await interaction.followup.send(
                    f"✅ Thanks! Your dad joke has been submitted for review.\n"
                    f"**Joke:** {joke}\n"
                    f"**Rating:** {rating}",
                    ephemeral=True
                )
            else:
                await interaction.followup.send("❌ Failed to submit your joke. Please try again later.", ephemeral=True)
                
        except Exception as e:
            logging.error(f"Error in slash_joke_submit: {e}")
            try:
                if not interaction.response.is_done():
                    await interaction.response.send_message("❌ An error occurred while submitting your joke.", ephemeral=True)
                else:
                    await interaction.followup.send("❌ An error occurred while submitting your joke.", ephemeral=True)
            except:
                pass  # Interaction might be expired

async def setup(bot):
    await bot.add_cog(JokeCog(bot))