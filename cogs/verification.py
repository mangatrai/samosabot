"""
Verification Cog

This cog handles the verification system for new members in a Discord server.
It manages the verification process, including:
- Assigning guest roles to new members
- Sending verification challenges
- Processing verification responses
- Managing role changes
- Logging verification attempts
"""

import discord
from discord.ext import commands
from discord import app_commands
import logging
from typing import Dict, Set, List, Optional
from utils import astra_db_ops, openai_utils
import asyncio

class VerificationCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.active_verifications: Dict[int, Dict] = {}  # user_id -> verification data
        self.rules_messages: Dict[int, int] = {}  # guild_id -> message_id
        self.role_selections: Dict[int, Dict] = {}  # user_id -> selection data
        logging.info("VerificationCog initialized")

    async def cog_load(self):
        """Initialize the cog."""
        logging.info("Loading VerificationCog...")

    async def cog_unload(self):
        """Clean up when the cog is unloaded."""
        logging.info("Unloading VerificationCog...")

    def get_guild_settings(self, guild_id: int) -> dict:
        """Get verification settings for a guild."""
        return astra_db_ops.get_guild_verification_settings(guild_id)

    async def assign_guest_role(self, member: discord.Member):
        """Assign the Guest role to a new member."""
        try:
            settings = self.get_guild_settings(member.guild.id)
            if not settings["enabled"]:
                return

            guest_role = discord.utils.get(member.guild.roles, name=settings["guest_role_name"])
            if not guest_role:
                # Create the role if it doesn't exist
                guest_role = await member.guild.create_role(name=settings["guest_role_name"])
            
            await member.add_roles(guest_role)
            logging.info(f"Assigned Guest role to {member.name} ({member.id})")
            
            # Store verification attempt in AstraDB
            astra_db_ops.log_verification_attempt(
                user_id=member.id,
                username=member.name,
                guild_id=member.guild.id,
                stage="guest_role_assigned"
            )
        except Exception as e:
            logging.error(f"Error assigning Guest role to {member.name}: {e}")

    async def send_verification_challenge(self, member: discord.Member):
        """Send a verification challenge to the user."""
        try:
            # Generate verification questions using OpenAI
            questions = openai_utils.generate_openai_response("Generate 3 verification questions", intent="verification")
            
            # Create verification embed for the first question
            embed = discord.Embed(
                title="🔐 Verification Challenge",
                description=f"Welcome to {member.guild.name}! To verify you're human, please answer this question:\n\n"
                          f"**{questions[0]['question']}**\n\n"
                          f"Please type your answer in this channel.",
                color=discord.Color.blue()
            )
            
            # Send the challenge and store verification data
            channel = member.guild.system_channel or member.guild.text_channels[0]
            message = await channel.send(embed=embed)
            
            self.active_verifications[member.id] = {
                "questions": questions,
                "current_question": 0,
                "correct_answers": 0,
                "message_id": message.id,
                "attempts": 0
            }
            
            # Log verification start
            astra_db_ops.log_verification_attempt(
                user_id=member.id,
                username=member.name,
                guild_id=member.guild.id,
                stage="verification_started"
            )
        except Exception as e:
            logging.error(f"Error sending verification challenge to {member.name}: {e}")

    async def handle_verification_button(self, interaction: discord.Interaction):
        """Handle the verification button click."""
        try:
            if interaction.user.id not in self.active_verifications:
                await interaction.response.send_message(
                    "❌ No active verification session found.",
                    ephemeral=True
                )
                return

            verification_data = self.active_verifications[interaction.user.id]
            if verification_data["channel_id"] != interaction.channel_id:
                await interaction.response.send_message(
                    "❌ Please use your verification channel.",
                    ephemeral=True
                )
                return

            # Use existing questions instead of generating new ones
            questions = verification_data["questions"]
            
            # Update verification data
            verification_data.update({
                "current_question": 0,
                "correct_answers": 0,
                "stage": "answering"
            })

            # Create question embed
            embed = discord.Embed(
                title="🔐 Verification Question",
                description=(
                    f"Please answer this question:\n\n"
                    f"**{questions[0]['question']}**\n\n"
                    f"Type your answer in this channel."
                ),
                color=discord.Color.blue()
            )
            
            # Add progress footer
            embed.set_footer(text="Question 1/3")

            await interaction.response.edit_message(
                embed=embed,
                view=None  # Remove the button
            )

        except Exception as e:
            logging.error(f"Error handling verification button: {e}")
            await interaction.response.send_message(
                "❌ An error occurred. Please try again or contact an admin.",
                ephemeral=True
            )

    async def handle_verification_response(self, message: discord.Message):
        """Handle a user's response to the verification challenge."""
        try:
            user_id = message.author.id
            if user_id not in self.active_verifications:
                return

            verification_data = self.active_verifications[user_id]
            if verification_data["stage"] != "answering":
                return

            if verification_data["channel_id"] != message.channel.id:
                return

            verification_data["attempts"] += 1
            current_question = verification_data["questions"][verification_data["current_question"]]

            # Check if the answer is correct
            if message.content.lower() == current_question["answer"].lower():
                verification_data["correct_answers"] += 1
                
                # Move to next question or complete verification
                if verification_data["current_question"] < 2:
                    verification_data["current_question"] += 1
                    next_question = verification_data["questions"][verification_data["current_question"]]
                    
                    embed = discord.Embed(
                        title="🔐 Verification Question",
                        description=(
                            f"✅ Correct!\n\n"
                            f"Next question:\n"
                            f"**{next_question['question']}**\n\n"
                            f"Type your answer in this channel."
                        ),
                        color=discord.Color.blue()
                    )
                    embed.set_footer(text=f"Question {verification_data['current_question'] + 1}/3")
                    
                    await message.channel.send(embed=embed)
                else:
                    # All questions answered
                    await self.complete_verification(message)
            else:
                # Wrong answer
                if verification_data["attempts"] >= 3:
                    # Too many attempts
                    embed = discord.Embed(
                        title="❌ Verification Failed",
                        description=(
                            "You've exceeded the maximum number of attempts.\n"
                            "An admin has been notified and will review your case."
                        ),
                        color=discord.Color.red()
                    )
                    await message.channel.send(embed=embed)
                    
                    # Notify admins
                    settings = self.get_guild_settings(message.guild.id)
                    admin_channel = discord.utils.get(
                        message.guild.channels,
                        name=settings["admin_channel_name"]
                    )
                    if admin_channel:
                        await admin_channel.send(
                            f"⚠️ {message.author.mention} has failed verification after 3 attempts.\n"
                            f"Channel: {message.channel.mention}"
                        )
                    
                    # Update verification data
                    verification_data["stage"] = "failed"
                    
                    # Log failure
                    astra_db_ops.log_verification_attempt(
                        user_id=user_id,
                        username=message.author.name,
                        guild_id=message.guild.id,
                        stage="verification_failed",
                        success=False
                    )
                else:
                    # Still has attempts left
                    remaining = 3 - verification_data["attempts"]
                    await message.channel.send(
                        f"❌ Incorrect answer. You have {remaining} attempts remaining."
                    )

        except Exception as e:
            logging.error(f"Error handling verification response: {e}")
            await message.channel.send(
                "❌ An error occurred. Please try again or contact an admin."
            )

    async def complete_verification(self, message: discord.Message):
        """Handle completion of the verification questions."""
        try:
            verification_data = self.active_verifications[message.author.id]
            correct_answers = verification_data["correct_answers"]

            if correct_answers >= 2:
                # Get guild settings for role assignment
                settings = self.get_guild_settings(message.guild.id)
                
                # Assign Guest role first
                guest_role = discord.utils.get(message.guild.roles, name=settings["guest_role_name"])
                if guest_role:
                    await message.author.add_roles(guest_role)
                    logging.info(f"Assigned Guest role to {message.author.name} ({message.author.id})")
                else:
                    logging.error(f"Guest role {settings['guest_role_name']} not found in guild {message.guild.name}")
                
                # Update verification stage
                verification_data["stage"] = "rules"
                
                embed = discord.Embed(
                    title="✅ Verification Successful!",
                    description=(
                        "Congratulations! You've successfully completed the verification.\n\n"
                        "**Next Steps:**\n"
                        "1. Please read the server rules in #rules\n"
                        "2. Come back here and click the button below when you're done"
                    ),
                    color=discord.Color.green()
                )

                # Create button for rules acknowledgment
                view = discord.ui.View()
                rules_button = discord.ui.Button(
                    label="I've Read the Rules",
                    style=discord.ButtonStyle.primary,
                    custom_id="acknowledge_rules"
                )
                view.add_item(rules_button)

                await message.channel.send(embed=embed, view=view)
                
                # Log success
                astra_db_ops.log_verification_attempt(
                    user_id=message.author.id,
                    username=message.author.name,
                    guild_id=message.guild.id,
                    stage="verification_completed",
                    success=True
                )
            else:
                # Not enough correct answers
                embed = discord.Embed(
                    title="❌ Verification Failed",
                    description=(
                        f"You got {correct_answers}/3 questions correct.\n"
                        "A minimum of 2 correct answers is required.\n"
                        "An admin has been notified and will review your case."
                    ),
                    color=discord.Color.red()
                )
                await message.channel.send(embed=embed)
                
                # Notify admins
                settings = self.get_guild_settings(message.guild.id)
                admin_channel = discord.utils.get(
                    message.guild.channels,
                    name=settings["admin_channel_name"]
                )
                if admin_channel:
                    await admin_channel.send(
                        f"⚠️ {message.author.mention} failed verification with {correct_answers}/3 correct answers.\n"
                        f"Channel: {message.channel.mention}"
                    )
                
                # Update verification data
                verification_data["stage"] = "failed"
                
                # Log failure
                astra_db_ops.log_verification_attempt(
                    user_id=message.author.id,
                    username=message.author.name,
                    guild_id=message.guild.id,
                    stage="verification_failed",
                    success=False
                )

        except Exception as e:
            logging.error(f"Error completing verification: {e}")
            await message.channel.send(
                "❌ An error occurred. Please contact an admin for assistance."
            )

    @commands.Cog.listener()
    async def on_interaction(self, interaction: discord.Interaction):
        """Handle button interactions."""
        if not interaction.type == discord.InteractionType.component:
            return

        # Get the custom_id from the interaction data
        custom_id = interaction.data.get('custom_id')
        if not custom_id:
            return

        if custom_id == "start_verification":
            await self.handle_verification_button(interaction)
        elif custom_id == "acknowledge_rules":
            await self.handle_rules_acknowledgment(interaction)
        elif custom_id == "done_selecting_roles":
            await self.handle_role_selection_complete(interaction)
        elif custom_id.startswith(("approve_", "deny_")):
            await self.handle_admin_decision(interaction)

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        """Handle new member joins."""
        try:
            logging.debug(f"[DEBUG] Member joined: {member.name} (ID: {member.id}) in guild: {member.guild.name} (ID: {member.guild.id})")
            
            settings = self.get_guild_settings(member.guild.id)
            logging.debug(f"[DEBUG] Guild settings: {settings}")
            
            if not settings["enabled"]:
                logging.debug(f"[DEBUG] Verification is disabled for guild: {member.guild.name}")
                return

            logging.debug(f"[DEBUG] Creating verification channel for {member.name}")
            # Create temporary verification channel
            channel = await self.create_temp_verification_channel(member)
            logging.debug(f"[DEBUG] Created verification channel: {channel.name} (ID: {channel.id})")

            # Store verification state
            self.active_verifications[member.id] = {
                "channel_id": channel.id,
                "stage": "verification",
                "attempts": 0,
                "timestamp": discord.utils.utcnow().timestamp(),
                "selected_roles": set()
            }
            logging.debug(f"[DEBUG] Stored verification state for {member.name}")

            # Create welcome embed
            embed = discord.Embed(
                title=f"Welcome to {member.guild.name}!",
                description=(
                    f"Hi {member.mention}! Welcome to the server. "
                    "Before you can access the rest of the server, let's complete a quick verification process.\n\n"
                    "**Steps:**\n"
                    "1. Complete verification\n"
                    "2. Read the rules\n"
                    "3. Select your roles\n"
                    "4. Wait for admin approval\n\n"
                    "Click 'Start Verification' below to begin!"
                ),
                color=discord.Color.blue()
            )

            # Create verification button
            view = discord.ui.View()
            start_button = discord.ui.Button(
                label="Start Verification",
                style=discord.ButtonStyle.primary,
                custom_id="start_verification"
            )
            view.add_item(start_button)

            # Send welcome message
            logging.debug(f"[DEBUG] Sending welcome message to {member.name}")
            await channel.send(embed=embed, view=view)

            # Log verification start
            astra_db_ops.log_verification_attempt(
                user_id=member.id,
                username=member.name,
                guild_id=member.guild.id,
                stage="channel_created"
            )
            logging.debug(f"[DEBUG] Logged verification attempt for {member.name}")

        except Exception as e:
            logging.error(f"[ERROR] Error in on_member_join for {member.name}: {e}")
            # Try to send a DM to the user if channel creation failed
            try:
                await member.send("There was an error setting up your verification. Please contact a server admin.")
                logging.debug(f"[DEBUG] Sent error DM to {member.name}")
            except Exception as dm_error:
                logging.error(f"[ERROR] Failed to send DM to {member.name}: {dm_error}")

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        """Handle messages for verification responses."""
        if message.author.bot:
            return

        # Check if this is a verification response
        if message.author.id in self.active_verifications:
            await self.handle_verification_response(message)

    @commands.Cog.listener()
    async def on_reaction_add(self, reaction: discord.Reaction, user: discord.User):
        """Handle reactions for rules acknowledgment."""
        if user.bot:
            return

        # Check if this is a rules acknowledgment
        if (reaction.message.guild.id in self.rules_messages and 
            reaction.message.id == self.rules_messages[reaction.message.guild.id] and 
            str(reaction.emoji) == "✅"):
            
            member = reaction.message.guild.get_member(user.id)
            if not member:
                return

            # Check if user has Verified role
            settings = self.get_guild_settings(reaction.message.guild.id)
            verified_role = discord.utils.get(member.roles, name=settings["verified_role_name"])
            if not verified_role:
                return

            # Remove reaction to prevent spam
            await reaction.remove(user)

            # Log rules acknowledgment
            astra_db_ops.log_verification_attempt(
                user_id=user.id,
                username=user.name,
                guild_id=reaction.message.guild.id,
                stage="rules_acknowledged"
            )

            # Proceed to role selection
            await self.setup_role_selection(member)

    async def setup_role_selection(self, member: discord.Member):
        """Set up the role selection process for a verified user."""
        try:
            settings = self.get_guild_settings(member.guild.id)
            # Find or create roles channel
            roles_channel = discord.utils.get(member.guild.channels, name=settings["roles_channel_name"])
            if not roles_channel:
                roles_channel = await member.guild.create_text_channel(settings["roles_channel_name"])

            # Create role selection embed
            embed = discord.Embed(
                title="🎭 Role Selection",
                description="Select your roles by clicking the buttons below:",
                color=discord.Color.blue()
            )

            # Add available roles
            available_roles = [
                "Gamer", "Artist", "Music", "Tech", "Sports",
                "Movies", "Books", "Food", "Travel", "Science"
            ]

            # Create view with role buttons
            view = RoleSelectionView(self, member, roles_channel.id)

            # Send role selection message
            message = await roles_channel.send(embed=embed, view=view)
            
            # Store selection data
            self.role_selections[member.id] = {
                "message_id": message.id,
                "selected_roles": set(),
                "timestamp": discord.utils.utcnow()
            }

            # Log role selection setup
            astra_db_ops.log_verification_attempt(
                user_id=member.id,
                username=member.name,
                guild_id=member.guild.id,
                stage="role_selection_started"
            )
        except Exception as e:
            logging.error(f"Error setting up role selection for {member.name}: {e}")

    @app_commands.command(name="verification", description="Configure verification settings")
    @app_commands.describe(
        action="Action to perform (enable/disable/setup)",
        channel="Channel to use (for setup)",
        channel_type="Type of channel (rules/roles/admin)",
        role="Role to use (for setup)",
        role_type="Type of role (guest/verified/admin)"
    )
    @app_commands.choices(
        action=[
            app_commands.Choice(name="Enable", value="enable"),
            app_commands.Choice(name="Disable", value="disable"),
            app_commands.Choice(name="Setup", value="setup")
        ],
        channel_type=[
            app_commands.Choice(name="Rules", value="rules"),
            app_commands.Choice(name="Roles", value="roles"),
            app_commands.Choice(name="Admin", value="admin")
        ],
        role_type=[
            app_commands.Choice(name="Guest", value="guest"),
            app_commands.Choice(name="Verified", value="verified"),
            app_commands.Choice(name="Admin", value="admin")
        ]
    )
    async def verification_config(
        self,
        interaction: discord.Interaction,
        action: str,
        channel: discord.TextChannel = None,
        channel_type: str = None,
        role: discord.Role = None,
        role_type: str = None
    ):
        """Configure verification settings for the server."""
        try:
            if action == "enable":
                astra_db_ops.toggle_guild_verification(interaction.guild_id, True)
                await interaction.response.send_message("✅ Verification system enabled!", ephemeral=True)
            
            elif action == "disable":
                astra_db_ops.toggle_guild_verification(interaction.guild_id, False)
                await interaction.response.send_message("✅ Verification system disabled!", ephemeral=True)
            
            elif action == "setup":
                if not channel and not role:
                    await interaction.response.send_message(
                        "❌ Please provide either a channel or role to configure.",
                        ephemeral=True
                    )
                    return

                if channel and channel_type:
                    astra_db_ops.update_guild_channel_settings(
                        interaction.guild_id,
                        channel_type,
                        channel.name
                    )
                    await interaction.response.send_message(
                        f"✅ Set {channel_type} channel to {channel.mention}",
                        ephemeral=True
                    )
                
                elif role and role_type:
                    astra_db_ops.update_guild_role_settings(
                        interaction.guild_id,
                        role_type,
                        role.name
                    )
                    await interaction.response.send_message(
                        f"✅ Set {role_type} role to {role.mention}",
                        ephemeral=True
                    )
            
            else:
                await interaction.response.send_message(
                    "❌ Invalid action. Use 'enable', 'disable', or 'setup'.",
                    ephemeral=True
                )

        except Exception as e:
            logging.error(f"Error configuring verification: {e}")
            await interaction.response.send_message(
                "❌ An error occurred while configuring verification.",
                ephemeral=True
            )

    @app_commands.command(name="verification_status", description="Check verification settings")
    async def verification_status(self, interaction: discord.Interaction):
        """Check current verification settings for the server."""
        try:
            settings = self.get_guild_settings(interaction.guild_id)
            
            embed = discord.Embed(
                title="🔐 Verification Settings",
                color=discord.Color.blue()
            )
            
            # Add status
            status = "✅ Enabled" if settings["enabled"] else "❌ Disabled"
            embed.add_field(name="Status", value=status, inline=False)
            
            # Add roles
            roles_section = (
                f"👤 Guest Role: {settings['guest_role_name']}\n"
                f"✅ Verified Role: {settings['verified_role_name']}\n"
                f"👑 Admin Role: {settings['admin_role_name']}"
            )
            embed.add_field(name="Roles", value=roles_section, inline=False)
            
            # Add channels
            channels_section = (
                f"📜 Rules Channel: {settings['rules_channel_name']}\n"
                f"🎭 Roles Channel: {settings['roles_channel_name']}\n"
                f"⚠️ Admin Channel: {settings['admin_channel_name']}"
            )
            embed.add_field(name="Channels", value=channels_section, inline=False)
            
            await interaction.response.send_message(embed=embed, ephemeral=True)
            
        except Exception as e:
            logging.error(f"Error checking verification status: {e}")
            await interaction.response.send_message(
                "❌ An error occurred while checking verification status.",
                ephemeral=True
            )

    @app_commands.command(name="setup_wizard", description="Start the verification setup wizard")
    async def setup_wizard(self, interaction: discord.Interaction):
        """Start the verification setup wizard to configure the system step by step."""
        try:
            # Create initial embed
            embed = discord.Embed(
                title="🔐 Verification Setup Wizard",
                description=(
                    "Welcome to the verification setup wizard! This will guide you through "
                    "configuring the verification system step by step.\n\n"
                    "The setup will:\n"
                    "1. Create necessary roles (Guest, Verified)\n"
                    "2. Create required channels (Rules, Roles, Admin)\n"
                    "3. Enable the verification system\n\n"
                    "Click 'Start Setup' to begin!"
                ),
                color=discord.Color.blue()
            )

            # Create view with only the Start Setup button
            view = SetupWizardView(self, interaction)
            view.clear_items()  # Clear any existing buttons
            view.add_item(view.start_setup)  # Add only the Start Setup button

            await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

        except Exception as e:
            logging.error(f"Error starting setup wizard: {e}")
            await interaction.response.send_message(
                "❌ An error occurred while starting the setup wizard.",
                ephemeral=True
            )

    async def handle_rules_acknowledgment(self, interaction: discord.Interaction):
        """Handle when a user acknowledges reading the rules."""
        try:
            if interaction.user.id not in self.active_verifications:
                await interaction.response.send_message(
                    "❌ No active verification session found.",
                    ephemeral=True
                )
                return

            verification_data = self.active_verifications[interaction.user.id]
            if verification_data["channel_id"] != interaction.channel.id:
                await interaction.response.send_message(
                    "❌ Please use your verification channel.",
                    ephemeral=True
                )
                return

            if verification_data["stage"] != "rules":
                await interaction.response.send_message(
                    "❌ Please complete verification first.",
                    ephemeral=True
                )
                return

            # Update verification stage
            verification_data["stage"] = "roles"
            verification_data["rules_acknowledged"] = True
            verification_data["rules_timestamp"] = discord.utils.utcnow().timestamp()

            # Create roles selection embed
            embed = discord.Embed(
                title="🎭 Role Selection",
                description=(
                    "Great! Now let's select your roles.\n\n"
                    "1. Go to #roles channel\n"
                    "2. React to the roles you're interested in\n"
                    "3. Come back here and click 'Done Selecting Roles' when finished\n\n"
                    "**Note:** You can always change your roles later!"
                ),
                color=discord.Color.blue()
            )

            # Create button for completing role selection
            view = discord.ui.View()
            done_button = discord.ui.Button(
                label="Done Selecting Roles",
                style=discord.ButtonStyle.primary,
                custom_id="done_selecting_roles"
            )
            view.add_item(done_button)

            await interaction.response.edit_message(embed=embed, view=view)

            # Log rules acknowledgment
            astra_db_ops.log_verification_attempt(
                user_id=interaction.user.id,
                username=interaction.user.name,
                guild_id=interaction.guild_id,
                stage="rules_acknowledged"
            )

        except Exception as e:
            logging.error(f"Error handling rules acknowledgment: {e}")
            await interaction.response.send_message(
                "❌ An error occurred. Please try again or contact an admin.",
                ephemeral=True
            )

    async def handle_role_selection_complete(self, interaction: discord.Interaction):
        """Handle completion of role selection."""
        try:
            # Get guild settings
            settings = self.get_guild_settings(interaction.guild.id)
            
            # Get user's roles excluding @everyone and guest role
            guest_role_name = settings["guest_role_name"]
            user_roles = [
                role.name for role in interaction.user.roles 
                if role.name != "@everyone" and role.name != guest_role_name
            ]
            
            if not user_roles:
                await interaction.response.send_message(
                    "❌ Please select at least one role in the #roles channel before proceeding.",
                    ephemeral=True
                )
                return
            
            # Update verification state
            verification_data = self.active_verifications[interaction.user.id]
            verification_data["selected_roles"] = set(user_roles)
            verification_data["stage"] = "roles_selected"
            
            # Show selected roles in temp channel
            embed = discord.Embed(
                title="✅ Roles Selected!",
                description=(
                    "Great! You've selected the following roles:\n\n"
                    f"{', '.join(user_roles)}\n\n"
                    "An admin will review your verification shortly."
                ),
                color=discord.Color.green()
            )
            
            await interaction.response.edit_message(embed=embed, view=None)
            
            # Log role selection
            astra_db_ops.log_verification_attempt(
                user_id=interaction.user.id,
                username=interaction.user.name,
                guild_id=interaction.guild.id,
                stage="roles_selected",
                success=True
            )
            
            # Notify admins with approve/deny buttons
            admin_channel = discord.utils.get(
                interaction.guild.channels,
                name=settings["admin_channel_name"]
            )
            if admin_channel:
                review_embed = discord.Embed(
                    title="👋 New Member Review",
                    description=(
                        f"**User:** {interaction.user.mention}\n"
                        f"**Joined:** <t:{int(verification_data['timestamp'])}:R>\n"
                        f"**Rules Acknowledged:** <t:{int(verification_data['rules_timestamp'])}:R>\n"
                        f"**Selected Roles:**\n" + "\n".join(f"• {role}" for role in user_roles)
                    ),
                    color=discord.Color.blue()
                )

                # Create approve/deny buttons
                review_view = discord.ui.View()
                approve_button = discord.ui.Button(
                    label="Approve",
                    style=discord.ButtonStyle.success,
                    custom_id=f"approve_{interaction.user.id}"
                )
                deny_button = discord.ui.Button(
                    label="Deny",
                    style=discord.ButtonStyle.danger,
                    custom_id=f"deny_{interaction.user.id}"
                )
                review_view.add_item(approve_button)
                review_view.add_item(deny_button)

                await admin_channel.send(embed=review_embed, view=review_view)
                
                # Log awaiting approval
                astra_db_ops.log_verification_attempt(
                    user_id=interaction.user.id,
                    username=interaction.user.name,
                    guild_id=interaction.guild.id,
                    stage="awaiting_approval",
                    success=True
                )
            
        except Exception as e:
            logging.error(f"Error handling role selection completion: {e}")
            await interaction.response.send_message(
                "❌ An error occurred while processing your role selection.",
                ephemeral=True
            )

    async def handle_admin_decision(self, interaction: discord.Interaction):
        """Handle admin's approval or denial of a new member."""
        try:
            # Check if the user has admin permissions
            is_owner = interaction.user.id == interaction.guild.owner_id
            has_admin = interaction.user.guild_permissions.administrator
            
            if not (is_owner or has_admin):
                await interaction.response.send_message(
                    "❌ You need administrator permissions to use this command.",
                    ephemeral=True
                )
                return

            # Extract user ID and decision from custom_id
            custom_id = interaction.data.get('custom_id')
            if not custom_id:
                await interaction.response.send_message(
                    "❌ Invalid interaction data.",
                    ephemeral=True
                )
                return
                
            action, user_id = custom_id.split('_')
            user_id = int(user_id)
            
            if user_id not in self.active_verifications:
                await interaction.response.send_message(
                    "❌ Verification session not found.",
                    ephemeral=True
                )
                return

            verification_data = self.active_verifications[user_id]
            member = interaction.guild.get_member(user_id)
            
            if not member:
                await interaction.response.send_message(
                    "❌ Member not found. They may have left the server.",
                    ephemeral=True
                )
                del self.active_verifications[user_id]
                return

            # Acknowledge the interaction first
            await interaction.response.defer()

            # Get roles
            settings = self.get_guild_settings(interaction.guild_id)
            guest_role = discord.utils.get(
                interaction.guild.roles,
                name=settings["guest_role_name"]
            )

            if action == "approve":
                # Get verified role
                verified_role = discord.utils.get(
                    interaction.guild.roles,
                    name=settings["verified_role_name"]
                )

                # Apply roles
                if verified_role:
                    await member.add_roles(verified_role)
                if guest_role:
                    await member.remove_roles(guest_role)

                # Send approval message
                channel = interaction.guild.get_channel(verification_data["channel_id"])
                if channel:
                    embed = discord.Embed(
                        title="🎉 Welcome to the Server!",
                        description=(
                            "Your verification has been approved!\n"
                            "You now have access to the server.\n\n"
                            "This channel will be deleted in 60 seconds."
                        ),
                        color=discord.Color.green()
                    )
                    await channel.send(embed=embed)
                    
                    # Schedule channel deletion
                    await asyncio.sleep(60)
                    await channel.delete()

                # Log approval
                astra_db_ops.log_verification_attempt(
                    user_id=user_id,
                    username=member.name,
                    guild_id=interaction.guild_id,
                    stage="approved",
                    success=True
                )

            else:  # deny
                # Remove guest role
                if guest_role:
                    await member.remove_roles(guest_role)

                # Send denial message to verification channel
                channel = interaction.guild.get_channel(verification_data["channel_id"])
                if channel:
                    embed = discord.Embed(
                        title="❌ Verification Denied",
                        description=(
                            "Your verification has been denied by an administrator.\n"
                            "Please contact the server staff for more information."
                        ),
                        color=discord.Color.red()
                    )
                    await channel.send(embed=embed)
                    
                    # Schedule channel deletion
                    await asyncio.sleep(60)
                    await channel.delete()

                # Send DM to user
                try:
                    await member.send(
                        "❌ Your verification request has been denied by an administrator.\n"
                        "Please contact the server staff for more information."
                    )
                except Exception as dm_error:
                    logging.error(f"Failed to send denial DM to {member.name}: {dm_error}")

                # Log denial
                astra_db_ops.log_verification_attempt(
                    user_id=user_id,
                    username=member.name,
                    guild_id=interaction.guild_id,
                    stage="denied",
                    success=False
                )

            # Clean up
            del self.active_verifications[user_id]
            await interaction.message.delete()

        except Exception as e:
            logging.error(f"Error handling admin decision: {e}")
            if not interaction.response.is_done():
                await interaction.response.send_message(
                    "❌ An error occurred while processing the decision.",
                    ephemeral=True
                )

    async def create_temp_verification_channel(self, member: discord.Member) -> discord.TextChannel:
        """Create a temporary verification channel for a new member."""
        try:
            # Get or create the verification category
            category = discord.utils.get(member.guild.categories, name="Verification")
            if not category:
                category = await member.guild.create_category("Verification")

            # Create base overwrites denying access to everyone
            overwrites = {
                member.guild.default_role: discord.PermissionOverwrite(read_messages=False),
                member.guild.me: discord.PermissionOverwrite(
                    read_messages=True,
                    send_messages=True,
                    manage_channels=True,
                    read_message_history=True,
                    view_channel=True,
                    embed_links=True,
                    add_reactions=True
                )
            }

            # Deny access to all roles
            for role in member.guild.roles:
                if not role.is_default():
                    overwrites[role] = discord.PermissionOverwrite(read_messages=False)

            # Allow access to the specific member with all necessary permissions
            overwrites[member] = discord.PermissionOverwrite(
                read_messages=True,
                send_messages=True,
                read_message_history=True,
                view_channel=True,
                embed_links=True,
                add_reactions=True
            )

            # Create the channel
            try:
                channel = await member.guild.create_text_channel(
                    name=f"verify-{member.name}",
                    category=category,
                    overwrites=overwrites
                )
            except Exception as e:
                logging.error(f"[ERROR] Failed to create channel: {e}")
                logging.error(f"[ERROR] Bot permissions: {member.guild.me.guild_permissions}")
                raise

            # Set channel to be deleted after 24 hours
            await channel.edit(topic="This channel will be deleted after 24 hours of inactivity.")
            
            return channel

        except Exception as e:
            logging.error(f"[ERROR] Channel creation failed: {e}")
            raise

class RoleSelectionView(discord.ui.View):
    def __init__(self, cog, member: discord.Member, roles_channel_id: int):
        super().__init__(timeout=300)
        self.cog = cog
        self.member = member
        self.roles_channel_id = roles_channel_id
        
        # Add done button
        done_button = discord.ui.Button(
            label="Done Selecting Roles",
            style=discord.ButtonStyle.primary,
            custom_id="done_selecting_roles"
        )
        done_button.callback = self.cog.handle_role_selection_complete
        self.add_item(done_button)

    async def handle_role_selection_complete(self, interaction: discord.Interaction):
        """Handle completion of role selection."""
        try:
            # Get guild settings
            settings = self.cog.get_guild_settings(interaction.guild.id)
            
            # Get user's roles excluding @everyone and guest role
            guest_role_name = settings["guest_role_name"]
            user_roles = [
                role.name for role in interaction.user.roles 
                if role.name != "@everyone" and role.name != guest_role_name
            ]
            
            if not user_roles:
                await interaction.response.send_message(
                    "❌ Please select at least one role in the #roles channel before proceeding.",
                    ephemeral=True
                )
                return
            
            # Update verification state
            verification_data = self.cog.active_verifications[interaction.user.id]
            verification_data["selected_roles"] = set(user_roles)
            verification_data["stage"] = "roles_selected"
            
            # Show selected roles in temp channel
            embed = discord.Embed(
                title="✅ Roles Selected!",
                description=(
                    "Great! You've selected the following roles:\n\n"
                    f"{', '.join(user_roles)}\n\n"
                    "An admin will review your verification shortly."
                ),
                color=discord.Color.green()
            )
            
            await interaction.response.edit_message(embed=embed, view=None)
            
            # Log role selection
            astra_db_ops.log_verification_attempt(
                user_id=interaction.user.id,
                username=interaction.user.name,
                guild_id=interaction.guild.id,
                stage="roles_selected",
                success=True
            )
            
            # Notify admins with approve/deny buttons
            admin_channel = discord.utils.get(
                interaction.guild.channels,
                name=settings["admin_channel_name"]
            )
            if admin_channel:
                review_embed = discord.Embed(
                    title="👋 New Member Review",
                    description=(
                        f"**User:** {interaction.user.mention}\n"
                        f"**Joined:** <t:{int(verification_data['timestamp'])}:R>\n"
                        f"**Rules Acknowledged:** <t:{int(verification_data['rules_timestamp'])}:R>\n"
                        f"**Selected Roles:**\n" + "\n".join(f"• {role}" for role in user_roles)
                    ),
                    color=discord.Color.blue()
                )

                # Create approve/deny buttons
                review_view = discord.ui.View()
                approve_button = discord.ui.Button(
                    label="Approve",
                    style=discord.ButtonStyle.success,
                    custom_id=f"approve_{interaction.user.id}"
                )
                deny_button = discord.ui.Button(
                    label="Deny",
                    style=discord.ButtonStyle.danger,
                    custom_id=f"deny_{interaction.user.id}"
                )
                review_view.add_item(approve_button)
                review_view.add_item(deny_button)

                await admin_channel.send(embed=review_embed, view=review_view)
                
                # Log awaiting approval
                astra_db_ops.log_verification_attempt(
                    user_id=interaction.user.id,
                    username=interaction.user.name,
                    guild_id=interaction.guild.id,
                    stage="awaiting_approval",
                    success=True
                )
            
        except Exception as e:
            logging.error(f"Error handling role selection: {e}")
            await interaction.response.send_message(
                "❌ An error occurred. Please try again or contact an admin.",
                ephemeral=True
            )

class SetupWizardView(discord.ui.View):
    def __init__(self, cog, interaction: discord.Interaction):
        super().__init__(timeout=None)
        self.cog = cog
        self.interaction = interaction
        self.current_step = 0
        self.settings = {}
        self.selection_active = False
        self.current_select = None

    def is_admin(self, interaction: discord.Interaction) -> bool:
        """Check if the user has administrator permissions."""
        try:
            # For slash commands, interaction.user is already a Member object in guild context
            # and has guild_permissions attribute
            is_owner = interaction.user.id == interaction.guild.owner_id
            has_admin = interaction.user.guild_permissions.administrator
            
            logging.info(f"Permission check for {interaction.user.name} in {interaction.guild.name}: is_owner={is_owner}, has_admin={has_admin}")
            return is_owner or has_admin
            
        except Exception as e:
            logging.error(f"Error checking permissions for {interaction.user.name}: {e}")
            return False

    def get_guild_settings(self, guild_id: int) -> dict:
        """Get verification settings for a guild."""
        return self.cog.get_guild_settings(guild_id)

    @discord.ui.button(label="Start Setup", style=discord.ButtonStyle.primary)
    async def start_setup(self, interaction: discord.Interaction, button: discord.ui.Button):
        logging.info(f"Start Setup clicked by {interaction.user.name} (ID: {interaction.user.id})")
        if not self.is_admin(interaction):
            logging.error(f"Permission denied for {interaction.user.name}")
            await interaction.response.send_message(
                "❌ You need administrator permissions to use this command.",
                ephemeral=True
            )
            return

        self.current_step = 1
        button.disabled = True
        await interaction.response.edit_message(view=self)
        await self.show_current_step()

    @discord.ui.button(label="Next", style=discord.ButtonStyle.success)
    async def next_step(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self.is_admin(interaction):
            await interaction.response.send_message(
                "❌ You need administrator permissions to use this command.",
                ephemeral=True
            )
            return

        if self.current_step == 0:
            await interaction.response.send_message(
                "❌ Please click 'Start Setup' first.",
                ephemeral=True
            )
            return

        # Check if current step is completed
        if not self.is_step_completed(self.current_step):
            await interaction.response.send_message(
                "❌ Please complete the current step before proceeding.",
                ephemeral=True
            )
            return

        if self.current_step < 7:  # Total number of steps
            self.current_step += 1
            await interaction.response.edit_message(view=self)
            await self.show_current_step()
        else:
            await self.complete_setup(interaction)

    @discord.ui.button(label="Back", style=discord.ButtonStyle.secondary)
    async def back_step(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self.is_admin(interaction):
            await interaction.response.send_message(
                "❌ You need administrator permissions to use this command.",
                ephemeral=True
            )
            return

        if self.current_step == 0:
            await interaction.response.send_message(
                "❌ Please click 'Start Setup' first.",
                ephemeral=True
            )
            return

        if self.current_step > 1:
            self.current_step -= 1
            await interaction.response.edit_message(view=self)
            await self.show_current_step()

    async def show_current_step(self):
        embed = discord.Embed(
            title="🔐 Verification Setup Wizard",
            description="Let's set up the verification system step by step!",
            color=discord.Color.blue()
        )

        # Clear all existing buttons first
        self.clear_items()

        # Add current settings summary if any exist
        if self.settings:
            settings_summary = "**Current Settings:**\n"
            if "guest_role_name" in self.settings:
                settings_summary += f"👤 Guest Role: {self.settings['guest_role_name']}\n"
            if "verified_role_name" in self.settings:
                settings_summary += f"✅ Verified Role: {self.settings['verified_role_name']}\n"
            if "admin_role_name" in self.settings:
                settings_summary += f"👑 Admin Role: {self.settings['admin_role_name']}\n"
            if "rules_channel_name" in self.settings:
                settings_summary += f"📜 Rules Channel: {self.settings['rules_channel_name']}\n"
            if "roles_channel_name" in self.settings:
                settings_summary += f"🎭 Roles Channel: {self.settings['roles_channel_name']}\n"
            if "admin_channel_name" in self.settings:
                settings_summary += f"⚠️ Admin Channel: {self.settings['admin_channel_name']}\n"
            embed.add_field(name="Current Configuration", value=settings_summary, inline=False)

        if not self.selection_active:
            if self.current_step == 0:
                embed.description = (
                    "Welcome to the verification setup wizard! This will guide you through "
                    "configuring the verification system step by step.\n\n"
                    "The setup will:\n"
                    "1. Create necessary roles (Guest, Verified)\n"
                    "2. Create required channels (Rules, Roles, Admin)\n"
                    "3. Enable the verification system\n\n"
                    "Click 'Start Setup' to begin!"
                )
                self.add_item(self.start_setup)
            elif self.current_step == 1:
                embed.description = (
                    "**Step 1: Guest Role Setup**\n\n"
                    "First, let's set up the Guest role that new members will receive.\n"
                    "You can either:\n"
                    "1. Select an existing role\n"
                    "2. Create a new role"
                )
                self.add_item(self.select_guest_role)
                self.add_item(self.create_guest_role)
                self.add_item(self.next_step)
            elif self.current_step == 2:
                embed.description = (
                    "**Step 2: Verified Role Setup**\n\n"
                    "Next, let's set up the Verified role that members will receive after verification.\n"
                    "You can either:\n"
                    "1. Select an existing role\n"
                    "2. Create a new role"
                )
                self.add_item(self.select_verified_role)
                self.add_item(self.create_verified_role)
                self.add_item(self.back_step)
                self.add_item(self.next_step)
            elif self.current_step == 3:
                embed.description = (
                    "**Step 3: Admin Role Setup**\n\n"
                    "Now, let's set up the Admin role that will be used for verification approvals.\n"
                    "You can either:\n"
                    "1. Select an existing role\n"
                    "2. Create a new role"
                )
                self.add_item(self.select_admin_role)
                self.add_item(self.create_admin_role)
                self.add_item(self.back_step)
                self.add_item(self.next_step)
            elif self.current_step == 4:
                embed.description = (
                    "**Step 4: Rules Channel Setup**\n\n"
                    "Let's set up the channel for server rules.\n"
                    "You can either:\n"
                    "1. Select an existing channel\n"
                    "2. Create a new channel"
                )
                self.add_item(self.select_rules_channel)
                self.add_item(self.create_rules_channel)
                self.add_item(self.back_step)
                self.add_item(self.next_step)
            elif self.current_step == 5:
                embed.description = (
                    "**Step 5: Roles Channel Setup**\n\n"
                    "Now, let's set up the channel for role selection.\n"
                    "You can either:\n"
                    "1. Select an existing channel\n"
                    "2. Create a new channel"
                )
                self.add_item(self.select_roles_channel)
                self.add_item(self.create_roles_channel)
                self.add_item(self.back_step)
                self.add_item(self.next_step)
            elif self.current_step == 6:
                embed.description = (
                    "**Step 6: Admin Channel Setup**\n\n"
                    "Let's set up the channel for admin approvals.\n"
                    "You can either:\n"
                    "1. Select an existing channel\n"
                    "2. Create a new channel"
                )
                self.add_item(self.select_admin_channel)
                self.add_item(self.create_admin_channel)
                self.add_item(self.back_step)
                self.add_item(self.next_step)
            elif self.current_step == 7:
                embed.description = (
                    "**Step 7: Review and Enable**\n\n"
                    "Please review your settings below. If everything looks correct, "
                    "click 'Enable Verification' to complete the setup."
                )
                self.add_item(self.enable_verification)
                self.add_item(self.back_step)

        await self.interaction.edit_original_response(embed=embed, view=self)

    @discord.ui.button(label="Select Guest Role", style=discord.ButtonStyle.primary)
    async def select_guest_role(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self.is_admin(interaction):
            await interaction.response.send_message(
                "❌ You need administrator permissions to use this command.",
                ephemeral=True
            )
            return

        # Get available roles
        available_roles = [
            role for role in interaction.guild.roles
            if len(role.name) <= 25 and not role.is_default()
        ]

        if not available_roles:
            await interaction.response.send_message(
                "❌ No roles available. Please create a role first.",
                ephemeral=True
            )
            return

        # Create select menu
        select = discord.ui.Select(
            placeholder="Choose an existing Guest role",
            options=[
                discord.SelectOption(
                    label=role.name,
                    value=str(role.id),
                    description=f"Select {role.name} as Guest role"
                )
                for role in available_roles
            ]
        )
        select.callback = self.handle_guest_role_selection

        # Update view with select menu
        self.clear_items()
        self.add_item(select)
        self.selection_active = True
        self.current_select = "guest_role"

        # Add a cancel button
        cancel_button = discord.ui.Button(label="Cancel", style=discord.ButtonStyle.secondary)
        cancel_button.callback = self.cancel_selection
        self.add_item(cancel_button)

        await interaction.response.edit_message(view=self)

    async def handle_guest_role_selection(self, interaction: discord.Interaction):
        if not self.is_admin(interaction):
            await interaction.response.send_message(
                "❌ You need administrator permissions to use this command.",
                ephemeral=True
            )
            return

        role_id = int(interaction.data["values"][0])
        role = interaction.guild.get_role(role_id)
        if role:
            self.settings["guest_role_name"] = role.name
            self.selection_active = False
            self.current_select = None
            await self.show_current_step()
            await interaction.response.edit_message(view=self)
        else:
            await interaction.response.send_message("❌ Selected role not found.", ephemeral=True)

    async def cancel_selection(self, interaction: discord.Interaction):
        if not self.is_admin(interaction):
            await interaction.response.send_message(
                "❌ You need administrator permissions to use this command.",
                ephemeral=True
            )
            return

        self.selection_active = False
        self.current_select = None
        await self.show_current_step()
        await interaction.response.edit_message(view=self)

    @discord.ui.button(label="Select Verified Role", style=discord.ButtonStyle.primary)
    async def select_verified_role(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self.is_admin(interaction):
            await interaction.response.send_message(
                "❌ You need administrator permissions to use this command.",
                ephemeral=True
            )
            return

        # Get available roles
        available_roles = [
            role for role in interaction.guild.roles
            if len(role.name) <= 25 and not role.is_default()
        ]

        if not available_roles:
            await interaction.response.send_message(
                "❌ No roles available. Please create a role first.",
                ephemeral=True
            )
            return

        select = discord.ui.Select(
            placeholder="Choose an existing Verified role",
            options=[
                discord.SelectOption(
                    label=role.name,
                    value=str(role.id),
                    description=f"Select {role.name} as Verified role"
                )
                for role in available_roles
            ]
        )
        select.callback = self.handle_verified_role_selection
        
        # Update view with select menu
        self.clear_items()
        self.add_item(select)
        self.selection_active = True
        self.current_select = "verified_role"

        # Add a cancel button
        cancel_button = discord.ui.Button(label="Cancel", style=discord.ButtonStyle.secondary)
        cancel_button.callback = self.cancel_selection
        self.add_item(cancel_button)
        
        await interaction.response.edit_message(view=self)

    async def handle_verified_role_selection(self, interaction: discord.Interaction):
        if not self.is_admin(interaction):
            await interaction.response.send_message(
                "❌ You need administrator permissions to use this command.",
                ephemeral=True
            )
            return

        role_id = int(interaction.data["values"][0])
        role = interaction.guild.get_role(role_id)
        if role:
            self.settings["verified_role_name"] = role.name
            self.selection_active = False
            self.current_select = None
            await self.show_current_step()
            await interaction.response.edit_message(view=self)
        else:
            await interaction.response.send_message("❌ Selected role not found.", ephemeral=True)

    @discord.ui.button(label="Select Rules Channel", style=discord.ButtonStyle.primary)
    async def select_rules_channel(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self.is_admin(interaction):
            await interaction.response.send_message(
                "❌ You need administrator permissions to use this command.",
                ephemeral=True
            )
            return

        # Get all text channels from the guild
        text_channels = [channel for channel in interaction.guild.channels if isinstance(channel, discord.TextChannel)]
        
        if not text_channels:
            await interaction.response.send_message(
                "❌ No text channels available. Please create a channel first.",
                ephemeral=True
            )
            return

        select = discord.ui.Select(
            placeholder="Choose an existing rules channel",
            options=[
                discord.SelectOption(
                    label=channel.name,
                    value=str(channel.id),
                    description=f"Select {channel.name} as rules channel"
                )
                for channel in text_channels[:25]  # Discord limits to 25 options
            ]
        )
        select.callback = self.handle_rules_channel_selection
        
        # Update view with select menu
        self.clear_items()
        self.add_item(select)
        self.selection_active = True
        self.current_select = "rules_channel"

        # Add a cancel button
        cancel_button = discord.ui.Button(label="Cancel", style=discord.ButtonStyle.secondary)
        cancel_button.callback = self.cancel_selection
        self.add_item(cancel_button)
        
        await interaction.response.edit_message(view=self)

    async def handle_rules_channel_selection(self, interaction: discord.Interaction):
        if not self.is_admin(interaction):
            await interaction.response.send_message(
                "❌ You need administrator permissions to use this command.",
                ephemeral=True
            )
            return

        channel_id = int(interaction.data["values"][0])
        channel = interaction.guild.get_channel(channel_id)
        if channel:
            self.settings["rules_channel_name"] = channel.name
            self.selection_active = False
            self.current_select = None
            await self.show_current_step()
            await interaction.response.edit_message(view=self)
        else:
            await interaction.response.send_message("❌ Selected channel not found.", ephemeral=True)

    @discord.ui.button(label="Select Roles Channel", style=discord.ButtonStyle.primary)
    async def select_roles_channel(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self.is_admin(interaction):
            await interaction.response.send_message(
                "❌ You need administrator permissions to use this command.",
                ephemeral=True
            )
            return

        # Get all text channels from the guild
        text_channels = [channel for channel in interaction.guild.channels if isinstance(channel, discord.TextChannel)]
        
        if not text_channels:
            await interaction.response.send_message(
                "❌ No text channels available. Please create a channel first.",
                ephemeral=True
            )
            return

        select = discord.ui.Select(
            placeholder="Choose an existing roles channel",
            options=[
                discord.SelectOption(
                    label=channel.name,
                    value=str(channel.id),
                    description=f"Select {channel.name} as roles channel"
                )
                for channel in text_channels[:25]  # Discord limits to 25 options
            ]
        )
        select.callback = self.handle_roles_channel_selection
        
        # Update view with select menu
        self.clear_items()
        self.add_item(select)
        self.selection_active = True
        self.current_select = "roles_channel"

        # Add a cancel button
        cancel_button = discord.ui.Button(label="Cancel", style=discord.ButtonStyle.secondary)
        cancel_button.callback = self.cancel_selection
        self.add_item(cancel_button)
        
        await interaction.response.edit_message(view=self)

    async def handle_roles_channel_selection(self, interaction: discord.Interaction):
        if not self.is_admin(interaction):
            await interaction.response.send_message(
                "❌ You need administrator permissions to use this command.",
                ephemeral=True
            )
            return

        channel_id = int(interaction.data["values"][0])
        channel = interaction.guild.get_channel(channel_id)
        if channel:
            self.settings["roles_channel_name"] = channel.name
            self.selection_active = False
            self.current_select = None
            await self.show_current_step()
            await interaction.response.edit_message(view=self)
        else:
            await interaction.response.send_message("❌ Selected channel not found.", ephemeral=True)

    @discord.ui.button(label="Select Admin Channel", style=discord.ButtonStyle.primary)
    async def select_admin_channel(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self.is_admin(interaction):
            await interaction.response.send_message(
                "❌ You need administrator permissions to use this command.",
                ephemeral=True
            )
            return

        # Get all text channels from the guild
        text_channels = [channel for channel in interaction.guild.channels if isinstance(channel, discord.TextChannel)]
        
        if not text_channels:
            await interaction.response.send_message(
                "❌ No text channels available. Please create a channel first.",
                ephemeral=True
            )
            return

        select = discord.ui.Select(
            placeholder="Choose an existing admin channel",
            options=[
                discord.SelectOption(
                    label=channel.name,
                    value=str(channel.id),
                    description=f"Select {channel.name} as admin channel"
                )
                for channel in text_channels[:25]  # Discord limits to 25 options
            ]
        )
        select.callback = self.handle_admin_channel_selection
        
        # Update view with select menu
        self.clear_items()
        self.add_item(select)
        self.selection_active = True
        self.current_select = "admin_channel"

        # Add a cancel button
        cancel_button = discord.ui.Button(label="Cancel", style=discord.ButtonStyle.secondary)
        cancel_button.callback = self.cancel_selection
        self.add_item(cancel_button)
        
        await interaction.response.edit_message(view=self)

    async def handle_admin_channel_selection(self, interaction: discord.Interaction):
        if not self.is_admin(interaction):
            await interaction.response.send_message(
                "❌ You need administrator permissions to use this command.",
                ephemeral=True
            )
            return

        channel_id = int(interaction.data["values"][0])
        channel = interaction.guild.get_channel(channel_id)
        if channel:
            self.settings["admin_channel_name"] = channel.name
            self.selection_active = False
            self.current_select = None
            await self.show_current_step()
            await interaction.response.edit_message(view=self)
        else:
            await interaction.response.send_message("❌ Selected channel not found.", ephemeral=True)

    @discord.ui.button(label="Create Guest Role", style=discord.ButtonStyle.primary)
    async def create_guest_role(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self.is_admin(interaction):
            await interaction.response.send_message(
                "❌ You need administrator permissions to use this command.",
                ephemeral=True
            )
            return

        try:
            settings = self.get_guild_settings(interaction.guild_id)
            role = await interaction.guild.create_role(name=settings["guest_role_name"])
            self.settings["guest_role_name"] = role.name
            await interaction.response.send_message(f"✅ Created Guest role: {role.mention}", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"❌ Error creating Guest role: {e}", ephemeral=True)

    @discord.ui.button(label="Create Verified Role", style=discord.ButtonStyle.primary)
    async def create_verified_role(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self.is_admin(interaction):
            await interaction.response.send_message(
                "❌ You need administrator permissions to use this command.",
                ephemeral=True
            )
            return

        try:
            settings = self.get_guild_settings(interaction.guild_id)
            role = await interaction.guild.create_role(name=settings["verified_role_name"])
            self.settings["verified_role_name"] = role.name
            await interaction.response.send_message(f"✅ Created Verified role: {role.mention}", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"❌ Error creating Verified role: {e}", ephemeral=True)

    @discord.ui.button(label="Create Rules Channel", style=discord.ButtonStyle.primary)
    async def create_rules_channel(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self.is_admin(interaction):
            await interaction.response.send_message(
                "❌ You need administrator permissions to use this command.",
                ephemeral=True
            )
            return

        try:
            settings = self.get_guild_settings(interaction.guild_id)
            channel = await interaction.guild.create_text_channel(settings["rules_channel_name"])
            self.settings["rules_channel_name"] = channel.name
            await interaction.response.send_message(f"✅ Created rules channel: {channel.mention}", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"❌ Error creating rules channel: {e}", ephemeral=True)

    @discord.ui.button(label="Create Roles Channel", style=discord.ButtonStyle.primary)
    async def create_roles_channel(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self.is_admin(interaction):
            await interaction.response.send_message(
                "❌ You need administrator permissions to use this command.",
                ephemeral=True
            )
            return

        try:
            settings = self.get_guild_settings(interaction.guild_id)
            channel = await interaction.guild.create_text_channel(settings["roles_channel_name"])
            self.settings["roles_channel_name"] = channel.name
            await self.show_current_step()
            await interaction.response.send_message(f"✅ Created roles channel: {channel.mention}", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"❌ Error creating roles channel: {e}", ephemeral=True)

    @discord.ui.button(label="Create Admin Channel", style=discord.ButtonStyle.primary)
    async def create_admin_channel(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self.is_admin(interaction):
            await interaction.response.send_message(
                "❌ You need administrator permissions to use this command.",
                ephemeral=True
            )
            return

        try:
            settings = self.get_guild_settings(interaction.guild_id)
            channel = await interaction.guild.create_text_channel(settings["admin_channel_name"])
            self.settings["admin_channel_name"] = channel.name
            await self.show_current_step()
            await interaction.response.send_message(f"✅ Created admin channel: {channel.mention}", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"❌ Error creating admin channel: {e}", ephemeral=True)

    @discord.ui.button(label="Enable Verification", style=discord.ButtonStyle.primary)
    async def enable_verification(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self.is_admin(interaction):
            await interaction.response.send_message(
                "❌ You need administrator permissions to use this command.",
                ephemeral=True
            )
            return

        try:
            # First save all settings to the database
            astra_db_ops.update_guild_verification_settings(interaction.guild_id, self.settings)
            
            # Then enable verification
            astra_db_ops.toggle_guild_verification(interaction.guild_id, True)
            
            # Create completion embed
            embed = discord.Embed(
                title="✅ Setup Complete!",
                description="The verification system has been configured successfully.",
                color=discord.Color.green()
            )
            
            # Add summary of settings
            settings_summary = (
                f"👤 Guest Role: {self.settings.get('guest_role_name', 'Guest')}\n"
                f"✅ Verified Role: {self.settings.get('verified_role_name', 'Verified')}\n"
                f"👑 Admin Role: {self.settings.get('admin_role_name', 'Staff')}\n"
                f"📜 Rules Channel: {self.settings.get('rules_channel_name', 'rules')}\n"
                f"🎭 Roles Channel: {self.settings.get('roles_channel_name', 'roles')}\n"
                f"⚠️ Admin Channel: {self.settings.get('admin_channel_name', 'admin')}"
            )
            embed.add_field(name="Configuration Summary", value=settings_summary, inline=False)
            
            # Clear all buttons
            self.clear_items()
            
            await interaction.response.edit_message(embed=embed, view=self)
            
        except Exception as e:
            await interaction.response.send_message(f"❌ Error completing setup: {e}", ephemeral=True)

    def is_step_completed(self, step: int) -> bool:
        """Check if the current step has been completed."""
        if step == 1:  # Guest Role
            return "guest_role_name" in self.settings
        elif step == 2:  # Verified Role
            return "verified_role_name" in self.settings
        elif step == 3:  # Admin Role
            return "admin_role_name" in self.settings
        elif step == 4:  # Rules Channel
            return "rules_channel_name" in self.settings
        elif step == 5:  # Roles Channel
            return "roles_channel_name" in self.settings
        elif step == 6:  # Admin Channel
            return "admin_channel_name" in self.settings
        elif step == 7:  # Enable Verification
            return True  # This step is completed by clicking the button
        return False

    async def complete_setup(self, interaction: discord.Interaction):
        try:
            # Save all settings to database
            astra_db_ops.update_guild_verification_settings(interaction.guild_id, self.settings)
            
            # Create completion embed
            embed = discord.Embed(
                title="✅ Setup Complete!",
                description="The verification system has been configured successfully.",
                color=discord.Color.green()
            )
            
            # Add summary of settings
            settings_summary = (
                f"👤 Guest Role: {self.settings.get('guest_role_name', 'Guest')}\n"
                f"✅ Verified Role: {self.settings.get('verified_role_name', 'Verified')}\n"
                f"👑 Admin Role: {self.settings.get('admin_role_name', 'Staff')}\n"
                f"📜 Rules Channel: {self.settings.get('rules_channel_name', 'rules')}\n"
                f"🎭 Roles Channel: {self.settings.get('roles_channel_name', 'roles')}\n"
                f"⚠️ Admin Channel: {self.settings.get('admin_channel_name', 'admin')}"
            )
            embed.add_field(name="Configuration Summary", value=settings_summary, inline=False)
            
            # Clear all buttons
            self.clear_items()
            
            await interaction.response.edit_message(embed=embed, view=self)
            
        except Exception as e:
            await interaction.response.send_message(f"❌ Error completing setup: {e}", ephemeral=True)

    @discord.ui.button(label="Select Admin Role", style=discord.ButtonStyle.primary)
    async def select_admin_role(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self.is_admin(interaction):
            await interaction.response.send_message(
                "❌ You need administrator permissions to use this command.",
                ephemeral=True
            )
            return

        # Get available roles
        available_roles = [
            role for role in interaction.guild.roles
            if len(role.name) <= 25 and not role.is_default()
        ]

        if not available_roles:
            await interaction.response.send_message(
                "❌ No roles available. Please create a role first.",
                ephemeral=True
            )
            return

        select = discord.ui.Select(
            placeholder="Choose an existing Admin role",
            options=[
                discord.SelectOption(
                    label=role.name,
                    value=str(role.id),
                    description=f"Select {role.name} as Admin role"
                )
                for role in available_roles
            ]
        )
        select.callback = self.handle_admin_role_selection
        
        # Update view with select menu
        self.clear_items()
        self.add_item(select)
        self.selection_active = True
        self.current_select = "admin_role"

        # Add a cancel button
        cancel_button = discord.ui.Button(label="Cancel", style=discord.ButtonStyle.secondary)
        cancel_button.callback = self.cancel_selection
        self.add_item(cancel_button)
        
        await interaction.response.edit_message(view=self)

    async def handle_admin_role_selection(self, interaction: discord.Interaction):
        if not self.is_admin(interaction):
            await interaction.response.send_message(
                "❌ You need administrator permissions to use this command.",
                ephemeral=True
            )
            return

        role_id = int(interaction.data["values"][0])
        role = interaction.guild.get_role(role_id)
        if role:
            self.settings["admin_role_name"] = role.name
            self.selection_active = False
            self.current_select = None
            await self.show_current_step()
            await interaction.response.edit_message(view=self)
        else:
            await interaction.response.send_message("❌ Selected role not found.", ephemeral=True)

    @discord.ui.button(label="Create Admin Role", style=discord.ButtonStyle.primary)
    async def create_admin_role(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self.is_admin(interaction):
            await interaction.response.send_message(
                "❌ You need administrator permissions to use this command.",
                ephemeral=True
            )
            return

        try:
            settings = self.get_guild_settings(interaction.guild_id)
            role = await interaction.guild.create_role(name=settings["admin_role_name"])
            self.settings["admin_role_name"] = role.name
            await interaction.response.send_message(f"✅ Created Admin role: {role.mention}", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"❌ Error creating Admin role: {e}", ephemeral=True)

async def setup(bot):
    """Add the cog to the bot."""
    await bot.add_cog(VerificationCog(bot)) 