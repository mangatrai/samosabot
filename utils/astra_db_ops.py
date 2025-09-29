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
def update_user_stats(user_id, username, correct_increment=0, wrong_increment=0):
    """Update user statistics and leaderboard in AstraDB, incrementing by 1."""
    try:
        collection = get_trivia_leaderboard_collection()
        existing_doc = collection.find_one({"user_id": user_id})

        update_data = {"$set": {"username": username}}
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
def insert_user_request(user_id, question, response):
    """Insert a user request into the user_requests collection."""
    try:
        collection = get_user_requests_collection()
        document = {
            "user_id": str(user_id),
            "question": question,
            "response": response,
            "timestamp": datetime.datetime.utcnow().isoformat()
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
    """Retrieve the daily request count for a user."""
    today = datetime.date.today().isoformat()
    try:
        collection = get_daily_counters_collection()
        result = collection.find_one({"user_id": str(user_id), "date": today})
        return result.get("count", 0) if result else 0
    except Exception as e:
        logging.error(f"Error retrieving daily request count: {e}")
        return 0

def increment_daily_request_count(user_id):
    """Increment the daily request count for a user."""
    today = datetime.date.today().isoformat()
    try:
        collection = get_daily_counters_collection()
        collection.find_one_and_update(
            {"user_id": str(user_id), "date": today},
            {"$inc": {"count": 1}},
            upsert=True,
        )
        logging.debug(f"Daily request count incremented for User ID {user_id}")
    except Exception as e:
        logging.error(f"Error incrementing daily request count: {e}")

def register_or_update_guild(guild_id: int, guild_name: str,status):
    """
    Register a guild by saving its ID, name, installation date, status, and last updated date.
    
    If the guild is not already registered, insert a new record with:
      - installed_at: current UTC time
      - status: "JOINED"
      - lastupdatedat: current UTC time
    If the guild already exists, update its guild_name, set status to "JOINED", and update lastupdatedat
    to the current UTC time.
    """
    collection = get_registered_servers_collection()
    if collection is None:
        return
    try:
        now = datetime.datetime.utcnow().isoformat()
        existing_record = collection.find_one({"guild_id": str(guild_id)})
        if not existing_record:
            # Insert new record
            document = {
                "guild_id": str(guild_id),
                "guild_name": guild_name,
                "installed_at": now,
                "status": status,
                "lastupdatedat": now
            }
            collection.insert_one(document)
            logging.debug(f"Inserted new guild record: {guild_name} ({guild_id}) at {now}")
        else:
            # Update existing record: update guild_name, set status to "JOINED", and update lastupdatedat.
            collection.update_one(
                {"guild_id": str(guild_id)},
                {"$set": {
                    "guild_name": guild_name,
                    "status": status,
                    "lastupdatedat": now
                }}
            )
            logging.debug(f"Updated guild record: {guild_name} ({guild_id}) with lastupdatedat {now}")
    except Exception as e:
        logging.error(f"Error in register_or_update_guild: {e}")

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
        
        # Find all questions of the specified type and rating with positive feedback >= negative feedback
        filter_query = {
            "type": question_type, 
            "rating": rating, 
            "approved": True,
            "$expr": {"$gte": ["$positive_feedback", "$negative_feedback"]}
        }
        all_questions = list(collection.find(filter_query))
        
        if all_questions:
            # Select a random question
            import random
            selected_question = random.choice(all_questions)
            
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
                           submitted_by: str = None):
    """Save a truth/dare question to the database and return the document ID."""
    try:
        collection = get_truth_dare_questions_collection()
        if collection is None:
            return None
        
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
            "created_at": datetime.datetime.utcnow().isoformat(),
            "last_used": None
        }
        
        result = collection.insert_one(document)
        logging.debug(f"Saved truth/dare question: {question_type} - {question[:50]}... with ID: {result.inserted_id}")
        return str(result.inserted_id)
    except Exception as e:
        logging.error(f"Error saving truth/dare question: {e}")
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

def save_truth_dare_message(message_id: str, question_id: str, guild_id: str, channel_id: str):
    """Save truth/dare message metadata for reaction tracking."""
    try:
        collection = get_truth_dare_questions_collection()
        if collection is None:
            return False
        
        # Store message metadata in a separate document
        message_doc = {
            "message_id": message_id,
            "question_id": question_id,
            "guild_id": guild_id,
            "channel_id": channel_id,
            "created_at": datetime.datetime.utcnow().isoformat()
        }
        
        collection.insert_one(message_doc)
        logging.debug(f"Saved truth/dare message metadata: {message_id} -> {question_id}")
        return True
    except Exception as e:
        logging.error(f"Error saving truth/dare message metadata: {e}")
        return False

def get_truth_dare_message_metadata(message_id: str):
    """Get truth/dare message metadata by message ID."""
    try:
        collection = get_truth_dare_questions_collection()
        if collection is None:
            return None
        
        # Find message metadata document
        message_doc = collection.find_one({"message_id": message_id})
        return message_doc
    except Exception as e:
        logging.error(f"Error getting truth/dare message metadata: {e}")
        return None