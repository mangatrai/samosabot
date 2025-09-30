"""
Facts Cog - Random facts from various APIs
"""

import discord
from discord.ext import commands
from discord import app_commands
import requests
import logging
import random
from utils import openai_utils
from configs import prompts

class FactsCog(commands.Cog):
    """Facts Cog for random facts"""
    
    def __init__(self, bot):
        self.bot = bot
        logging.info("Facts Cog loaded")
    
    def get_general_fact(self):
        """Get a general random fact from Useless Facts API"""
        try:
            response = requests.get("https://uselessfacts.jsph.pl/api/v2/facts/random?language=en", timeout=5)
            if response.status_code == 200:
                data = response.json()
                return data.get("text", "No fact available")
            return None
        except Exception as e:
            logging.error(f"Error getting general fact: {e}")
            return None
    
    def get_animal_fact(self):
        """Get a random animal fact (cat or dog)"""
        try:
            # Randomly choose between cat and dog facts
            if random.choice([True, False]):
                # Cat fact
                response = requests.get("https://catfact.ninja/fact", timeout=5)
                if response.status_code == 200:
                    data = response.json()
                    return f"🐱 **Cat Fact:** {data.get('fact', 'No cat fact available')}"
            else:
                # Dog fact
                response = requests.get("https://dogapi.dog/api/v2/facts", timeout=5)
                if response.status_code == 200:
                    data = response.json()
                    if data.get("data") and len(data["data"]) > 0:
                        fact = data["data"][0]["attributes"]["body"]
                        return f"🐕 **Dog Fact:** {fact}"
            return None
        except Exception as e:
            logging.error(f"Error getting animal fact: {e}")
            return None
    
    def get_ai_fact(self, category="general"):
        """Get AI-generated fact as fallback"""
        try:
            if category == "animals":
                prompt = prompts.fact_animals_prompt
            else:
                prompt = prompts.fact_general_prompt
            
            fact = openai_utils.generate_openai_response(prompt)
            return f"🤖 **AI Generated Fact:** {fact}"
        except Exception as e:
            logging.error(f"Error generating AI fact: {e}")
            return None
    
    @app_commands.command(name="fact", description="Get a random fact")
    @app_commands.choices(category=[
        app_commands.Choice(name="General", value="general"),
        app_commands.Choice(name="Animals", value="animals")
    ])
    async def slash_fact(self, interaction: discord.Interaction, category: str = "general"):
        """Main facts slash command"""
        try:
            await interaction.response.defer()
            
            fact = None
            
            if category == "general":
                # Try general facts API first
                fact = self.get_general_fact()
                if not fact:
                    # Fallback to AI
                    fact = self.get_ai_fact("general")
            elif category == "animals":
                # Try animal facts API first
                fact = self.get_animal_fact()
                if not fact:
                    # Fallback to AI
                    fact = self.get_ai_fact("animals")
            
            if fact:
                embed = discord.Embed(
                    title="📚 Random Fact",
                    description=fact,
                    color=discord.Color.blue()
                )
                embed.set_footer(text=f"Category: {category.title()}")
                await interaction.followup.send(embed=embed)
            else:
                await interaction.followup.send("❌ Sorry, I couldn't get a fact right now. Try again later!")
                
        except Exception as e:
            logging.error(f"Error in slash_fact: {e}")
            await interaction.followup.send("❌ An error occurred while getting your fact.")
    
    @commands.command(name="fact")
    async def prefix_fact(self, ctx, category: str = "general"):
        """Prefix command for facts"""
        try:
            fact = None
            
            if category.lower() in ["general", "g"]:
                # Try general facts API first
                fact = self.get_general_fact()
                if not fact:
                    # Fallback to AI
                    fact = self.get_ai_fact("general")
            elif category.lower() in ["animals", "animal", "a"]:
                # Try animal facts API first
                fact = self.get_animal_fact()
                if not fact:
                    # Fallback to AI
                    fact = self.get_ai_fact("animals")
            else:
                await ctx.send("❌ Invalid category! Use `general` or `animals`")
                return
            
            if fact:
                embed = discord.Embed(
                    title="📚 Random Fact",
                    description=fact,
                    color=discord.Color.blue()
                )
                embed.set_footer(text=f"Category: {category.title()}")
                await ctx.send(embed=embed)
            else:
                await ctx.send("❌ Sorry, I couldn't get a fact right now. Try again later!")
                
        except Exception as e:
            logging.error(f"Error in prefix_fact: {e}")
            await ctx.send("❌ An error occurred while getting your fact.")

async def setup(bot):
    """Setup function for cog loading"""
    await bot.add_cog(FactsCog(bot))
