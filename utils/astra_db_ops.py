"""
AstraDB Operations Module

This module provides a suite of functions for interacting with AstraDB using the astrapy library.
It handles database connectivity, collection management, and data operations essential for the
Discord bot's functionality. Key features include:

  - Establishing a connection to AstraDB using configuration parameters (API endpoint, namespace, and token)
    loaded from environment variables.
  - Creating and retrieving various collections, including:
      • qotd_channels: Stores scheduled Question of the Day (QOTD) channel configurations.
      • bot_status_channels: Stores channels for periodic bot status updates.
      • trivia_leaderboard: Maintains trivia game statistics and leaderboards.
      • user_requests: Logs user request data.
      • daily_counters: Tracks daily request counts per user.
  - Loading and saving QOTD schedules and bot status channels.
  - Updating and fetching user statistics and trivia leaderboard information.
  - Inserting user requests and managing daily request counts.

All operations are logged using Python's logging module for debugging and error tracking.
This module is a critical component for ensuring persistent data management within the Discord bot.
"""

import logging
import datetime
from .db_connection import get_db_connection

# Function to get qotd channels collection
def get_qotd_channels_collection():
    database = get_db_connection()
    if database is None:
        return None
    try:
        collection = database.get_collection("qotd_channels")
        logging.debug(f"Retrieved qotd_channels collection: {collection.info().name}")
        return collection
    except Exception as e:
        logging.error(f"[ERROR] Failed to retrieve qotd_channels collection: {e}")
        return None

# Function to get bot status channels collection
def get_bot_status_channels_collection():
    database = get_db_connection()
    if database is None:
        return None
    try:
        collection = database.get_collection("bot_status_channels")
        logging.debug(f"Retrieved bot_status_channels collection: {collection.info().name}")
        return collection
    except Exception as e:
        logging.error(f"[ERROR] Failed to retrieve bot_status_channels collection: {e}")
        return None

# Function to get trivia questions collection
def get_trivia_leaderboard_collection():
    database = get_db_connection()
    if database is None:
        return None
    try:
        collection = database.get_collection("trivia_leaderboard")
        logging.debug(f"Retrieved trivia_leaderboard collection: {collection.info().name}")
        return collection
    except Exception as e:
        logging.error(f"[ERROR] Failed to retrieve trivia_leaderboard collection: {e}")
        return None

# Function to get user request collection
def get_user_requests_collection():
    database = get_db_connection()
    if database is None:
        return None
    try:
        collection = database.get_collection("user_requests")
        logging.debug(f"Retrieved user_requests collection: {collection.info().name}")
        return collection
    except Exception as e:
        logging.error(f"[ERROR] Failed to retrieve user_requests collection: {e}")
        return None

def get_daily_counters_collection():
    database = get_db_connection()
    if database is None:
        return None
    try:
        collection = database.get_collection("daily_counters")
        logging.debug(f"Retrieved daily_counters collection: {collection.info().name}")
        return collection
    except Exception as e:
        logging.error(f"[ERROR] Failed to retrieve daily_counters collection: {e}")
        return None

def get_registered_servers_collection():
    database = get_db_connection()
    if database is None:
        return None
    try:
        collection = database.get_collection("registered_servers")
        logging.debug(f"Retrieved registered_servers collection: {collection.info().name}")
        return collection
    except Exception as e:
        logging.error(f"Failed to retrieve registered_servers collection: {e}")
        return None

def get_verification_attempts_collection():
    """Get the verification_attempts collection."""
    database = get_db_connection()
    if database is None:
        return None
    try:
        collection = database.get_collection("verification_attempts")
        logging.debug(f"Retrieved verification_attempts collection: {collection.info().name}")
        return collection
    except Exception as e:
        logging.error(f"Failed to retrieve verification_attempts collection: {e}")
        return None

def get_guild_verification_settings_collection():
    """Get the guild_verification_settings collection."""
    database = get_db_connection()
    if database is None:
        return None
    try:
        collection = database.get_collection("guild_verification_settings")
        logging.debug(f"Retrieved guild_verification_settings collection: {collection.info().name}")
        return collection
    except Exception as e:
        logging.error(f"Failed to retrieve guild_verification_settings collection: {e}")
        return None

#Function to load qotd schedules
def load_qotd_schedules():
    """Load scheduled QOTD channels from AstraDB."""
    try:
        collection = get_qotd_channels_collection()
        if collection is None:
            return {}
        results = collection.find({})

        qotd_channels = {doc['guild_id']: doc['channel_id'] for doc in results}

        logging.debug(f"Loaded QOTD schedules: {qotd_channels}")
        return qotd_channels

    except Exception as e:
        logging.error(f"[ERROR] Failed to load QOTD schedules: {e}")
        return {}  # Return empty dict in case of error

# Function to save qotd schedules
def save_qotd_schedules(schedule_data):
    """Saves QOTD schedule data to AstraDB using find_one_and_update."""
    try:
        collection = get_qotd_channels_collection()

        result = collection.find_one_and_update(
            {"guild_id": schedule_data["guild_id"]},
            {"$set": schedule_data},
            upsert=True,
        )

        if result:
            logging.debug(f"Schedule data updated/inserted for guild_id: {schedule_data['guild_id']}")
        else:
            logging.debug(f"Schedule data may have been inserted or updated, but no document was returned. Guild ID: {schedule_data['guild_id']}")

    except Exception as e:
        logging.error(f"[ERROR] Failed to save/update QOTD schedules: {e}")


# Update user stats in Astra DB
def update_user_stats(user_id, username, correct_increment=0, wrong_increment=0, 
                     guild_id: str = None, guild_name: str = None, channel_id: str = None):
    """Update user statistics and leaderboard in AstraDB, incrementing by 1."""
    try:
        collection = get_trivia_leaderboard_collection()
        existing_doc = collection.find_one({"user_id": user_id})

        update_data = {"$set": {"username": username}}
        if guild_id:
            update_data["$set"]["guild_id"] = guild_id
        if guild_name:
            update_data["$set"]["guild_name"] = guild_name
        if channel_id:
            update_data["$set"]["channel_id"] = channel_id
        
        increment_data = {}

        if existing_doc:
            if correct_increment == 1:
                increment_data["total_correct"] = 1
            if wrong_increment == 1:
                increment_data["total_wrong"] = 1

            if increment_data:
                update_data["$inc"] = increment_data
        else:
            if correct_increment == 1:
                update_data["$set"]["total_correct"] = 1
                update_data["$set"]["total_wrong"] = 0
            elif wrong_increment == 1:
                update_data["$set"]["total_correct"] = 0
                update_data["$set"]["total_wrong"] = 1
            else:
                update_data["$set"]["total_correct"] = 0
                update_data["$set"]["total_wrong"] = 0

        # Use update_one with upsert=True
        collection.update_one(
            {"user_id": user_id},
            update_data,
            upsert=True,
        )
        logging.debug(f"User stats updated/inserted for user_id: {user_id}")

    except Exception as e:
        logging.error(f"[ERROR] Failed to update user stats: {e}")

# Retrieve user stats from Astra DB
def get_user_stats(user_id):
    """Fetch user statistics from trivia_leaderboard in AstraDB."""
    try:
        collection = get_trivia_leaderboard_collection()
        result = collection.find_one({"user_id": user_id})

        if result:
            return {"correct": result.get("total_correct", 0), "wrong": result.get("total_wrong", 0)}
        else:
            return {"correct": 0, "wrong": 0}

    except Exception as e:
        logging.error(f"[ERROR] Failed to retrieve user stats: {e}")
        return {"correct": 0, "wrong": 0}

# Save bot status channel to AstraDB
def save_bot_status_channel(guild_id, channel_id):
    """Save bot status channel in AstraDB."""
    try:
        collection = get_bot_status_channels_collection()
        collection.find_one_and_update(
            {"guild_id": guild_id},
            {"$set": {"channel_id": channel_id}},
            upsert=True,
        )
        logging.debug(f"Bot status channel saved/updated for guild_id: {guild_id}")
    except Exception as e:
        logging.error(f"[ERROR] Failed to save/update bot status channel: {e}")

# Load stored bot status channels from AstraDB
def load_bot_status_channels():
    """Load bot status channels from AstraDB."""
    try:
        collection = get_bot_status_channels_collection()
        results = collection.find({})  # Fetch all documents
        return {doc["guild_id"]: doc["channel_id"] for doc in results}
    except Exception as e:
        logging.error(f"[ERROR] Failed to load bot status channels: {e}")
        return {}

# Get trivia leaderboard from Astra DB
def get_trivia_leaderboard():
    """Show the top trivia players from AstraDB, including total wrong answers."""
    try:
        collection = get_trivia_leaderboard_collection()
        results = collection.find(sort={"total_correct": -1}, limit=10)  # Sort by total_correct descending and limit to 10.
        return [
            {
                "username": doc["username"],
                "total_correct": doc["total_correct"],
                "total_wrong": doc.get("total_wrong", 0),  # Use get() to handle missing total_wrong
            }
            for doc in results
        ]
    except Exception as e:
        logging.error(f"[ERROR] Failed to retrieve trivia leaderboard: {e}")
        return []

def clean_collection_data(collectionName):
    """Cleans all data from the trivia leaderboard collection."""
    try:
        collection = get_db_connection().get_collection(collectionName)
        # Delete all documents from the collection
        result = collection.delete_many(filter={})
        logging.debug(f"Deleted {result.deleted_count} documents from {collectionName}.")

    except Exception as e:
        logging.error(f"Error cleaning trivia leaderboard: {e}")

# New functions for user requests and daily counters
def insert_user_request(user_id, question, response, guild_id: str = None, guild_name: str = None, 
                       username: str = None, channel_id: str = None):
    """Insert a user request into the user_requests collection."""
    try:
        collection = get_user_requests_collection()
        document = {
            "user_id": str(user_id),
            "question": question,
            "response": response,
            "timestamp": datetime.datetime.utcnow().isoformat(),
            "guild_id": guild_id,
            "guild_name": guild_name,
            "username": username,
            "channel_id": channel_id
        }
        collection.insert_one(document)
        logging.debug(f"User request inserted: User ID {user_id}")
    except Exception as e:
        logging.error(f"Error inserting user request: {e}")

def get_user_requests(user_id):
    """Retrieve user requests from the user_requests collection."""
    try:
        collection = get_user_requests_collection()
        results = collection.find({"user_id": str(user_id)})
        return list(results)
    except Exception as e:
        logging.error(f"Error retrieving user requests: {e}")
        return []

def get_daily_request_count(user_id):
    """Retrieve the daily request count for a user (for /ask command limit)."""
    today = datetime.date.today().isoformat()
    try:
        collection = get_daily_counters_collection()
        # For backward compatibility, check both old format (no guild_id) and new format
        result = collection.find_one({"user_id": str(user_id), "date": today})
        if result:
            return result.get("count", 0)
        # If no result, sum all counts for this user today (in case multiple guilds)
        results = collection.find({"user_id": str(user_id), "date": today})
        total = sum(doc.get("count", 0) for doc in results)
        return total
    except Exception as e:
        logging.error(f"Error retrieving daily request count: {e}")
        return 0

def increment_daily_request_count(user_id, guild_id: str = None, guild_name: str = None, username: str = None):
    """Increment the daily request count for a user."""
    today = datetime.date.today().isoformat()
    try:
        collection = get_daily_counters_collection()
        # If guild_id provided, track per guild; otherwise track globally (for /ask backward compatibility)
        if guild_id:
            filter_query = {"user_id": str(user_id), "date": today, "guild_id": str(guild_id)}
            update_query = {
                "$inc": {"count": 1},
                "$set": {
                    "guild_name": guild_name,
                    "username": username
                }
            }
        else:
            # Backward compatibility for /ask command
            filter_query = {"user_id": str(user_id), "date": today}
            update_query = {"$inc": {"count": 1}}
        
        collection.find_one_and_update(
            filter_query,
            update_query,
            upsert=True,
        )
        logging.debug(f"Daily request count incremented for User ID {user_id}")
    except Exception as e:
        logging.error(f"Error incrementing daily request count: {e}")

def register_or_update_guild(guild_id: int, guild_name: str, status, owner_id: str = None,
                            owner_name: str = None, server_created_at: str = None,
                            description: str = None, member_count: int = None,
                            icon_url: str = None, banner_url: str = None,
                            verification_level: int = None, premium_tier: int = None,
                            premium_subscription_count: int = None, features: list = None,
                            vanity_url_code: str = None, preferred_locale: str = None,
                            nsfw_level: int = None):
    """
    Register or update a guild with comprehensive metadata.
    
    If the guild is not already registered, insert a new record with all provided metadata.
    If the guild already exists, update guild_name, status, lastupdatedat, and all provided metadata fields.
    """
    collection = get_registered_servers_collection()
    if collection is None:
        return
    try:
        now = datetime.datetime.utcnow().isoformat()
        existing_record = collection.find_one({"guild_id": str(guild_id)})
        
        # Build update document with only provided fields
        update_fields = {
            "guild_name": guild_name,
            "status": status,
            "lastupdatedat": now
        }
        
        # Add optional fields if provided
        if owner_id is not None:
            update_fields["owner_id"] = owner_id
        if owner_name is not None:
            update_fields["owner_name"] = owner_name
        if server_created_at is not None:
            update_fields["server_created_at"] = server_created_at
        if description is not None:
            update_fields["description"] = description
        if member_count is not None:
            update_fields["member_count"] = member_count
        if icon_url is not None:
            update_fields["icon_url"] = icon_url
        if banner_url is not None:
            update_fields["banner_url"] = banner_url
        if verification_level is not None:
            update_fields["verification_level"] = verification_level
        if premium_tier is not None:
            update_fields["premium_tier"] = premium_tier
        if premium_subscription_count is not None:
            update_fields["premium_subscription_count"] = premium_subscription_count
        if features is not None:
            update_fields["features"] = features
        if vanity_url_code is not None:
            update_fields["vanity_url_code"] = vanity_url_code
        if preferred_locale is not None:
            update_fields["preferred_locale"] = preferred_locale
        if nsfw_level is not None:
            update_fields["nsfw_level"] = nsfw_level
        
        if not existing_record:
            # Insert new record
            document = {
                "guild_id": str(guild_id),
                "installed_at": now,
                **update_fields
            }
            collection.insert_one(document)
            logging.debug(f"Inserted new guild record: {guild_name} ({guild_id}) at {now}")
        else:
            # Update existing record
            collection.update_one(
                {"guild_id": str(guild_id)},
                {"$set": update_fields}
            )
            logging.debug(f"Updated guild record: {guild_name} ({guild_id}) with lastupdatedat {now}")
    except Exception as e:
        logging.error(f"Error in register_or_update_guild: {e}")

def update_guild_added_by(guild_id: str, user_id: str, username: str):
    """Update added_by fields if not already set (first user heuristic)."""
    try:
        collection = get_registered_servers_collection()
        if collection is None:
            return
        
        # Only update if added_by_user_id doesn't exist
        result = collection.update_one(
            {"guild_id": guild_id, "added_by_user_id": {"$exists": False}},
            {"$set": {"added_by_user_id": user_id, "added_by_username": username}}
        )
        if result.modified_count > 0:
            logging.debug(f"Updated added_by for guild {guild_id}: {username} ({user_id})")
    except Exception as e:
        logging.error(f"Error updating guild added_by: {e}")

def list_registered_servers():
    """
    Retrieve a list of all registered servers from the 'registered_servers' collection in AstraDB.

    Returns:
        list: A list of dictionaries, each containing:
              - 'guild_id': The ID of the guild.
              - 'guild_name': The name of the guild.
              - 'installed_at': The ISO timestamp of when the bot was registered.
              Returns an empty list if no servers are found or if an error occurs.
    """
    collection = get_registered_servers_collection()
    if not collection:
        return []
    try:
        results = collection.find({})
        servers = [{
            "guild_id": doc.get("guild_id", "Unknown"),
            "guild_name": doc.get("guild_name", "Unknown"),
            "installed_at": doc.get("installed_at", "Unknown")
        } for doc in results]
        return servers
    except Exception as e:
        logging.error(f"Error retrieving registered servers: {e}")
        return []

def log_verification_attempt(
    user_id: str,
    username: str,
    guild_id: str,
    stage: str,
    success: bool = None,
    details: str = None
):
    """Log a verification attempt or stage completion."""
    try:
        collection = get_verification_attempts_collection()
        if collection is None:
            return

        document = {
            "user_id": str(user_id),
            "username": username,
            "guild_id": str(guild_id),
            "stage": stage,
            "success": success,
            "timestamp": datetime.datetime.utcnow().isoformat(),
            "details": details
        }
        
        collection.insert_one(document)
        logging.debug(f"Logged verification attempt for {username} at stage {stage}")
    except Exception as e:
        logging.error(f"Error logging verification attempt: {e}")

def get_verification_history(user_id: str, guild_id: str):
    """Get verification history for a user in a specific guild."""
    try:
        collection = get_verification_attempts_collection()
        if collection is None:
            return []

        results = collection.find({
            "user_id": str(user_id),
            "guild_id": str(guild_id)
        }, sort={"timestamp": -1})
        
        return list(results)
    except Exception as e:
        logging.error(f"Error getting verification history: {e}")
        return []

def get_guild_verification_settings(guild_id: int) -> dict:
    """
    Get verification settings for a guild.
    
    Returns:
        dict: Guild verification settings including:
            - enabled: bool
            - guest_role_name: str
            - verified_role_name: str
            - rules_channel_name: str
            - roles_channel_name: str
            - admin_channel_name: str
            - admin_role_name: str
    """
    try:
        collection = get_guild_verification_settings_collection()
        logging.info(f"Querying for guild_id: {guild_id} (type: {type(guild_id)})")
        result = collection.find_one({"guild_id": guild_id})
        
        if result:
            logging.info(f"Found settings: {result}")
            return result
        else:
            logging.info(f"No settings found for guild_id: {guild_id}, returning defaults")
            # Return default settings if none exist
            return {
                "guild_id": guild_id,
                "enabled": False,
                "guest_role_name": "Guest",
                "verified_role_name": "Verified",
                "rules_channel_name": "rules",
                "roles_channel_name": "reaction-roles",
                "admin_channel_name": "council-chat",
                "admin_role_name": "Staff"
            }
    except Exception as e:
        logging.error(f"Error getting guild verification settings: {e}")
        return None

def update_guild_verification_settings(guild_id: int, settings: dict):
    """
    Update verification settings for a guild.
    
    Args:
        guild_id: The Discord guild ID
        settings: Dictionary containing the settings to update
    """
    try:
        collection = get_guild_verification_settings_collection()
        settings["guild_id"] = guild_id
        logging.debug(f"Updating settings for guild_id: {guild_id} (type: {type(guild_id)})")
        logging.debug(f"Settings being stored: {settings}")
        collection.find_one_and_update(
            {"guild_id": guild_id},
            {"$set": settings},
            upsert=True
        )
        logging.info(f"Updated verification settings for guild {guild_id}")
    except Exception as e:
        logging.error(f"Error updating guild verification settings: {e}")

def toggle_guild_verification(guild_id: int, enabled: bool):
    """
    Toggle verification system for a guild.
    
    Args:
        guild_id: The Discord guild ID
        enabled: Whether to enable or disable verification
    """
    try:
        collection = get_guild_verification_settings_collection()
        collection.find_one_and_update(
            {"guild_id": guild_id},
            {"$set": {"enabled": enabled}},
            upsert=True
        )
        logging.info(f"Toggled verification for guild {guild_id} to {enabled}")
    except Exception as e:
        logging.error(f"Error toggling guild verification: {e}")

def update_guild_channel_settings(guild_id: int, channel_type: str, channel_name: str):
    """
    Update a specific channel setting for a guild.
    
    Args:
        guild_id: The Discord guild ID
        channel_type: Type of channel (rules, roles, admin)
        channel_name: New channel name
    """
    try:
        collection = get_guild_verification_settings_collection()
        channel_key = f"{channel_type}_channel_name"
        collection.find_one_and_update(
            {"guild_id": guild_id},
            {"$set": {channel_key: channel_name}},
            upsert=True
        )
        logging.info(f"Updated {channel_type} channel for guild {guild_id} to {channel_name}")
    except Exception as e:
        logging.error(f"Error updating guild channel settings: {e}")

def update_guild_role_settings(guild_id: int, role_type: str, role_name: str):
    """
    Update a specific role setting for a guild.
    
    Args:
        guild_id: The Discord guild ID
        role_type: Type of role (guest, verified, admin)
        role_name: New role name
    """
    try:
        collection = get_guild_verification_settings_collection()
        role_key = f"{role_type}_role_name"
        collection.find_one_and_update(
            {"guild_id": guild_id},
            {"$set": {role_key: role_name}},
            upsert=True
        )
        logging.info(f"Updated {role_type} role for guild {guild_id} to {role_name}")
    except Exception as e:
        logging.error(f"Error updating guild role settings: {e}")

def get_active_verifications_collection():
    """Get the active verifications collection."""
    database = get_db_connection()
    if database is None:
        return None
    try:
        collection = database.get_collection("active_verifications")
        logging.debug(f"Retrieved active_verifications collection: {collection.info().name}")
        return collection
    except Exception as e:
        logging.error(f"[ERROR] Failed to retrieve active_verifications collection: {e}")
        return None

def save_active_verification(user_id: int, guild_id: int, channel_id: int, data: dict):
    """
    Save or update an active verification session.
    
    Args:
        user_id: Discord user ID
        guild_id: Discord guild ID
        channel_id: Temporary verification channel ID
        data: Additional verification data including:
            - username: str
            - stage: str
            - selected_roles: list
            - started_at: datetime
            - last_updated: datetime
            - expires_at: datetime
    """
    try:
        collection = get_active_verifications_collection()
        if collection is None:
            return

        document = {
            "user_id": user_id,
            "guild_id": guild_id,
            "channel_id": channel_id,
            **data
        }
        
        collection.find_one_and_update(
            {"user_id": user_id, "guild_id": guild_id},
            {"$set": document},
            upsert=True
        )
        logging.debug(f"Saved active verification for user {user_id} in guild {guild_id}")
    except Exception as e:
        logging.error(f"Error saving active verification: {e}")

def get_active_verification(user_id: int, guild_id: int):
    """
    Get an active verification session.
    
    Args:
        user_id: Discord user ID
        guild_id: Discord guild ID
        
    Returns:
        dict: Active verification data or None if not found
    """
    try:
        collection = get_active_verifications_collection()
        if collection is None:
            return None
            
        return collection.find_one({
            "user_id": user_id,
            "guild_id": guild_id
        })
    except Exception as e:
        logging.error(f"Error getting active verification: {e}")
        return None

def delete_active_verification(user_id: int, guild_id: int):
    """
    Delete an active verification session.
    
    Args:
        user_id: Discord user ID
        guild_id: Discord guild ID
    """
    try:
        collection = get_active_verifications_collection()
        if collection is None:
            return
            
        collection.delete_one({
            "user_id": user_id,
            "guild_id": guild_id
        })
        logging.debug(f"Deleted active verification for user {user_id} in guild {guild_id}")
    except Exception as e:
        logging.error(f"Error deleting active verification: {e}")

def get_guild_active_verifications(guild_id: int):
    """
    Get all active verifications for a guild.
    
    Args:
        guild_id: Discord guild ID
        
    Returns:
        list: List of active verification documents
    """
    try:
        collection = get_active_verifications_collection()
        if collection is None:
            return []
            
        return list(collection.find({"guild_id": guild_id}))
    except Exception as e:
        logging.error(f"Error getting guild active verifications: {e}")
        return []

def load_all_active_verifications():
    """
    Load all active verifications from the database.
    This is typically called during bot startup.
    
    Returns:
        dict: Dictionary mapping (user_id, guild_id) tuples to verification data
    """
    try:
        collection = get_active_verifications_collection()
        if collection is None:
            return {}
            
        verifications = {}
        for doc in collection.find():
            verifications[(doc["user_id"], doc["guild_id"])] = doc
            
        return verifications
    except Exception as e:
        logging.error(f"Error loading all active verifications: {e}")
        return {}

# Truth and Dare Database Functions
def get_truth_dare_questions_collection():
    """Get the truth_dare_questions collection."""
    database = get_db_connection()
    if database is None:
        return None
    try:
        collection = database.get_collection("truth_dare_questions")
        logging.debug(f"Retrieved truth_dare_questions collection: {collection.info().name}")
        return collection
    except Exception as e:
        logging.error(f"Failed to retrieve truth_dare_questions collection: {e}")
        return None

def get_random_truth_dare_question(question_type: str, rating: str = "PG"):
    """Get a random question from the database."""
    try:
        collection = get_truth_dare_questions_collection()
        if collection is None:
            return None
        
        # Find approved questions of the specified type and rating
        # Note: AstraDB doesn't support $expr for field comparisons in filters,
        # so we filter in Python to keep only questions where positive_feedback >= negative_feedback
        filter_query = {
            "type": question_type, 
            "rating": rating, 
            "approved": True
        }
        all_questions = list(collection.find(filter_query, limit=20))
        
        # Filter in Python: keep only questions where positive_feedback >= negative_feedback
        filtered_questions = [
            q for q in all_questions
            if q.get("positive_feedback", 0) >= q.get("negative_feedback", 0)
        ]
        
        if filtered_questions:
            # Select a random question
            import random
            selected_question = random.choice(filtered_questions)
            
            # Update usage count
            collection.update_one(
                {"_id": selected_question["_id"]},
                {"$inc": {"usage_count": 1}, "$set": {"last_used": datetime.datetime.utcnow().isoformat()}}
            )
            return selected_question
        return None
    except Exception as e:
        logging.error(f"Error getting random truth/dare question: {e}")
        return None

def save_truth_dare_question(guild_id: str, user_id: str, question: str, 
                           question_type: str, rating: str, source: str, 
                           submitted_by: str = None, guild_name: str = None,
                           command_name: str = None, username: str = None):
    """Save a truth/dare question to the database and return the document ID."""
    try:
        collection = get_truth_dare_questions_collection()
        if collection is None:
            return None
        
        now = datetime.datetime.utcnow().isoformat()
        document = {
            "guild_id": guild_id,
            "user_id": user_id,
            "question": question,
            "type": question_type,
            "rating": rating,
            "source": source,
            "submitted_by": submitted_by or "Unknown",
            "approved": True,  # Auto-approve all questions, let feedback system handle quality control
            "positive_feedback": 0,
            "negative_feedback": 0,
            "usage_count": 0,
            "created_at": now,
            "last_used": now,  # Set to created_at for new questions
            "message_metadata": [],  # Array to store message metadata for reaction tracking
            "guild_name": guild_name,
            "command_name": command_name,
            "username": username
        }
        
        result = collection.insert_one(document)
        logging.debug(f"Saved truth/dare question: {question_type} - {question[:50]}... with ID: {result.inserted_id}")
        return str(result.inserted_id)
    except Exception as e:
        logging.error(f"Error saving truth/dare question: {e}")
        return None

# Confession-related database operations

def get_confession_settings(guild_id: int) -> dict:
    """
    Get confession settings for a guild from registered_servers collection.
    
    Returns:
        dict: Confession settings including:
            - confession_enabled: bool
            - confession_channel_id: str
            - confession_admin_channel_id: str
            - confession_approval_required: bool
            - confession_auto_approve_enabled: bool
            - confession_counter: int
    """
    try:
        collection = get_registered_servers_collection()
        if collection is None:
            return None
        
        result = collection.find_one({"guild_id": str(guild_id)})
        if result:
            return {
                "confession_enabled": result.get("confession_enabled", False),
                "confession_channel_id": result.get("confession_channel_id"),
                "confession_admin_channel_id": result.get("confession_admin_channel_id"),
                "confession_approval_required": result.get("confession_approval_required", True),
                "confession_auto_approve_enabled": result.get("confession_auto_approve_enabled", False),
                "confession_counter": result.get("confession_counter", 0)
            }
        return None
    except Exception as e:
        logging.error(f"Error getting confession settings: {e}")
        return None

def update_confession_settings(guild_id: int, settings: dict):
    """
    Update confession settings for a guild in registered_servers collection.
    
    Args:
        guild_id: The Discord guild ID
        settings: Dictionary containing settings to update
    """
    try:
        collection = get_registered_servers_collection()
        if collection is None:
            return
        
        collection.find_one_and_update(
            {"guild_id": str(guild_id)},
            {"$set": settings},
            upsert=True
        )
        logging.info(f"Updated confession settings for guild {guild_id}")
    except Exception as e:
        logging.error(f"Error updating confession settings: {e}")

def get_next_confession_id(guild_id: int) -> int:
    """
    Atomically increment and return the next confession ID for a guild.
    
    Args:
        guild_id: The Discord guild ID
        
    Returns:
        int: Next confession ID (1-indexed)
    """
    try:
        collection = get_registered_servers_collection()
        if collection is None:
            return 1
        
        result = collection.find_one_and_update(
            {"guild_id": str(guild_id)},
            {"$inc": {"confession_counter": 1}},
            upsert=True,
            return_document="after"  # Must be string "after" or "before", not boolean
        )
        
        # If upsert created new document, counter starts at 1
        # Otherwise, return the incremented value
        if result:
            counter = result.get("confession_counter", 1)
            logging.info(f"Next confession ID for guild {guild_id}: {counter}")
            return counter
        else:
            # Fallback: if result is None, try to get current value and increment manually
            logging.warning(f"find_one_and_update returned None for guild {guild_id}, using fallback")
            existing = collection.find_one({"guild_id": str(guild_id)})
            if existing:
                current_counter = existing.get("confession_counter", 0)
                new_counter = current_counter + 1
                collection.update_one(
                    {"guild_id": str(guild_id)},
                    {"$set": {"confession_counter": new_counter}}
                )
                logging.info(f"Fallback: Next confession ID for guild {guild_id}: {new_counter}")
                return new_counter
            else:
                # First confession for this guild
                collection.update_one(
                    {"guild_id": str(guild_id)},
                    {"$set": {"confession_counter": 1}},
                    upsert=True
                )
                logging.info(f"First confession for guild {guild_id}: 1")
                return 1
    except Exception as e:
        logging.error(f"Error getting next confession ID: {e}")
        return 1

def save_confession(user_id: str, username: str, guild_id: str, guild_name: str,
                   confession_text: str, confession_id: int, sentiment_data: dict,
                   channel_id: str = None) -> str:
    """
    Save a confession to user_requests collection with request_type="confession".
    
    Args:
        user_id: User ID who submitted confession
        username: User display name
        guild_id: Guild ID
        guild_name: Guild name
        confession_text: Confession content
        confession_id: Guild-specific confession ID
        sentiment_data: Sentiment analysis results
        channel_id: Channel ID where confession was submitted
        
    Returns:
        str: Document ID or None if failed
    """
    try:
        collection = get_user_requests_collection()
        if collection is None:
            return None
        
        document = {
            "user_id": str(user_id),
            "username": username,
            "guild_id": guild_id,
            "guild_name": guild_name,
            "timestamp": datetime.datetime.utcnow().isoformat(),
            "channel_id": channel_id,
            "question": confession_text,  # Repurposed field
            "response": "pending",  # Repurposed field (status)
            "request_type": "confession",
            "confession_id": confession_id,
            "sentiment_score": sentiment_data.get("score", 0.0),
            "sentiment_category": sentiment_data.get("category", "neutral"),
            "sentiment_confidence": sentiment_data.get("confidence", "low"),
            "sentiment_details": sentiment_data.get("details", {}),
            "auto_approved": sentiment_data.get("auto_approve", False)
        }
        
        result = collection.insert_one(document)
        logging.debug(f"Confession saved: ID #{confession_id} for user {user_id}")
        return str(result.inserted_id)
    except Exception as e:
        logging.error(f"Error saving confession: {e}")
        return None

def update_confession_status(confession_id: int, guild_id: str, status: str,
                            admin_id: str = None, admin_username: str = None,
                            rejection_reason: str = None):
    """
    Update confession status in user_requests collection.
    
    Args:
        confession_id: Confession ID
        guild_id: Guild ID
        status: New status (approved/rejected)
        admin_id: Admin user ID who reviewed
        admin_username: Admin display name
        rejection_reason: Optional rejection reason
    """
    try:
        collection = get_user_requests_collection()
        if collection is None:
            return
        
        update_data = {
            "response": status,  # Repurposed field
            "reviewed_at": datetime.datetime.utcnow().isoformat()
        }
        
        if admin_id:
            update_data["admin_id"] = str(admin_id)
        if admin_username:
            update_data["admin_username"] = admin_username
        if rejection_reason:
            update_data["rejection_reason"] = rejection_reason
        
        collection.update_one(
            {"confession_id": confession_id, "guild_id": guild_id, "request_type": "confession"},
            {"$set": update_data}
        )
        logging.debug(f"Updated confession #{confession_id} status to {status}")
    except Exception as e:
        logging.error(f"Error updating confession status: {e}")

def get_confession_by_id(confession_id: int, guild_id: str) -> dict:
    """
    Get confession by ID from user_requests collection.
    
    Args:
        confession_id: Confession ID
        guild_id: Guild ID
        
    Returns:
        dict: Confession document or None
    """
    try:
        collection = get_user_requests_collection()
        if collection is None:
            return None
        
        result = collection.find_one({
            "confession_id": confession_id,
            "guild_id": guild_id,
            "request_type": "confession"
        })
        return result
    except Exception as e:
        logging.error(f"Error getting confession by ID: {e}")
        return None

def get_truth_dare_question_by_id(question_id: str):
    """Get a specific question by its ID."""
    try:
        collection = get_truth_dare_questions_collection()
        if collection is None:
            return None
        
        question = collection.find_one({"_id": question_id})
        return question
    except Exception as e:
        logging.error(f"Error getting question by ID: {e}")
        return None

def update_question_last_used(question_id: str):
    """Update the last_used timestamp when a question is presented in UI."""
    try:
        if not question_id:
            return
        collection = get_truth_dare_questions_collection()
        if collection is None:
            return
        
        collection.update_one(
            {"_id": question_id},
            {"$set": {"last_used": datetime.datetime.utcnow().isoformat()}}
        )
    except Exception as e:
        logging.error(f"Error updating question last_used: {e}")

def record_question_feedback(question_id: str, feedback: str):
    """Record feedback for a question."""
    try:
        collection = get_truth_dare_questions_collection()
        if collection is None:
            return False
        
        # Update feedback counters
        if feedback == "positive":
            collection.update_one(
                {"_id": question_id},
                {"$inc": {"positive_feedback": 1}}
            )
        elif feedback == "negative":
            collection.update_one(
                {"_id": question_id},
                {"$inc": {"negative_feedback": 1}}
            )
        
        logging.debug(f"Recorded {feedback} feedback for question {question_id}")
        return True
    except Exception as e:
        logging.error(f"Error recording question feedback: {e}")
        return False

def add_message_metadata(question_id: str, message_id: str, guild_id: str, channel_id: str):
    """Add message metadata to existing question record for reaction tracking."""
    try:
        collection = get_truth_dare_questions_collection()
        if collection is None:
            return False
        
        # Create message metadata object
        message_metadata = {
            "message_id": message_id,
            "guild_id": guild_id,
            "channel_id": channel_id,
            "created_at": datetime.datetime.utcnow().isoformat()
        }
        
        # Add to message_metadata array in the question document
        collection.update_one(
            {"_id": question_id},
            {"$push": {"message_metadata": message_metadata}}
        )
        
        logging.debug(f"Added message metadata to question {question_id}: {message_id}")
        return True
    except Exception as e:
        logging.error(f"Error adding message metadata: {e}")
        return False

def get_truth_dare_message_metadata(message_id: str):
    """Get truth/dare message metadata by message ID from question records.
    
    Note: AstraDB doesn't support $elemMatch for array queries, so we use Python-side filtering.
    This is the most efficient approach available for AstraDB's current capabilities.
    """
    try:
        collection = get_truth_dare_questions_collection()
        if collection is None:
            return None
        
        # Query documents with non-empty message_metadata arrays
        # This is the only array querying approach that works in AstraDB
        # Performance note: This queries all documents with message_metadata, then filters in Python
        # For better performance, consider adding an index on message_metadata if query volume is high
        all_docs = collection.find({"message_metadata": {"$exists": True, "$ne": []}})
        
        for question_doc in all_docs:
            # Find the specific message metadata within the array
            for metadata in question_doc.get("message_metadata", []):
                if metadata.get("message_id") == message_id:
                    # Return metadata with question_id for compatibility
                    metadata["question_id"] = str(question_doc["_id"])
                    logging.debug(f"Found message metadata for {message_id} in question {question_doc['_id']}")
                    return metadata
        
        logging.debug(f"No message metadata found for message_id: {message_id}")
        return None
    except Exception as e:
        logging.error(f"Error getting truth/dare message metadata: {e}")
        return None