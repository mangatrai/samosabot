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
import aiohttp
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
DISCORD_API_BASE = "https://discord.com/api/v10"
REQUEST_TIMEOUT = 10  # seconds

async def fetch_guild_info(session: aiohttp.ClientSession, guild_id: str):
    """
    Fetch guild information from Discord API.
    
    Args:
        session: aiohttp session
        guild_id: The Discord guild ID
        
    Returns:
        Tuple of (success: bool, guild_name: str)
    """
    url = f"{DISCORD_API_BASE}/guilds/{guild_id}"
    headers = {
        "Authorization": f"Bot {TOKEN}",
        "Content-Type": "application/json"
    }
    
    try:
        async with session.get(url, headers=headers, timeout=aiohttp.ClientTimeout(total=REQUEST_TIMEOUT)) as response:
            if response.status == 200:
                data = await response.json()
                return True, data.get("name", "Unknown")
            elif response.status == 404:
                logging.warning(f"Guild {guild_id} not found (404). Guild may not exist or bot not in server.")
                return False, "Unknown (Not Found)"
            elif response.status == 403:
                logging.warning(f"Bot does not have access to guild {guild_id} (403). Bot may have been removed.")
                return False, "Unknown (Forbidden)"
            else:
                logging.error(f"Unexpected status code {response.status} when fetching guild {guild_id}")
                return False, "Unknown (Error)"
    except asyncio.TimeoutError:
        logging.error(f"Timeout fetching guild {guild_id}")
        return False, "Unknown (Timeout)"
    except Exception as e:
        logging.error(f"Error fetching guild info: {e}")
        return False, "Unknown (Error)"

async def leave_guild(session: aiohttp.ClientSession, guild_id: str) -> bool:
    """
    Leave a guild using Discord API.
    
    Args:
        session: aiohttp session
        guild_id: The Discord guild ID to leave
        
    Returns:
        True if successful, False otherwise
    """
    url = f"{DISCORD_API_BASE}/users/@me/guilds/{guild_id}"
    headers = {
        "Authorization": f"Bot {TOKEN}",
        "Content-Type": "application/json"
    }
    
    try:
        async with session.delete(url, headers=headers, timeout=aiohttp.ClientTimeout(total=REQUEST_TIMEOUT)) as response:
            if response.status == 204:
                logging.info(f"Successfully left guild {guild_id}")
                return True
            elif response.status == 404:
                logging.warning(f"Guild {guild_id} not found when trying to leave (404)")
                return False
            elif response.status == 403:
                logging.warning(f"Bot does not have permission to leave guild {guild_id} (403)")
                return False
            else:
                error_text = await response.text()
                logging.error(f"Unexpected status code {response.status} when leaving guild {guild_id}: {error_text}")
                return False
    except asyncio.TimeoutError:
        logging.error(f"Timeout leaving guild {guild_id}")
        return False
    except Exception as e:
        logging.error(f"Error leaving guild: {e}")
        return False

async def evict_server(guild_id: str):
    """
    Forcefully remove the bot from a Discord server and update database.
    Uses HTTP API directly instead of full bot connection to avoid hanging.
    
    Args:
        guild_id: The Discord guild ID to evict the bot from
    """
    if not TOKEN:
        logging.error("DISCORD_BOT_TOKEN not found in environment variables")
        return False
    
    guild_name = None
    
    async with aiohttp.ClientSession() as session:
        # First, try to fetch guild info to get the name and validate existence
        logging.info(f"Fetching guild information for {guild_id}...")
        success, fetched_name = await fetch_guild_info(session, guild_id)
        
        if success:
            guild_name = fetched_name
            logging.info(f"Found guild: {guild_name} ({guild_id})")
            
            # Try to leave the guild
            logging.info(f"Attempting to leave guild {guild_name} ({guild_id})...")
            left_successfully = await leave_guild(session, guild_id)
            
            if left_successfully:
                logging.info(f"Successfully left guild {guild_name} ({guild_id})")
            else:
                logging.warning(f"Could not leave guild {guild_id}, but will update database anyway")
        else:
            # Guild not found or bot not in it, but we'll still update database
            logging.info(f"Guild {guild_id} not accessible, but will update database status")
            guild_name = fetched_name
        
        # Update database with EVICTED status regardless of leave result
        logging.info(f"Updating database status to EVICTED for guild {guild_id}...")
        
        # Try to get the actual guild name from database if we don't have it
        if not guild_name or guild_name.startswith("Unknown"):
            try:
                from utils.astra_db_ops import get_registered_servers_collection
                collection = get_registered_servers_collection()
                if collection:
                    existing = collection.find_one({"guild_id": guild_id})
                    if existing and existing.get("guild_name"):
                        guild_name = existing.get("guild_name")
                        logging.info(f"Retrieved guild name from database: {guild_name}")
            except Exception as e:
                logging.warning(f"Could not retrieve guild name from database: {e}")
        
        astra_db_ops.register_or_update_guild(
            guild_id=int(guild_id),
            guild_name=guild_name or "Unknown",
            status="EVICTED"
        )
        logging.info(f"Database updated successfully. Guild {guild_id} status set to EVICTED")
        
        return True

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
