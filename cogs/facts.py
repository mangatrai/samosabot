"""
FactsCog Module

This module provides a Discord cog for delivering random facts through both prefix and slash commands.
It integrates with external APIs and OpenAI for fact generation, with support for user submissions
and community feedback.

Features:
  - General facts and animal facts from real APIs
  - AI-generated facts as fallback
  - User submissions with community feedback (👍/👎 reactions)
  - Database storage for community-submitted facts
  - Rating options: Family Friendly (PG13) or Adult Only (R)
"""

import discord
from discord.ext import commands
from discord import app_commands
import requests
import logging
import random
import os
from dotenv import load_dotenv
from utils import openai_utils
from configs import prompts

# Load environment variables
load_dotenv()

class FactsCog(commands.Cog):
    """Facts Cog for random facts"""
    
    def __init__(self, bot):
        self.bot = bot
        logging.info("Facts Cog loaded")
    
    def get_general_fact(self):
        """Get general fact with priority: API (70%) -> Database (20%) -> AI (10%)"""
        from utils import astra_db_ops
        
        # Add randomization: 70% API, 20% Database, 10% AI
        rand = random.random()
        
        if rand < 0.7:
            # Try API first (70% chance)
            try:
                api_url = os.getenv("USELESS_FACTS_API_URL", "https://uselessfacts.jsph.pl/api/v2/facts/random?language=en")
                response = requests.get(api_url, timeout=5)
                if response.status_code == 200:
                    data = response.json()
                    fact = data.get("text", "No fact available")
                    logging.debug(f"General fact from API: {fact}")
                    return fact, "api", None, None
            except Exception as e:
                logging.error(f"Error getting general fact from API: {e}")
        
        if rand < 0.9:
            # Try database (20% chance)
            try:
                fact_data = astra_db_ops.get_random_truth_dare_question("general_fact", "PG")
                if fact_data:
                    fact = fact_data.get('question')
                    fact_id = str(fact_data.get('_id'))
                    submitted_by = fact_data.get('submitted_by', 'Community')
                    logging.debug(f"General fact from database: {fact}")
                    return fact, "database", fact_id, submitted_by
            except Exception as e:
                logging.error(f"Error getting general fact from database: {e}")
        
        # Fallback to AI (10% chance or if others fail)
        try:
            fact = self.get_ai_fact("general")
            if fact:
                # Store AI-generated fact in database for future use
                fact_id = astra_db_ops.save_truth_dare_question(
                    guild_id="system",
                    user_id="ai",
                    question=fact,
                    question_type="general_fact",
                    rating="PG",
                    source="llm",
                    submitted_by="AI"
                )
                logging.debug(f"AI-generated general fact: {fact}")
                logging.debug(f"AI-generated fact_id: {fact_id}")
                return fact, "llm", fact_id, "AI"
        except Exception as e:
            logging.error(f"Error generating AI general fact: {e}")
        
        # If all fail, try API as final fallback
        try:
            api_url = os.getenv("USELESS_FACTS_API_URL", "https://uselessfacts.jsph.pl/api/v2/facts/random?language=en")
            response = requests.get(api_url, timeout=5)
            if response.status_code == 200:
                data = response.json()
                fact = data.get("text", "No fact available")
                logging.debug(f"General fact API fallback: {fact}")
                return fact, "api", None, None
        except Exception as e:
            logging.error(f"Error in general fact API fallback: {e}")
        
        return None, None, None, None
    
    def get_animal_fact(self):
        """Get animal fact with priority: API (70%) -> Database (20%) -> AI (10%)"""
        from utils import astra_db_ops
        
        # Add randomization: 70% API, 20% Database, 10% AI
        rand = random.random()
        
        if rand < 0.7:
            # Try API first (70% chance)
            try:
                # Randomly choose between cat and dog facts
                if random.choice([True, False]):
                    # Cat fact
                    cat_api_url = os.getenv("CAT_FACTS_API_URL", "https://catfact.ninja/fact")
                    response = requests.get(cat_api_url, timeout=5)
                    if response.status_code == 200:
                        data = response.json()
                        fact = f"🐱 **Cat Fact:** {data.get('fact', 'No cat fact available')}"
                        logging.debug(f"Cat fact from API: {fact}")
                        return fact, "api", None, None
                else:
                    # Dog fact
                    dog_api_url = os.getenv("DOG_FACTS_API_URL", "https://dogapi.dog/api/v2/facts")
                    response = requests.get(dog_api_url, timeout=5)
                    if response.status_code == 200:
                        data = response.json()
                        if data.get("data") and len(data["data"]) > 0:
                            fact = data["data"][0]["attributes"]["body"]
                            fact = f"🐕 **Dog Fact:** {fact}"
                            logging.debug(f"Dog fact from API: {fact}")
                            return fact, "api", None, None
            except Exception as e:
                logging.error(f"Error getting animal fact from API: {e}")
        
        if rand < 0.9:
            # Try database (20% chance)
            try:
                fact_data = astra_db_ops.get_random_truth_dare_question("animal_fact", "PG")
                if fact_data:
                    fact = fact_data.get('question')
                    fact_id = str(fact_data.get('_id'))
                    submitted_by = fact_data.get('submitted_by', 'Community')
                    logging.debug(f"Animal fact from database: {fact}")
                    return fact, "database", fact_id, submitted_by
            except Exception as e:
                logging.error(f"Error getting animal fact from database: {e}")
        
        # Fallback to AI (10% chance or if others fail)
        try:
            fact = self.get_ai_fact("animals")
            if fact:
                # Store AI-generated fact in database for future use
                fact_id = astra_db_ops.save_truth_dare_question(
                    guild_id="system",
                    user_id="ai",
                    question=fact,
                    question_type="animal_fact",
                    rating="PG",
                    source="llm",
                    submitted_by="AI"
                )
                logging.debug(f"AI-generated animal fact: {fact}")
                logging.debug(f"AI-generated fact_id: {fact_id}")
                return fact, "llm", fact_id, "AI"
        except Exception as e:
            logging.error(f"Error generating AI animal fact: {e}")
        
        # If all fail, try API as final fallback
        try:
            # Try cat fact as final fallback
            cat_api_url = os.getenv("CAT_FACTS_API_URL", "https://catfact.ninja/fact")
            response = requests.get(cat_api_url, timeout=5)
            if response.status_code == 200:
                data = response.json()
                fact = f"🐱 **Cat Fact:** {data.get('fact', 'No cat fact available')}"
                logging.debug(f"Animal fact API fallback: {fact}")
                return fact, "api", None, None
        except Exception as e:
            logging.error(f"Error in animal fact API fallback: {e}")
        
        return None, None, None, None
    
    def get_ai_fact(self, category="general"):
        """Get AI-generated fact as fallback"""
        try:
            if category == "animals":
                prompt = prompts.fact_animals_prompt
            else:
                prompt = prompts.fact_general_prompt
            
            fact = openai_utils.generate_openai_response(prompt)
            return fact
        except Exception as e:
            logging.error(f"Error generating AI fact: {e}")
            return None
    
    @app_commands.command(name="fact", description="Get a random fact")
    @app_commands.choices(category=[
        app_commands.Choice(name="General", value="general"),
        app_commands.Choice(name="Animals", value="animals")
    ])
    async def slash_fact(self, interaction: discord.Interaction, category: str = "general"):
        """
        Get a random fact (slash command).
        
        Categories: General, Animals
        Community-submitted facts support feedback via reactions.
        """
        try:
            await interaction.response.defer()
            
            fact = None
            fact_id = None
            source = None
            submitted_by = None
            
            if category == "general":
                result = self.get_general_fact()
                if result and result[0]:
                    fact, source, fact_id, submitted_by = result
                else:
                    fact = self.get_ai_fact("general")
            elif category == "animals":
                result = self.get_animal_fact()
                if result and result[0]:
                    fact, source, fact_id, submitted_by = result
                else:
                    fact = self.get_ai_fact("animals")
            
            if fact:
                # Handle feedback collection for database content (including AI-generated)
                logging.debug(f"Fact condition check - fact_id: {fact_id}, type: {type(fact_id)}")
                if fact_id:
                    # Create embed for database content
                    category_icon = "📚" if category == "general" else "🐾"
                    embed = discord.Embed(
                        title=f"{category_icon} {category.title()} Fact",
                        description=fact,
                        color=discord.Color.blue()
                    )
                    
                    # Send message with embed
                    message = await interaction.followup.send(embed=embed)
                    
                    # Add emoji reactions for feedback collection
                    await message.add_reaction("👍")
                    await message.add_reaction("👎")
                    
                    # Save message metadata for reaction tracking
                    from utils import astra_db_ops
                    astra_db_ops.add_message_metadata(fact_id, str(message.id), str(interaction.guild_id), str(interaction.channel_id))
                else:
                    # Regular fact display for API/AI content
                    embed = discord.Embed(
                        title="📚 Random Fact",
                        description=fact,
                        color=discord.Color.blue()
                    )
                    embed.set_footer(text=f"Category: {category.title()}")
                    embed.add_field(name="💡 Tip", value="Use `/fact-submit` to share your own facts!", inline=False)
                    await interaction.followup.send(embed=embed)
            else:
                await interaction.followup.send("❌ Sorry, I couldn't get a fact right now. Try again later!")
                
        except Exception as e:
            logging.error(f"Error in slash_fact: {e}")
            await interaction.followup.send("❌ An error occurred while getting your fact.")
    
    @commands.command(name="fact")
    async def prefix_fact(self, ctx, category: str = "general"):
        """
        Get a random fact (prefix command).
        
        Categories: general, animals
        Community-submitted facts support feedback via reactions.
        """
        try:
            fact = None
            fact_id = None
            source = None
            submitted_by = None
            
            if category.lower() in ["general", "g"]:
                result = self.get_general_fact()
                if result and result[0]:
                    fact, source, fact_id, submitted_by = result
                else:
                    # Store AI-generated content in database for feedback collection
                    fact = self.get_ai_fact("general")
                    if fact:
                        from utils import astra_db_ops
                        fact_id = astra_db_ops.save_truth_dare_question(
                            guild_id=str(ctx.guild.id),
                            user_id="ai",
                            question=fact,
                            question_type="general_fact",
                            rating="PG",
                            source="llm",
                            submitted_by="AI"
                        )
                        source = "llm"
                        submitted_by = "AI"
            elif category.lower() in ["animals", "animal", "a"]:
                result = self.get_animal_fact()
                if result and result[0]:
                    fact, source, fact_id, submitted_by = result
                else:
                    # Store AI-generated content in database for feedback collection
                    fact = self.get_ai_fact("animals")
                    if fact:
                        from utils import astra_db_ops
                        fact_id = astra_db_ops.save_truth_dare_question(
                            guild_id=str(ctx.guild.id),
                            user_id="ai",
                            question=fact,
                            question_type="animal_fact",
                            rating="PG",
                            source="llm",
                            submitted_by="AI"
                        )
                        source = "llm"
                        submitted_by = "AI"
            else:
                await ctx.send("❌ Invalid category! Use `general` or `animals`")
                return
            
            if fact:
                # Handle feedback collection for database content (including AI-generated)
                if fact_id:
                    # Create embed for database content
                    category_icon = "📚" if category.lower() in ["general", "g"] else "🐾"
                    embed = discord.Embed(
                        title=f"{category_icon} {category.title()} Fact",
                        description=fact,
                        color=discord.Color.blue()
                    )
                    
                    # Send message with embed
                    message = await ctx.send(embed=embed)
                    
                    # Add emoji reactions for feedback collection
                    await message.add_reaction("👍")
                    await message.add_reaction("👎")
                    
                    # Save message metadata for reaction tracking
                    from utils import astra_db_ops
                    astra_db_ops.add_message_metadata(fact_id, str(message.id), str(ctx.guild.id), str(ctx.channel.id))
                else:
                    # Regular fact display for API/AI content
                    embed = discord.Embed(
                        title="📚 Random Fact",
                        description=fact,
                        color=discord.Color.blue()
                    )
                    embed.add_field(name="💡 Tip", value="Use `/fact-submit` to share your own facts!", inline=False)
                    embed.set_footer(text=f"Category: {category.title()}")
                    await ctx.send(embed=embed)
            else:
                await ctx.send("❌ Sorry, I couldn't get a fact right now. Try again later!")
                
        except Exception as e:
            logging.error(f"Error in prefix_fact: {e}")
            await ctx.send("❌ An error occurred while getting your fact.")

    @app_commands.command(name="fact-submit", description="Submit your own fact")
    @app_commands.choices(category=[
        app_commands.Choice(name="General", value="general_fact"),
        app_commands.Choice(name="Animal", value="animal_fact")
    ])
    @app_commands.choices(rating=[
        app_commands.Choice(name="Family Friendly", value="PG13"),
        app_commands.Choice(name="Adult Only", value="R")
    ])
    async def slash_fact_submit(self, interaction: discord.Interaction, category: str, fact: str, rating: str = "PG"):
        """
        Submit your own fact to the community database.
        
        Args:
            category: General or Animal fact
            fact: Your fact (max 200 characters)
            rating: Family Friendly (PG13) or Adult Only (R)
        """
        try:
            # Validate fact length
            if len(fact) > 200:
                await interaction.response.send_message("❌ Fact is too long! Please keep it under 200 characters.", ephemeral=True)
                return
            
            # Import here to avoid circular imports
            from utils import astra_db_ops
            
            # Save to database
            fact_id = astra_db_ops.save_truth_dare_question(
                guild_id=str(interaction.guild.id),
                user_id=str(interaction.user.id),
                question=fact,
                question_type=category,
                rating=rating,
                source="user",
                submitted_by=interaction.user.display_name
            )
            
            if fact_id:
                category_display = "General" if category == "general_fact" else "Animal"
                await interaction.response.send_message(
                    f"✅ Thanks! Your {category_display.lower()} fact has been submitted for review.\n"
                    f"**Fact:** {fact}\n"
                    f"**Category:** {category_display}\n"
                    f"**Rating:** {rating}",
                    ephemeral=True
                )
            else:
                await interaction.response.send_message("❌ Failed to submit your fact. Please try again later.", ephemeral=True)
                
        except Exception as e:
            logging.error(f"Error in slash_fact_submit: {e}")
            await interaction.response.send_message("❌ An error occurred while submitting your fact.", ephemeral=True)

async def setup(bot):
    """Setup function for cog loading"""
    await bot.add_cog(FactsCog(bot))
