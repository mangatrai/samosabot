"""
AstraDB Collection Creation Script

This script handles the creation of all necessary collections in AstraDB for the Discord bot.
It provides functions to create individual collections and a main function to create all collections at once.
"""

import logging
import os
import sys
from db_connection import get_db_connection, ASTRA_NAMESPACE

# Add the parent directory to the Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def _get_existing_collection_names(database) -> list:
    """Return names of all existing collections in the database."""
    try:
        return [c.name for c in database.list_collections()]
    except Exception as e:
        logging.warning(f"Could not list existing collections: {e}")
        return []

def create_collection(collection_name: str):
    """Create a single collection in AstraDB if it doesn't exist."""
    try:
        database = get_db_connection()
        if database is None:
            return False

        # list_collections() is the correct way to check existence.
        # get_collection() never raises even if the collection is missing,
        # so it cannot be used as an existence check.
        existing = _get_existing_collection_names(database)
        if collection_name in existing:
            logging.info(f"Collection '{collection_name}' already exists — skipping")
            return True

        database.create_collection(
            name=collection_name,
            keyspace=ASTRA_NAMESPACE
        )
        logging.info(f"Successfully created collection: {collection_name}")
        return True
    except Exception as e:
        logging.error(f"Failed to create collection {collection_name}: {e}")
        return False

def create_qotd_collections():
    """Create collections related to Question of the Day feature."""
    collections = [
        "qotd_channels",
        "bot_status_channels"
    ]
    for collection in collections:
        create_collection(collection)

def create_trivia_collections():
    """Create collections related to Trivia game feature."""
    collections = [
        "trivia_leaderboard"
    ]
    for collection in collections:
        create_collection(collection)

def create_verification_collections():
    """Create collections related to Verification system."""
    collections = [
        "verification_attempts",
        "guild_verification_settings",
        "active_verifications",   # tracks in-progress verification sessions
    ]
    for collection in collections:
        create_collection(collection)

def create_user_collections():
    """Create collections related to user data."""
    collections = [
        "user_requests",
        "daily_counters"
    ]
    for collection in collections:
        create_collection(collection)

def create_server_collections():
    """Create collections related to server/guild data."""
    collections = [
        "registered_servers"
    ]
    for collection in collections:
        create_collection(collection)

def create_truth_dare_collections():
    """Create collections related to Truth and Dare game."""
    collections = [
        "truth_dare_questions"
    ]
    for collection in collections:
        create_collection(collection)

def create_all_collections():
    """Create all collections for the Discord bot."""
    logging.info("Starting collection creation process...")
    
    # Create collections for each feature
    create_qotd_collections()
    create_trivia_collections()
    create_verification_collections()
    create_user_collections()
    create_server_collections()
    create_truth_dare_collections()
    
    logging.info("Collection creation process completed!")

def main():
    """Main function to run the collection creation script."""
    logging.info("Starting AstraDB Collection Creation Script")
    
    # Create all collections
    create_all_collections()

if __name__ == "__main__":
    main() 