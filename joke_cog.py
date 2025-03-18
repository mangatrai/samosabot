import discord
from discord.ext import commands
from discord import app_commands
import openai_utils
import prompts
import json
import logging

def format_joke(response_text):
    """Parses and formats jokes properly, ensuring setup and punchline appear on separate lines."""
    try:
        if response_text.startswith("```json"):
            response_text = response_text.strip("```json").strip("```")
        joke_data = json.loads(response_text)
        setup = joke_data.get("setup", "").strip()
        punchline = joke_data.get("punchline", "").strip()
        if setup and punchline:
            return f"🤣 **Joke:**\n{setup}\n{punchline}"
    except json.JSONDecodeError:
        logging.warning(f"Failed to parse JSON: {response_text}")
    if '. ' in response_text:
        parts = response_text.split('. ', 1)
        return f"🤣 **Joke:**\n{parts[0]}.\n{parts[1]}"
    return f"🤣 **Joke:**\n{response_text.strip()}"

class JokeCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="joke")
    async def joke(self, ctx, category: str = "general"):
        if category == "insult":
            content = openai_utils.generate_openai_prompt(prompts.joke_insult_prompt)
        elif category == "dad":
            content = openai_utils.generate_openai_prompt(prompts.joke_dad_prompt)
        else:
            content = openai_utils.generate_openai_prompt(prompts.joke_gen_prompt)
        formatted_joke = format_joke(content)
        await ctx.send(formatted_joke)

    @app_commands.command(name="joke", description="Get a joke")
    @app_commands.choices(category=[
        app_commands.Choice(name="Dad Joke", value="dad"),
        app_commands.Choice(name="Insult", value="insult"),
        app_commands.Choice(name="General", value="general")
    ])
    async def slash_joke(self, interaction: discord.Interaction, category: str):
        if category == "insult":
            content = openai_utils.generate_openai_prompt(prompts.joke_insult_prompt)
        elif category == "dad":
            content = openai_utils.generate_openai_prompt(prompts.joke_dad_prompt)
        else:
            content = openai_utils.generate_openai_prompt(prompts.joke_gen_prompt)
        formatted_joke = format_joke(content)
        await interaction.response.send_message(formatted_joke)

async def setup(bot):
    await bot.add_cog(JokeCog(bot))