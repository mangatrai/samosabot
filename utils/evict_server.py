"""
Server Eviction Utility

Standalone script to forcefully remove the bot from a Discord server and update
the registered_servers collection with status "EVICTED".

Usage:
    python utils/evict_server.py <guild_id>

Example:
    python utils/evict_server.py 123456789012345678
"""

import sys
import os
import asyncio
import discord
from dotenv import load_dotenv
import logging

# Add parent directory to path to import utils
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils import astra_db_ops

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

TOKEN = os.getenv("DISCORD_BOT_TOKEN")
CONNECTION_TIMEOUT = 30  # seconds
READY_TIMEOUT = 30  # seconds

async def evict_server(guild_id: str):
    """
    Forcefully remove the bot from a Discord server and update database.
    
    Args:
        guild_id: The Discord guild ID to evict the bot from
    """
    if not TOKEN:
        logging.error("DISCORD_BOT_TOKEN not found in environment variables")
        return False
    
    # Set up minimal intents needed to leave guild
    intents = discord.Intents.default()
    intents.guilds = True
    
    bot = discord.Client(intents=intents)
    guild_name = None
    
    try:
        # Connect to Discord with timeout
        logging.info("Connecting to Discord...")
        await bot.login(TOKEN)
        
        # Connect with timeout
        try:
            await asyncio.wait_for(bot.connect(), timeout=CONNECTION_TIMEOUT)
        except asyncio.TimeoutError:
            logging.error(f"Connection to Discord timed out after {CONNECTION_TIMEOUT} seconds")
            return False
        
        # Wait for bot to be ready with timeout
        logging.info("Waiting for bot to be ready...")
        try:
            await asyncio.wait_for(bot.wait_until_ready(), timeout=READY_TIMEOUT)
        except asyncio.TimeoutError:
            logging.error(f"Bot ready state timed out after {READY_TIMEOUT} seconds")
            return False
        
        logging.info(f"Bot connected. Bot user: {bot.user}")
        
        # First try to get from cache (fast)
        guild = bot.get_guild(int(guild_id))
        
        # If not in cache, fetch from API (validates existence and bot membership)
        if not guild:
            logging.info(f"Guild {guild_id} not in cache, fetching from API...")
            try:
                guild = await asyncio.wait_for(bot.fetch_guild(int(guild_id)), timeout=10)
            except asyncio.TimeoutError:
                logging.error(f"Fetching guild {guild_id} timed out")
                return False
            except discord.errors.NotFound:
                logging.warning(f"Guild {guild_id} not found. Bot may not be in this server or guild doesn't exist.")
                # Update database anyway to mark as EVICTED
                logging.info(f"Updating database status to EVICTED for guild {guild_id}...")
                astra_db_ops.register_or_update_guild(
                    guild_id=int(guild_id),
                    guild_name="Unknown (Not Found)",
                    status="EVICTED"
                )
                logging.info(f"Database updated. Guild {guild_id} marked as EVICTED (not found)")
                return True
            except discord.errors.Forbidden:
                logging.warning(f"Bot does not have access to guild {guild_id}. Bot may have been removed.")
                # Update database anyway to mark as EVICTED
                logging.info(f"Updating database status to EVICTED for guild {guild_id}...")
                astra_db_ops.register_or_update_guild(
                    guild_id=int(guild_id),
                    guild_name="Unknown (Forbidden)",
                    status="EVICTED"
                )
                logging.info(f"Database updated. Guild {guild_id} marked as EVICTED (forbidden)")
                return True
        
        guild_name = guild.name
        logging.info(f"Found guild: {guild_name} ({guild_id})")
        
        # Leave the guild forcefully
        logging.info(f"Leaving guild {guild_name} ({guild_id})...")
        try:
            await asyncio.wait_for(guild.leave(), timeout=10)
        except asyncio.TimeoutError:
            logging.error(f"Leaving guild {guild_id} timed out")
            return False
        
        logging.info(f"Successfully left guild {guild_name} ({guild_id})")
        
        # Update database with EVICTED status
        logging.info(f"Updating database status to EVICTED for guild {guild_id}...")
        astra_db_ops.register_or_update_guild(
            guild_id=int(guild_id),
            guild_name=guild_name,
            status="EVICTED"
        )
        logging.info(f"Database updated successfully. Guild {guild_id} status set to EVICTED")
        
        return True
        
    except discord.errors.Forbidden:
        logging.error(f"Bot does not have permission to leave guild {guild_id}")
        # Still update database
        astra_db_ops.register_or_update_guild(
            guild_id=int(guild_id),
            guild_name=guild_name or "Unknown (Forbidden)",
            status="EVICTED"
        )
        return False
    except discord.errors.NotFound:
        logging.error(f"Guild {guild_id} not found or bot is not in this server")
        # Still update database
        astra_db_ops.register_or_update_guild(
            guild_id=int(guild_id),
            guild_name=guild_name or "Unknown (Not Found)",
            status="EVICTED"
        )
        return False
    except Exception as e:
        logging.error(f"Error evicting server: {e}", exc_info=True)
        return False
    finally:
        # Close the bot connection
        logging.info("Closing bot connection...")
        try:
            await asyncio.wait_for(bot.close(), timeout=5)
        except Exception as e:
            logging.warning(f"Error closing bot connection: {e}")

def validate_guild_id(guild_id: str) -> bool:
    """
    Validate Discord guild ID format.
    Discord snowflake IDs are 17-19 digits.
    
    Args:
        guild_id: The guild ID string to validate
        
    Returns:
        True if valid, False otherwise
    """
    if not guild_id.isdigit():
        return False
    
    # Discord snowflake IDs are typically 17-19 digits
    if len(guild_id) < 17 or len(guild_id) > 19:
        return False
    
    return True

def main():
    """Main entry point for the script."""
    if len(sys.argv) < 2:
        print("Usage: python utils/evict_server.py <guild_id>")
        print("Example: python utils/evict_server.py 123456789012345678")
        sys.exit(1)
    
    guild_id = sys.argv[1].strip()
    
    # Validate guild_id format
    if not validate_guild_id(guild_id):
        logging.error(f"Invalid guild_id format: {guild_id}")
        logging.error("Discord guild IDs must be 17-19 digit numbers (snowflake format)")
        sys.exit(1)
    
    logging.info(f"Starting eviction process for guild ID: {guild_id}")
    
    # Run the async eviction
    try:
        success = asyncio.run(evict_server(guild_id))
        
        if success:
            logging.info("Eviction completed successfully")
            sys.exit(0)
        else:
            logging.error("Eviction failed")
            sys.exit(1)
    except KeyboardInterrupt:
        logging.warning("Eviction process interrupted by user")
        sys.exit(1)
    except Exception as e:
        logging.error(f"Unexpected error: {e}", exc_info=True)
        sys.exit(1)

if __name__ == "__main__":
    main()
