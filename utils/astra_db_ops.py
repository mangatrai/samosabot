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

from astrapy import DataAPIClient
from astrapy.constants import VectorMetric
import os
from dotenv import load_dotenv
import logging
import datetime

# Load environment variables
load_dotenv()

# Load environment variables for AstraDB
ASTRA_API_ENDPOINT = os.getenv("ASTRA_API_ENDPOINT")  # AstraDB API endpoint
ASTRA_NAMESPACE = os.getenv("ASTRA_NAMESPACE")  # Your namespace (like a database)
ASTRA_API_TOKEN = os.getenv("ASTRA_API_TOKEN")  # API authentication token

# Function to get a database connection
def get_db_connection():
    try:
        # Initialize the client and get a "Database" object
        client = DataAPIClient(ASTRA_API_TOKEN)
        database = client.get_database(ASTRA_API_ENDPOINT, keyspace=ASTRA_NAMESPACE)
        logging.debug(f"Database connection established: {database.info().name}")
        return database
    except Exception as e:
        logging.error(f"Error establishing database connection: {e}")
        return None

# Function to create collections
def create_qotd_channels_collection():
    """Creates the qotd_channels collection."""
    try:
        get_db_connection().create_collection("qotd_channels")
        logging.debug("qotd_channels collection created successfully.")
    except Exception as e:
        logging.error(f"Error creating qotd_channels collection: {e}")

def create_bot_status_channels_collection():
    """Creates the bot_status_channels collection."""
    try:
        get_db_connection().create_collection("bot_status_channels")
        logging.debug("bot_status_channels collection created successfully.")
    except Exception as e:
        logging.error(f"Error creating bot_status_channels collection: {e}")

def create_trivia_leaderboard_collection():
    """Creates the trivia_leaderboard collection."""
    try:
        get_db_connection().create_collection("trivia_leaderboard")
        logging.debug("trivia_leaderboard collection created successfully.")
    except Exception as e:
        logging.error(f"Error creating trivia_leaderboard collection: {e}")

def create_user_requests_collection():
    """Creates the user_requests collection."""
    try:
        get_db_connection().create_collection("user_requests")
        logging.debug("user_requests collection created successfully.")
    except Exception as e:
        logging.error(f"Error creating user_requests collection: {e}")

def create_daily_counters_collection():
    """Creates the daily_counters collection."""
    try:
        get_db_connection().create_collection("daily_counters")
        logging.debug("daily_counters collection created successfully.")
    except Exception as e:
        logging.error(f"Error creating daily_counters collection: {e}")

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