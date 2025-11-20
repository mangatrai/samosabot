"""
TruthDareCog Module

This module provides a Discord cog for Truth or Dare games with multiple game types and rating options.
It supports both prefix and slash commands, persistent buttons that work after bot restarts, and
community submissions with feedback collection.

Features:
  - Multiple game types: Truth, Dare, Would You Rather, Never Have I Ever, Paranoia
  - Rating options: Family-friendly (PG13) or Adult Only (R)
  - Persistent interactive buttons for continuous gameplay
  - User submissions with community feedback (👍/👎 reactions)
  - Multiple content sources: External API, community database, AI generation
  - Clean embed presentation with question formatting
"""

import discord
from discord.ext import commands
from discord import app_commands
import logging
import os
import requests
import random
from dotenv import load_dotenv

# Import existing utilities
from utils import astra_db_ops
from utils import openai_utils
from configs import prompts

load_dotenv()

class TruthDareCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.api_base_url = os.getenv("TRUTH_DARE_API_URL", "https://api.truthordarebot.xyz/v1")

    def get_api_question(self, question_type: str, rating: str = "PG13"):
        """Get a question from the Truth or Dare Bot API."""
        try:
            # Map our types to API endpoints
            endpoint_map = {
                "truth": "truth",
                "dare": "dare", 
                "wyr": "wyr",
                "nhie": "nhie",
                "paranoia": "paranoia"
            }
            
            endpoint = endpoint_map.get(question_type)
            if not endpoint:
                return None, None
                
            url = f"{self.api_base_url}/{endpoint}"
            if rating not in ["PG", "PG13"]:
                url += f"?rating={rating}"
                
            response = requests.get(url, timeout=5)
            if response.status_code == 200:
                data = response.json()
                question = data.get("question", "")
                question_id = data.get("id", "API")
                logging.debug(f"API {question_type} response: {question}")
                return question, question_id
        except Exception as e:
            logging.error(f"Error getting API question: {e}")
        return None, None

    def get_llm_question(self, question_type: str, rating: str = "PG13"):
        """Get a question from LLM using existing prompts."""
        try:
            # Map to prompt variables
            prompt_map = {
                ("truth", "PG"): prompts.truth_pg_prompt,
                ("truth", "PG13"): prompts.truth_pg13_prompt,
                ("truth", "R"): prompts.truth_r_prompt,
                ("dare", "PG"): prompts.dare_pg_prompt,
                ("dare", "PG13"): prompts.dare_pg13_prompt,
                ("dare", "R"): prompts.dare_r_prompt,
                ("wyr", "PG"): prompts.wyr_pg_prompt,
                ("wyr", "PG13"): prompts.wyr_pg13_prompt,
                ("wyr", "R"): prompts.wyr_r_prompt,
                ("nhie", "PG"): prompts.nhie_pg_prompt,
                ("nhie", "PG13"): prompts.nhie_pg13_prompt,
                ("nhie", "R"): prompts.nhie_r_prompt,
                ("paranoia", "PG"): prompts.paranoia_pg_prompt,
                ("paranoia", "PG13"): prompts.paranoia_pg13_prompt,
                ("paranoia", "R"): prompts.paranoia_r_prompt,
            }
            
            prompt = prompt_map.get((question_type, rating))
            if prompt:
                question = openai_utils.generate_openai_response(prompt)
                logging.debug(f"LLM {question_type} response: {question}")
                return question, "AI"
        except Exception as e:
            logging.error(f"Error getting LLM question: {e}")
        return None, None

    def get_database_question(self, question_type: str, rating: str = "PG13"):
        """Get a question from the database."""
        try:
            question_data = astra_db_ops.get_random_truth_dare_question(question_type, rating)
            if question_data:
                question = question_data.get("question", "")
                submitted_by = question_data.get("submitted_by", "Unknown")
                logging.debug(f"Database {question_type} response: {question}")
                return question, submitted_by, question_data.get("_id")
        except Exception as e:
            logging.error(f"Error getting database question: {e}")
        return None, None, None

    async def get_question(self, question_type: str, rating: str = "PG13"):
        """Get a question using the priority: API -> Database -> LLM with randomization."""
        # Add randomization: 70% API, 20% Database, 10% LLM
        rand = random.random()
        
        if rand < 0.7:
            # Try API first (70% chance)
            question, question_id = self.get_api_question(question_type, rating)
            if question:
                return question, "api", "API", question_type, rating, question_id
        
        if rand < 0.9:
            # Try database (20% chance)
            question_data = self.get_database_question(question_type, rating)
            if question_data and question_data[0]: # Check if question_data is not None and has a question
                question, submitted_by, question_id = question_data
                # Check if this is an AI-generated question by looking at the source
                is_ai_question = self.is_ai_generated_question(question_id)
                return question, "database", submitted_by, question_type, rating, question_id, is_ai_question
        
        # Fallback to LLM (10% chance or if others fail)
        question, creator_id = self.get_llm_question(question_type, rating)
        if question:
            # Store AI-generated question in database for future use
            question_id = self.save_ai_question(question, question_type, rating)
            return question, "llm", creator_id, question_type, rating, question_id, True
        
        # If all fail, try API as final fallback
        question, question_id = self.get_api_question(question_type, rating)
        if question:
            return question, "api", "API", question_type, rating, question_id, False
            
        return None, None, None, None, None, None, False

    def get_embed_color(self, question_type: str, rating: str):
        """Get appropriate embed color based on question type and rating."""
        if question_type == "truth":
            return 0x00ff00 if rating == "PG" else 0x00ff00 if rating == "PG13" else 0xff0000  # Green for PG, Light Red for PG13, Dark Red for R
        elif question_type == "dare":
            return 0xff6b6b if rating in ["PG", "PG13"] else 0xff0000  # Light Red for PG/PG13, Dark Red for R
        else:
            return 0x0099ff  # Blue for WYR, NHIE, and others

    def get_question_icon(self, question_type: str):
        """Get appropriate icon based on question type."""
        icon_map = {
            "truth": "🗣️",
            "dare": "⚡", 
            "wyr": "🤔",
            "nhie": "🙋",
            "paranoia": "👁️"
        }
        return icon_map.get(question_type, "🎯")

    def get_rating_icon(self, rating: str):
        """Get appropriate icon based on rating."""
        return "👨‍👩‍👧‍👦" if rating in ["PG", "PG13"] else "🔞"

    def save_ai_question(self, question: str, question_type: str, rating: str):
        """Save AI-generated question to database and return question ID."""
        try:
            # Save to database and get the actual database ID
            question_id = astra_db_ops.save_truth_dare_question(
                guild_id="global",  # AI questions are global
                user_id="ai_system",
                question=question,
                question_type=question_type,
                rating=rating,
                source="llm",
                submitted_by="AI"
            )
            
            if question_id:
                logging.debug(f"Saved AI question to database: {question_type} - {question[:50]}... with ID: {question_id}")
                return question_id
            else:
                logging.error("Failed to save AI question to database")
                return None
        except Exception as e:
            logging.error(f"Error saving AI question: {e}")
            return None

    def is_ai_generated_question(self, question_id: str):
        """Check if a question is AI-generated by looking at its source in the database."""
        try:
            if not question_id:
                return False
            question_data = astra_db_ops.get_truth_dare_question_by_id(question_id)
            if question_data:
                return question_data.get("source") == "llm"
            return False
        except Exception as e:
            logging.error(f"Error checking if question is AI-generated: {e}")
            return False

    @app_commands.command(name="tod", description="Start a Truth or Dare game")
    @app_commands.choices(action=[
        app_commands.Choice(name="Truth", value="truth"),
        app_commands.Choice(name="Dare", value="dare"),
        app_commands.Choice(name="Random", value="random"),
        app_commands.Choice(name="Would You Rather", value="wyr"),
        app_commands.Choice(name="Never Have I Ever", value="nhie"),
        app_commands.Choice(name="Paranoia", value="paranoia")
    ])
    @app_commands.choices(category=[
        app_commands.Choice(name="Family Friendly", value="PG13"),
        app_commands.Choice(name="Adult Only", value="R")
    ])
    async def slash_tod(self, interaction: discord.Interaction, action: str, category: str = "PG13"):
        """
        Start a Truth or Dare game with interactive buttons.
        
        Game Types: Truth, Dare, Random, Would You Rather, Never Have I Ever, Paranoia
        Rating: Family Friendly (PG13) or Adult Only (R)
        Buttons persist after bot restarts for continuous gameplay.
        """
        try:
            await interaction.response.defer()
            
            # Handle random action
            if action == "random":
                action = random.choice(["truth", "dare", "wyr", "nhie", "paranoia"])
            
            # Get question
            result = await self.get_question(action, category)
            if len(result) < 3:
                await interaction.followup.send("❌ Sorry, I couldn't generate a question right now. Try again later!")
                return
                
            question, source, creator, question_type, rating = result[:5]
            question_id = result[5] if len(result) > 5 else None
            is_ai_question = result[6] if len(result) > 6 else False
            
            if not question:
                await interaction.followup.send("❌ Sorry, I couldn't generate a question right now. Try again later!")
                return
            
            # Create clean embed
            embed = discord.Embed(
                description=f"### **{question}**",
                color=self.get_embed_color(question_type, rating)
            )
            embed.set_author(name=f"Requested by {interaction.user.display_name}")
            
            # Add metadata in footer
            embed.set_footer(text=f"Type: {question_type.upper()} | Rating: {rating} | ID: {question_id if question_id else 'N/A'}")
            
            # Create view with improved buttons
            view = TruthDareView(action, category, self, requested_type=action)
            
            message = await interaction.followup.send(embed=embed, view=view)
            
            # Add emoji reactions only for questions that need feedback
            if question_id and source != "api":  # Don't add reactions for TOD API questions
                await message.add_reaction("👍")
                await message.add_reaction("👎")
                # Save message metadata for reaction tracking
                astra_db_ops.add_message_metadata(question_id, str(message.id), str(interaction.guild_id), str(interaction.channel_id))
            
        except Exception as e:
            logging.error(f"Error in slash_tod: {e}")
            await interaction.followup.send("❌ An error occurred while getting your question.")

    @app_commands.command(name="tod-submit", description="Submit your own Truth or Dare question")
    @app_commands.choices(type=[
        app_commands.Choice(name="Truth", value="truth"),
        app_commands.Choice(name="Dare", value="dare"),
        app_commands.Choice(name="Would You Rather", value="wyr"),
        app_commands.Choice(name="Never Have I Ever", value="nhie")
    ])
    @app_commands.choices(rating=[
        app_commands.Choice(name="Family Friendly", value="PG13"),
        app_commands.Choice(name="Adult Only", value="R")
    ])
    async def slash_tod_submit(self, interaction: discord.Interaction, type: str, rating: str, question: str):
        """
        Submit your own Truth or Dare question to the community database.
        
        Args:
            type: Question type (Truth, Dare, Would You Rather, Never Have I Ever)
            rating: Family Friendly (PG13) or Adult Only (R)
            question: Your question (max 200 characters)
        """
        try:
            # Validate question length
            if len(question) > 200:
                await interaction.response.send_message("❌ Question is too long! Please keep it under 200 characters.", ephemeral=True)
                return
            
            # Save to database
            question_id = astra_db_ops.save_truth_dare_question(
                guild_id=str(interaction.guild.id),
                user_id=str(interaction.user.id),
                question=question,
                question_type=type,
                rating=rating,
                source="user",
                submitted_by=interaction.user.display_name
            )
            
            if question_id:
                await interaction.response.send_message(
                    f"✅ Thanks! Your {type} question has been submitted for review.\n"
                    f"**Question:** {question}\n"
                    f"**Rating:** {rating}",
                    ephemeral=True
                )
            else:
                await interaction.response.send_message("❌ Failed to submit your question. Please try again later.", ephemeral=True)
                
        except Exception as e:
            logging.error(f"Error in slash_tod_submit: {e}")
            await interaction.response.send_message("❌ An error occurred while submitting your question.", ephemeral=True)

class TruthDareView(discord.ui.View):
    def __init__(self, current_action: str, current_rating: str, cog_instance, requested_type=None):
        super().__init__(timeout=None)  # No timeout - buttons work indefinitely
        self.current_action = current_action
        self.current_rating = current_rating
        self.cog = cog_instance
        self.requested_type = requested_type
        
        # Add action buttons
        self.add_item(ActionButton("Truth", "truth", current_action, current_rating, cog_instance, requested_type))
        self.add_item(ActionButton("Dare", "dare", current_action, current_rating, cog_instance, requested_type))
        self.add_item(ActionButton("Random", "random", current_action, current_rating, cog_instance, requested_type))
        
        # Add contextual button if user specifically requested WYR/NHIE/Paranoia
        if requested_type in ["wyr", "nhie", "paranoia"]:
            self.add_item(ActionButton(requested_type.upper(), requested_type, current_action, current_rating, cog_instance, requested_type))

class ActionButton(discord.ui.Button):
    def __init__(self, label: str, action: str, current_action: str, current_rating: str, cog_instance, requested_type=None):
        # Use consistent colors for different actions
        style_map = {
            "truth": discord.ButtonStyle.success,      # Green
            "dare": discord.ButtonStyle.danger,        # Red
            "random": discord.ButtonStyle.primary,     # Blue
            "wyr": discord.ButtonStyle.primary,        # Blue
            "nhie": discord.ButtonStyle.primary,       # Blue
            "paranoia": discord.ButtonStyle.primary,   # Blue
        }
        
        # Get base style
        base_style = style_map.get(action, discord.ButtonStyle.primary)
        
        # If this is the current action, add an emoji prefix to indicate it's active
        if action == current_action:
            label = f"✓ {label}"  # Add checkmark to show it's the current action
        
        super().__init__(label=label, style=base_style)
        self.action = action
        self.current_action = current_action
        self.current_rating = current_rating
        self.cog = cog_instance
        self.requested_type = requested_type

    async def callback(self, interaction: discord.Interaction):
        try:
            # Immediately acknowledge the interaction to prevent timeout
            await interaction.response.defer()
            
            # Remove buttons from original message
            try:
                await interaction.edit_original_response(view=None)
            except:
                pass  # Ignore if original message can't be edited
            
            # Handle random action
            if self.action == "random":
                self.action = random.choice(["truth", "dare", "wyr", "nhie", "paranoia"])
            
            # Get question
            result = await self.cog.get_question(self.action, self.current_rating)
            if len(result) < 3:
                await interaction.followup.send("❌ Sorry, I couldn't generate a question right now. Try again later!")
                return
                
            question, source, creator, question_type, rating = result[:5]
            question_id = result[5] if len(result) > 5 else None
            is_ai_question = result[6] if len(result) > 6 else False
            
            if not question:
                await interaction.followup.send("❌ Sorry, I couldn't generate a question right now. Try again later!")
                return
            
            # Create clean embed
            embed = discord.Embed(
                description=f"### **{question}**",
                color=self.cog.get_embed_color(question_type, rating)
            )
            embed.set_author(name=f"Requested by {interaction.user.display_name}")
            
            # Add metadata in footer
            embed.set_footer(text=f"Type: {question_type.upper()} | Rating: {rating} | ID: {question_id if question_id else 'N/A'}")
            
            # Create new view
            view = TruthDareView(self.action, self.current_rating, self.cog, requested_type=self.requested_type)
            
            message = await interaction.followup.send(embed=embed, view=view)
            
            # Add emoji reactions only for questions that need feedback
            if question_id and source != "api":  # Don't add reactions for TOD API questions
                await message.add_reaction("👍")
                await message.add_reaction("👎")
                # Save message metadata for reaction tracking
                astra_db_ops.add_message_metadata(question_id, str(message.id), str(interaction.guild_id), str(interaction.channel_id))
            
        except Exception as e:
            logging.error(f"Error in ActionButton callback: {e}")
            # Try to send error message
            try:
                if not interaction.response.is_done():
                    await interaction.response.send_message("❌ An error occurred while getting your question.", ephemeral=True)
                else:
                    await interaction.followup.send("❌ An error occurred while getting your question.")
            except:
                pass  # Interaction might be expired

class FeedbackButton(discord.ui.Button):
    def __init__(self, question_id: str, feedback_type: str):
        if feedback_type == "positive":
            super().__init__(label="👍 Good", style=discord.ButtonStyle.success, custom_id=f"feedback_pos_{question_id}")
        else:
            super().__init__(label="👎 Bad", style=discord.ButtonStyle.danger, custom_id=f"feedback_neg_{question_id}")
        
        self.question_id = question_id
        self.feedback_type = feedback_type

    async def callback(self, interaction: discord.Interaction):
        try:
            # Record feedback
            success = astra_db_ops.record_question_feedback(self.question_id, self.feedback_type)
            
            if success:
                if self.feedback_type == "positive":
                    await interaction.response.send_message("✅ Thanks for the positive feedback! This question will be saved for future use.", ephemeral=True)
                else:
                    await interaction.response.send_message("✅ Thanks for the feedback! We'll use this to improve our AI.", ephemeral=True)
            else:
                await interaction.response.send_message("❌ Failed to record feedback. Please try again.", ephemeral=True)
                
        except Exception as e:
            logging.error(f"Error in FeedbackButton callback: {e}")
            # Try to send error message
            try:
                if not interaction.response.is_done():
                    await interaction.response.send_message("❌ An error occurred while recording feedback.", ephemeral=True)
                else:
                    await interaction.followup.send("❌ An error occurred while recording feedback.")
            except:
                pass  # Interaction might be expired

async def setup(bot):
    await bot.add_cog(TruthDareCog(bot))
