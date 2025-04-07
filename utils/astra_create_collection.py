"""
AstraDB Collection Creation Script

This script handles the creation of all necessary collections in AstraDB for the Discord bot.
It provides functions to create individual collections and a main function to create all collections at once.
"""

import logging
import os
import sys
from .db_connection import get_db_connection, ASTRA_NAMESPACE

# Add the parent directory to the Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def create_collection(collection_name: str):
    """Create a single collection in AstraDB if it doesn't exist."""
    try:
        database = get_db_connection()
        if database is None:
            return False

        # Create collection with check_exists=True
        database.create_collection(
            name=collection_name,
            keyspace=ASTRA_NAMESPACE,
            check_exists=True
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
        "role_changes",
        "guild_verification_settings"
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

def create_all_collections():
    """Create all collections for the Discord bot."""
    logging.info("Starting collection creation process...")
    
    # Create collections for each feature
    create_qotd_collections()
    create_trivia_collections()
    create_verification_collections()
    create_user_collections()
    create_server_collections()
    
    logging.info("Collection creation process completed!")

def main():
    """Main function to run the collection creation script."""
    logging.info("Starting AstraDB Collection Creation Script")
    
    # Create all collections
    create_all_collections()

if __name__ == "__main__":
    main() 