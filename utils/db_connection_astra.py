"""
AstraDB Connection Module

Establishes a connection to AstraDB using the Data API client.
Called by the db_connection factory when DATABASE_PROVIDER=ASTRA (the default).

Required env vars: ASTRA_API_ENDPOINT, ASTRA_API_TOKEN
Optional env var:  ASTRA_NAMESPACE (default: default_keyspace)
"""

import os
from dotenv import load_dotenv
import logging
from astrapy import DataAPIClient

load_dotenv()

ASTRA_API_ENDPOINT = os.getenv("ASTRA_API_ENDPOINT")
ASTRA_NAMESPACE = os.getenv("ASTRA_NAMESPACE", "default_keyspace")
ASTRA_API_TOKEN = os.getenv("ASTRA_API_TOKEN")


def get_db_connection():
    """
    Connect to AstraDB and return the Database object.

    Returns:
        astrapy.Database, or None if connection fails.
    """
    try:
        if not all([ASTRA_API_ENDPOINT, ASTRA_NAMESPACE, ASTRA_API_TOKEN]):
            logging.error("Missing required AstraDB configuration (ASTRA_API_ENDPOINT, ASTRA_API_TOKEN)")
            return None

        client = DataAPIClient(ASTRA_API_TOKEN)
        database = client.get_database(ASTRA_API_ENDPOINT, keyspace=ASTRA_NAMESPACE)
        logging.debug("AstraDB connection established (keyspace: %s)", ASTRA_NAMESPACE)
        return database
    except Exception as e:
        logging.error("Error establishing AstraDB connection: %s", e)
        return None
