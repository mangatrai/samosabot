from astrapy import DataAPIClient
from astrapy.constants import VectorMetric
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Load environment variables for AstraDB
ASTRA_API_ENDPOINT = os.getenv("ASTRA_API_ENDPOINT")  # AstraDB API endpoint
ASTRA_NAMESPACE = os.getenv("ASTRA_NAMESPACE")  # Your namespace (like a database)
ASTRA_API_TOKEN = os.getenv("ASTRA_API_TOKEN")  # API authentication token

# Function to get a database connection
def get_db_connection():
    # Initialize the client and get a "Database" object
    client = DataAPIClient(ASTRA_API_TOKEN)
    database = client.get_database(ASTRA_API_ENDPOINT, keyspace=ASTRA_NAMESPACE)
    #print(f"* Database: {database.info().name}\n")
    return database

# Function to create collections
def create_qotd_channels_collection():
    """Creates the qotd_channels collection."""
    try:
        get_db_connection().create_collection("qotd_channels")
        print("qotd_channels collection created successfully.")
    except Exception as e:
        print(f"Error creating qotd_channels collection: {e}")

def create_bot_status_channels_collection():
    """Creates the bot_status_channels collection."""
    try:
        get_db_connection().create_collection("bot_status_channels")
        print("bot_status_channels collection created successfully.")
    except Exception as e:
        print(f"Error creating bot_status_channels collection: {e}")

def create_trivia_leaderboard_collection():
    """Creates the trivia_leaderboard collection."""
    try:
        get_db_connection().create_collection("trivia_leaderboard")
        print("trivia_leaderboard collection created successfully.")
    except Exception as e:
        print(f"Error creating trivia_leaderboard collection: {e}")

# Function to get qotd channels collection
def get_qotd_channels_collection():
    # Get the collection
    collection = get_db_connection().get_collection("qotd_channels")
    #print(f"* Collection: {collection.info().name}\n")
    return collection

# Function to get bot status channels collection
def get_bot_status_channels_collection():
    # Get the collection
    collection = get_db_connection().get_collection("bot_status_channels")
    #print(f"* Collection: {collection.info().name}\n")
    return collection

# Function to get trivia questions collection
def get_trivia_leaderboard_collection():
    # Get the collection
    collection = get_db_connection().get_collection("trivia_leaderboard")
    #print(f"* Collection: {collection.info().name}\n")
    return collection

#Function to load qotd schedules
def load_qotd_schedules():
    """Load scheduled QOTD channels from AstraDB."""
    try:
        # Fetch all documents from the collection
        results = get_qotd_channels_collection().find({})

        # Convert results into a dictionary {guild_id: channel_id}
        qotd_channels = {doc['guild_id']: doc['channel_id'] for doc in results}

        return qotd_channels  # ✅ Ensure a valid dictionary is returned

    except Exception as e:
        print(f"[ERROR] Failed to load QOTD schedules: {e}")
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
            print(f"Schedule data updated/inserted for guild_id: {schedule_data['guild_id']}")
        else:
            print(f"Schedule data may have been inserted or updated, but no document was returned. Guild ID: {schedule_data['guild_id']}")

    except Exception as e:
        print(f"[ERROR] Failed to save/update QOTD schedules: {e}")


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
        print(f"User stats updated/inserted for user_id: {user_id}")

    except Exception as e:
        print(f"[ERROR] Failed to update user stats: {e}")

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
        print(f"[ERROR] Failed to retrieve user stats: {e}")
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
        print(f"Bot status channel saved/updated for guild_id: {guild_id}")
    except Exception as e:
        print(f"[ERROR] Failed to save/update bot status channel: {e}")

# Load stored bot status channels from AstraDB
def load_bot_status_channels():
    """Load bot status channels from AstraDB."""
    try:
        collection = get_bot_status_channels_collection()
        results = collection.find({})  # Fetch all documents
        return {doc["guild_id"]: doc["channel_id"] for doc in results}
    except Exception as e:
        print(f"[ERROR] Failed to load bot status channels: {e}")
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
        print(f"[ERROR] Failed to retrieve trivia leaderboard: {e}")
        return []

def clean_collection_data(collectionName):
    """Cleans all data from the trivia leaderboard collection."""
    try:
        collection = get_db_connection().get_collection(collectionName)
        # Delete all documents from the collection
        result = collection.delete_many(filter={})
        print(f"Deleted {result.deleted_count} documents from {collectionName}.")

    except Exception as e:
        print(f"Error cleaning trivia leaderboard: {e}")

# Example Usage (if needed):
if __name__ == "__main__":
    clean_collection_data("qotd_channels")
    clean_collection_data("bot_status_channels")
    clean_collection_data("trivia_leaderboard")