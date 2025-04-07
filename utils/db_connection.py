"""
Database Connection Module

This module provides a centralized way to establish and manage connections to AstraDB.
It handles the connection setup using environment variables and provides a single point
of access for database operations.
"""

import os
from dotenv import load_dotenv
import logging
from astrapy import DataAPIClient

# Load environment variables
load_dotenv()

# Get AstraDB configuration from environment variables
ASTRA_API_ENDPOINT = os.getenv("ASTRA_API_ENDPOINT")
ASTRA_NAMESPACE = os.getenv("ASTRA_NAMESPACE")
ASTRA_API_TOKEN = os.getenv("ASTRA_API_TOKEN")

def get_db_connection():
    """
    Get a connection to AstraDB.
    
    Returns:
        Database: A connection to the AstraDB database, or None if connection fails.
    """
    try:
        if not all([ASTRA_API_ENDPOINT, ASTRA_NAMESPACE, ASTRA_API_TOKEN]):
            logging.error("Missing required AstraDB configuration")
            return None
            
        # Initialize the client and get a "Database" object
        client = DataAPIClient(ASTRA_API_TOKEN)
        database = client.get_database(ASTRA_API_ENDPOINT, keyspace=ASTRA_NAMESPACE)
        logging.debug(f"Database connection established: {database.info().name}")
        return database
    except Exception as e:
        logging.error(f"Error establishing database connection: {e}")
        return None 