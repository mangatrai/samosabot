"""
Database Connection Factory

Returns a database connection for the configured provider.
Set DATABASE_PROVIDER env var to select the backend:

  DATABASE_PROVIDER=ASTRA    (default) — AstraDB via astrapy
  DATABASE_PROVIDER=MONGODB           — MongoDB Atlas via pymongo

The returned object exposes get_collection(name) which returns a collection
supporting the astrapy-compatible API used throughout astra_db_ops.py.
"""

import os
import logging


def get_db_connection():
    """
    Return a database connection for the active provider.

    Returns:
        astrapy.Database        when DATABASE_PROVIDER=ASTRA (or unset)
        MongoDatabaseAdapter    when DATABASE_PROVIDER=MONGODB
        None on connection failure.
    """
    provider = os.getenv("DATABASE_PROVIDER", "ASTRA").upper().strip()

    if provider == "MONGODB":
        from .db_connection_mongodb import get_db_connection as _get
        logging.debug("Database provider: MongoDB Atlas")
    else:
        if provider != "ASTRA":
            logging.warning(
                "Unknown DATABASE_PROVIDER '%s' — falling back to ASTRA", provider
            )
        from .db_connection_astra import get_db_connection as _get
        logging.debug("Database provider: AstraDB")

    return _get()
