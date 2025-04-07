import discord
from discord.ext import commands
import asyncio
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Test bot configuration
TEST_TOKEN = os.getenv('TEST_BOT_TOKEN')  # Token for your test bot
GUILD_ID = int(os.getenv('TEST_GUILD_ID'))  # Your test server ID
ADMIN_ID = int(os.getenv('ADMIN_USER_ID'))  # Your admin user ID

class TestBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.all()
        super().__init__(command_prefix='!test_', intents=intents)
        
    async def setup_hook(self):
        print(f"Test bot is ready!")

    async def on_ready(self):
        print(f'Logged in as {self.user} (ID: {self.user.id})')
        print('------')

class VerificationTester(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command()
    async def simulate_join(self, ctx):
        """Simulates a new member joining the server"""
        try:
            # Check if bot has necessary permissions
            if not ctx.guild.me.guild_permissions.manage_channels:
                await ctx.send("❌ Bot needs 'Manage Channels' permission!")
                return

            guild = self.bot.get_guild(GUILD_ID)
            if not guild:
                await ctx.send("❌ Couldn't find the test guild! Please check your GUILD_ID in .env")
                return

            member = ctx.author
            await ctx.send(f"🔄 Starting join simulation for {member.name}...")
            
            # Create verification channel - replace dots with empty string
            channel_name = f"{member.name.lower().replace('.', '')}_welcome"
            category = discord.utils.get(guild.categories, name="Verification")
            
            if not category:
                try:
                    category = await guild.create_category("Verification")
                    await ctx.send("📁 Created Verification category")
                except discord.Forbidden:
                    await ctx.send("❌ Bot doesn't have permission to create categories!")
                    return
                except Exception as e:
                    await ctx.send(f"❌ Error creating category: {str(e)}")
                    return
            
            # Check if channel already exists
            existing_channel = discord.utils.get(guild.channels, name=channel_name)
            if existing_channel:
                await ctx.send(f"⚠️ Channel {channel_name} already exists!")
                return

            # Create the channel
            try:
                overwrites = {
                    guild.default_role: discord.PermissionOverwrite(read_messages=False),
                    member: discord.PermissionOverwrite(read_messages=True, send_messages=True),
                    guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True, manage_channels=True)
                }
                
                channel = await guild.create_text_channel(
                    name=channel_name,
                    category=category,
                    overwrites=overwrites
                )
                
                await ctx.send(f"✅ Created verification channel: {channel.mention}")
                
                # Send welcome message
                embed = discord.Embed(
                    title="Welcome to Verification!",
                    description="Please complete the verification process to access the server.",
                    color=discord.Color.blue()
                )
                embed.add_field(name="Steps", value="1. Click 'Start Verification'\n2. Answer the questions\n3. Read the rules\n4. Select your roles")
                
                # Create verification button
                button = discord.ui.Button(
                    style=discord.ButtonStyle.primary,
                    label="Start Verification",
                    custom_id="start_verification"
                )
                view = discord.ui.View()
                view.add_item(button)
                
                await channel.send(embed=embed, view=view)
                await ctx.send("✅ Welcome message sent!")
                
                # Trigger member join event (without await since dispatch is not async)
                self.bot.dispatch('member_join', member)
                await ctx.send("✅ Join event dispatched!")
                
            except discord.Forbidden:
                await ctx.send("❌ Bot doesn't have permission to create channels!")
                return
            except Exception as e:
                await ctx.send(f"❌ Error creating channel: {str(e)}")
                return
            
        except Exception as e:
            await ctx.send(f"❌ Error during simulation: {str(e)}")
            print(f"Error in simulate_join: {str(e)}")

    @commands.command()
    async def find_channel(self, ctx):
        """Lists all verification channels"""
        try:
            verification_category = discord.utils.get(ctx.guild.categories, name="Verification")
            if not verification_category:
                await ctx.send("❌ No Verification category found!")
                return

            channels = verification_category.channels
            if not channels:
                await ctx.send("❌ No channels found in Verification category!")
                return

            embed = discord.Embed(
                title="Verification Channels",
                color=discord.Color.blue()
            )

            for channel in channels:
                embed.add_field(
                    name=channel.name,
                    value=f"ID: {channel.id}\nType: {channel.type}",
                    inline=False
                )

            await ctx.send(embed=embed)

        except Exception as e:
            await ctx.send(f"❌ Error finding channels: {str(e)}")
            print(f"Error in find_channel: {str(e)}")

    @commands.command()
    async def verify_flow(self, ctx):
        """Tests the complete verification flow"""
        try:
            # Step 1: Check if verification channel exists
            # First try to find the channel by name - replace dots with empty string
            channel_name = f"{ctx.author.name.lower().replace('.', '')}_welcome"
            print(f"Looking for channel: {channel_name}")  # Debug print
            
            # Try to find in Verification category first
            verification_category = discord.utils.get(ctx.guild.categories, name="Verification")
            channels = []
            
            if verification_category:
                print(f"Found Verification category with {len(verification_category.channels)} channels")  # Debug print
                channels = [c for c in verification_category.channels if c.name == channel_name]
                if not channels:
                    # Try without the welcome suffix
                    base_name = ctx.author.name.lower().replace('.', '')
                    channels = [c for c in verification_category.channels if c.name.startswith(base_name)]
            
            if not channels:
                await ctx.send(f"❌ No verification channel found for {channel_name}! Run !test_simulate_join first")
                return

            channel = channels[0]
            await ctx.send(f"📝 Testing verification in {channel.mention}...")

            # Step 2: Simulate clicking verification button
            await ctx.send("🔄 Simulating 'Start Verification' click...")
            await asyncio.sleep(2)
            
            # Step 3: Simulate answering questions
            await ctx.send("❓ Simulating answering verification questions...")
            await asyncio.sleep(2)
            
            # Step 4: Simulate rules acknowledgment
            await ctx.send("📜 Simulating rules acknowledgment...")
            await asyncio.sleep(2)
            
            # Step 5: Simulate role selection
            await ctx.send("👥 Simulating role selection...")
            await asyncio.sleep(2)

            await ctx.send("✅ Verification flow test complete!")
            
        except Exception as e:
            await ctx.send(f"❌ Error during verification flow: {str(e)}")
            print(f"Error in verify_flow: {str(e)}")

    @commands.command()
    async def admin_approve(self, ctx, member: discord.Member = None):
        """Simulates admin approval of a verification"""
        try:
            if not member:
                member = ctx.author

            if ctx.author.id != ADMIN_ID:
                await ctx.send("❌ Only admins can use this command!")
                return

            await ctx.send(f"🔄 Simulating admin approval for {member.name}...")

            # Get the roles
            guest_role = discord.utils.get(ctx.guild.roles, name="Guest")
            verified_role = discord.utils.get(ctx.guild.roles, name="Verified")

            if not guest_role or not verified_role:
                await ctx.send("❌ Required roles not found! Make sure Guest and Verified roles exist.")
                return

            # Find the verification channel
            channel_name = f"{member.name.lower().replace('.', '')}_welcome"
            verification_channel = discord.utils.get(ctx.guild.channels, name=channel_name)

            if not verification_channel:
                await ctx.send("❌ Verification channel not found!")
                return

            # Perform role changes
            try:
                # Remove Guest role
                await member.remove_roles(guest_role)
                await ctx.send("✅ Removed Guest role")

                # Add Verified role
                await member.add_roles(verified_role)
                await ctx.send("✅ Added Verified role")

                # Send success message to verification channel
                embed = discord.Embed(
                    title="Verification Approved! 🎉",
                    description="Welcome to the server! You now have access to all verified channels.",
                    color=discord.Color.green()
                )
                embed.add_field(
                    name="Next Steps",
                    value="1. Check out the general channels\n2. Read the rules in #rules\n3. Select your roles in #roles"
                )
                await verification_channel.send(embed=embed)

                # Schedule channel deletion
                await ctx.send("⏳ Verification channel will be deleted in 60 seconds...")
                await asyncio.sleep(60)
                await verification_channel.delete()
                await ctx.send("✅ Verification channel deleted")

            except discord.Forbidden:
                await ctx.send("❌ Bot doesn't have permission to manage roles!")
                return
            except Exception as e:
                await ctx.send(f"❌ Error during role changes: {str(e)}")
                return

            await ctx.send("✅ Admin approval process completed!")
            
        except Exception as e:
            await ctx.send(f"❌ Error during admin approval: {str(e)}")
            print(f"Error in admin_approve: {str(e)}")

    @commands.command()
    async def admin_deny(self, ctx, member: discord.Member = None, *, reason: str = "No reason provided"):
        """Simulates admin denial of a verification"""
        try:
            if not member:
                member = ctx.author

            if ctx.author.id != ADMIN_ID:
                await ctx.send("❌ Only admins can use this command!")
                return

            await ctx.send(f"🔄 Simulating admin denial for {member.name}...")

            # Find the verification channel
            channel_name = f"{member.name.lower().replace('.', '')}_welcome"
            verification_channel = discord.utils.get(ctx.guild.channels, name=channel_name)

            if not verification_channel:
                await ctx.send("❌ Verification channel not found!")
                return

            # Send denial message to verification channel
            embed = discord.Embed(
                title="Verification Denied ❌",
                description="Your verification request has been denied.",
                color=discord.Color.red()
            )
            embed.add_field(name="Reason", value=reason)
            embed.add_field(
                name="Next Steps",
                value="You can try the verification process again or contact an admin for assistance."
            )
            await verification_channel.send(embed=embed)

            await ctx.send("✅ Admin denial process completed!")
            
        except Exception as e:
            await ctx.send(f"❌ Error during admin denial: {str(e)}")
            print(f"Error in admin_deny: {str(e)}")

    @commands.command()
    async def cleanup(self, ctx):
        """Cleans up test channels and roles"""
        try:
            await ctx.send("🧹 Cleaning up test channels...")
            # Clean up verification channels
            for channel in ctx.guild.channels:
                if channel.name.endswith('_welcome'):
                    try:
                        await channel.delete()
                        await ctx.send(f"Deleted channel: {channel.name}")
                    except:
                        await ctx.send(f"Failed to delete: {channel.name}")

            # Clean up category if empty
            category = discord.utils.get(ctx.guild.categories, name="Verification")
            if category and len(category.channels) == 0:
                await category.delete()
                await ctx.send("Deleted Verification category")

            await ctx.send("✅ Cleanup complete!")
            
        except Exception as e:
            await ctx.send(f"❌ Error during cleanup: {str(e)}")
            print(f"Error in cleanup: {str(e)}")

    @commands.command()
    async def check_config(self, ctx):
        """Checks the bot's configuration and permissions"""
        try:
            guild = self.bot.get_guild(GUILD_ID)
            if not guild:
                await ctx.send("❌ Couldn't find the test guild!")
                return

            # Check bot permissions
            permissions = guild.me.guild_permissions
            required_permissions = {
                "Manage Channels": permissions.manage_channels,
                "Send Messages": permissions.send_messages,
                "Read Messages": permissions.read_messages,
                "Manage Roles": permissions.manage_roles
            }

            embed = discord.Embed(
                title="Bot Configuration Check",
                color=discord.Color.blue()
            )

            # Add permission status
            for perm, has_perm in required_permissions.items():
                embed.add_field(
                    name=perm,
                    value="✅" if has_perm else "❌",
                    inline=True
                )

            # Add environment variables status
            embed.add_field(
                name="Environment Variables",
                value=f"TEST_TOKEN: {'✅ Set' if TEST_TOKEN else '❌ Missing'}\n"
                      f"GUILD_ID: {'✅ Set' if GUILD_ID else '❌ Missing'}\n"
                      f"ADMIN_ID: {'✅ Set' if ADMIN_ID else '❌ Missing'}",
                inline=False
            )

            await ctx.send(embed=embed)

        except Exception as e:
            await ctx.send(f"❌ Error checking configuration: {str(e)}")
            print(f"Error in check_config: {str(e)}")

async def main():
    bot = TestBot()
    await bot.add_cog(VerificationTester(bot))
    async with bot:
        await bot.start(TEST_TOKEN)

if __name__ == "__main__":
    asyncio.run(main()) 