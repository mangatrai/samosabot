"""
JokeCog Module

This module provides a Discord cog for delivering jokes through both traditional prefix
commands and modern slash commands. It integrates with OpenAI via the openai_utils module
and utilizes predefined prompts from the prompts module to generate jokes. A helper function,
format_joke, attempts to parse and format the joke response (expected as JSON) by separating
the setup and punchline into distinct lines. In cases where JSON parsing fails, the function
falls back to a simple string split for formatting.

Features:
  - Supports multiple joke categories such as "General", "Dad Joke", and "Insult".
  - Provides both a text-based command (!joke) and a slash command (/joke) interface.
  - Dynamically generates jokes using OpenAI's API.
  - Logs warnings if the response cannot be parsed as JSON.

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
        except:
            pass
    
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
        joke = openai_utils.generate_openai_response(prompts.joke_dad_prompt)
        if joke:
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
    try:
        response = requests.get(os.getenv("EVILINSULT_URL"), timeout=5)
        if response.status_code == 200:
            insult = response.json().get('insult')
            logging.debug(f"Insult joke API response: {insult}")
            return insult
    except:
        pass
    return None

def get_general_joke():
    try:
        url = f"{os.getenv('JOKEAPI_URL')}Any?blacklistFlags=nsfw,racist,sexist,explicit"
        response = requests.get(url, timeout=5)
        if response.status_code == 200:
            data = response.json()
            if data.get('type') == 'single':
                joke = data.get('joke')
                logging.debug(f"General joke API response: {joke}")
                return joke
            elif data.get('type') == 'twopart':
                joke = f"{data.get('setup', '')}\n{data.get('delivery', '')}"
                logging.debug(f"General joke API response: {joke}")
                return joke
    except:
        pass
    return None

def get_dark_joke():
    try:
        url = f"{os.getenv('JOKEAPI_URL')}Dark?blacklistFlags=racist"
        response = requests.get(url, timeout=5)
        if response.status_code == 200:
            data = response.json()
            if data.get('type') == 'single':
                joke = data.get('joke')
                logging.debug(f"Dark joke API response: {joke}")
                return joke
            elif data.get('type') == 'twopart':
                joke = f"{data.get('setup', '')}\n{data.get('delivery', '')}"
                logging.debug(f"Dark joke API response: {joke}")
                return joke
    except:
        pass
    return None

def get_spooky_joke():
    try:
        url = f"{os.getenv('JOKEAPI_URL')}Spooky?blacklistFlags=racist"
        response = requests.get(url, timeout=5)
        if response.status_code == 200:
            data = response.json()
            if data.get('type') == 'single':
                joke = data.get('joke')
                logging.debug(f"Spooky joke API response: {joke}")
                return joke
            elif data.get('type') == 'twopart':
                joke = f"{data.get('setup', '')}\n{data.get('delivery', '')}"
                logging.debug(f"Spooky joke API response: {joke}")
                return joke
    except:
        pass
    return None

def format_joke(response_text):
    """Parses and formats jokes properly, handling both JSON (AI) and plain text (API) responses."""
    # Try JSON first (AI responses)
    try:
        if response_text.startswith("```json"):
            response_text = response_text.strip("```json").strip("```")
        joke_data = json.loads(response_text)
        setup = joke_data.get("setup", "").strip()
        punchline = joke_data.get("punchline", "").strip()
        if setup and punchline:
            return f"🤣 **Joke:**\n{setup}\n{punchline}"
    except json.JSONDecodeError:
        pass  # Not JSON, continue to plain text handling
    
    # Handle plain text (API responses)
    if '\n' in response_text:
        # Two-part joke
        lines = response_text.split('\n', 1)
        return f"🤣 **Joke:**\n{lines[0]}\n{lines[1]}"
    elif '. ' in response_text:
        # Single sentence with period
        parts = response_text.split('. ', 1)
        return f"🤣 **Joke:**\n{parts[0]}.\n{parts[1]}"
    else:
        # Single line joke
        return f"🤣 **Joke:**\n{response_text.strip()}"

class JokeCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="joke")
    async def joke(self, ctx, category: str = "general"):
        content = None
        
        if category == "insult":
            content = get_insult_joke()
            if content is None:
                content = openai_utils.generate_openai_response(prompts.joke_insult_prompt)
        elif category == "dad":
            result = get_dad_joke()
            if result and result[0]:
                content, source, joke_id, submitted_by = result
                # For database content, we'll add feedback collection in the future
                # For now, just display the joke
            else:
                content = openai_utils.generate_openai_response(prompts.joke_dad_prompt)
        elif category == "dark":
            content = get_dark_joke()
            if content is None:
                content = openai_utils.generate_openai_response(prompts.joke_gen_prompt)
        elif category == "spooky":
            content = get_spooky_joke()
            if content is None:
                content = openai_utils.generate_openai_response(prompts.joke_gen_prompt)
        else:
            content = get_general_joke()
            if content is None:
                content = openai_utils.generate_openai_response(prompts.joke_gen_prompt)
        
        # Create embed for consistent presentation
        embed = discord.Embed(
            title="😄 Joke",
            description=f"### {content}",
            color=discord.Color.green()
        )
        
        # Add fields for better information display
        embed.add_field(name="📋 Type", value=category.title(), inline=True)
        embed.add_field(name="🔗 Source", value="API", inline=True)
        embed.add_field(name="💡 Tip", value="Use `/joke-submit` to share your own jokes!", inline=False)
        
        await ctx.send(embed=embed)

    @app_commands.command(name="joke", description="Get a joke")
    @app_commands.choices(category=[
        app_commands.Choice(name="Dad Joke", value="dad"),
        app_commands.Choice(name="Insult", value="insult"),
        app_commands.Choice(name="General", value="general"),
        app_commands.Choice(name="Dark", value="dark"),
        app_commands.Choice(name="Spooky", value="spooky")
    ])
    async def slash_joke(self, interaction: discord.Interaction, category: str):
        content = None
        joke_id = None
        source = None
        submitted_by = None
        
        if category == "insult":
            content = get_insult_joke()
            if content is None:
                content = openai_utils.generate_openai_response(prompts.joke_insult_prompt)
        elif category == "dad":
            result = get_dad_joke()
            if result and result[0]:
                content, source, joke_id, submitted_by = result
            else:
                content = openai_utils.generate_openai_response(prompts.joke_dad_prompt)
        elif category == "dark":
            content = get_dark_joke()
            if content is None:
                content = openai_utils.generate_openai_response(prompts.joke_gen_prompt)
        elif category == "spooky":
            content = get_spooky_joke()
            if content is None:
                content = openai_utils.generate_openai_response(prompts.joke_gen_prompt)
        else:
            content = get_general_joke()
            if content is None:
                content = openai_utils.generate_openai_response(prompts.joke_gen_prompt)
        
        # Handle feedback collection for database content (including AI-generated)
        if joke_id:
            # Defer response to allow for embed and reactions
            await interaction.response.defer()
            
            # Create embed for database content
            embed = discord.Embed(
                title="😄 Dad Joke",
                description=f"### {content}",
                color=discord.Color.orange()
            )
            
            # Add fields for better information display
            embed.add_field(name="📋 Type", value="Dad Joke", inline=True)
            embed.add_field(name="👤 Submitted by", value=submitted_by, inline=True)
            embed.add_field(name="📊 Community Joke", value="React with 👍 if you like this joke, 👎 if you don't!", inline=False)
            
            # Send message with embed
            message = await interaction.followup.send(embed=embed)
            
            # Add emoji reactions for feedback collection
            await message.add_reaction("👍")
            await message.add_reaction("👎")
            
            # Save message metadata for reaction tracking
            from utils import astra_db_ops
            astra_db_ops.add_message_metadata(joke_id, str(message.id), str(interaction.guild_id), str(interaction.channel_id))
        else:
            # Regular joke display for API/AI content with embed
            await interaction.response.defer()
            
            # Create embed for API/AI content
            embed = discord.Embed(
                title="😄 Joke",
                description=f"### {content}",
                color=discord.Color.green()
            )
            
            # Add fields for better information display
            embed.add_field(name="📋 Type", value=category.title(), inline=True)
            embed.add_field(name="🔗 Source", value=source.title() if source else "API", inline=True)
            embed.add_field(name="💡 Tip", value="Use `/joke-submit` to share your own jokes!", inline=False)
            
            await interaction.followup.send(embed=embed)

    @app_commands.command(name="joke-submit", description="Submit your own dad joke")
    @app_commands.choices(rating=[
        app_commands.Choice(name="Family Friendly", value="PG"),
        app_commands.Choice(name="Adult Only", value="PG13")
    ])
    async def slash_joke_submit(self, interaction: discord.Interaction, joke: str, rating: str = "PG"):
        """Submit a custom dad joke."""
        try:
            # Validate joke length
            if len(joke) > 200:
                await interaction.response.send_message("❌ Joke is too long! Please keep it under 200 characters.", ephemeral=True)
                return
            
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
                await interaction.response.send_message(
                    f"✅ Thanks! Your dad joke has been submitted for review.\n"
                    f"**Joke:** {joke}\n"
                    f"**Rating:** {rating}",
                    ephemeral=True
                )
            else:
                await interaction.response.send_message("❌ Failed to submit your joke. Please try again later.", ephemeral=True)
                
        except Exception as e:
            logging.error(f"Error in slash_joke_submit: {e}")
            await interaction.response.send_message("❌ An error occurred while submitting your joke.", ephemeral=True)

async def setup(bot):
    await bot.add_cog(JokeCog(bot))