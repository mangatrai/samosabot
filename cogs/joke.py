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
    try:
        response = requests.get(os.getenv("ICANHAZDADJOKE_URL"), headers={"Accept": "application/json"}, timeout=5)
        if response.status_code == 200:
            joke = response.json().get('joke')
            logging.debug(f"Dad joke API response: {joke}")
            return joke
    except:
        pass
    return None

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
            content = get_dad_joke()
            if content is None:
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
        
        formatted_joke = format_joke(content)
        await ctx.send(formatted_joke)

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
        
        if category == "insult":
            content = get_insult_joke()
            if content is None:
                content = openai_utils.generate_openai_response(prompts.joke_insult_prompt)
        elif category == "dad":
            content = get_dad_joke()
            if content is None:
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
        
        formatted_joke = format_joke(content)
        await interaction.response.send_message(formatted_joke)

async def setup(bot):
    await bot.add_cog(JokeCog(bot))