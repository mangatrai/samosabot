"""
MongoDB Atlas Connection Module

Provides a pymongo-backed database connection that exposes the same collection
API surface as astrapy, so astra_db_ops.py works unchanged regardless of provider.

Called by the db_connection factory when DATABASE_PROVIDER=MONGODB.

Required env var: MONGODB_URI  (mongodb+srv://user:pass@cluster.mongodb.net/)
Optional env var: MONGODB_DB_NAME (default: samosabot)
"""

import os
import logging
from dotenv import load_dotenv

load_dotenv()

MONGODB_URI = os.getenv("MONGODB_URI")
MONGODB_DB_NAME = os.getenv("MONGODB_DB_NAME", "samosabot")


# ---------------------------------------------------------------------------
# Adapter: makes a pymongo Collection look like an astrapy Collection
# ---------------------------------------------------------------------------

class MongoCollectionAdapter:
    """
    Wraps a pymongo Collection to expose the astrapy-compatible call signatures
    used throughout astra_db_ops.py:

      - find(filter, *, sort=dict, limit=int, skip=int)
        astrapy accepts these as kwargs; pymongo uses cursor chaining.

      - find_one_and_update(..., return_document="after"/"before")
        astrapy accepts strings; pymongo requires ReturnDocument constants.

    All other methods (find_one, insert_one, update_one, delete_one,
    delete_many) have identical signatures in both libraries and pass through
    directly to pymongo.
    """

    def __init__(self, collection):
        self._coll = collection

    # --- read ---

    def find(self, filter=None, *, sort=None, limit=None, skip=None, **_kwargs):
        """
        astrapy-compatible find. Translates sort dict and limit/skip kwargs
        into pymongo cursor chaining.
        """
        cursor = self._coll.find(filter or {})
        if sort:
            # astrapy sort: {"field": -1}  →  pymongo: [("field", -1)]
            cursor = cursor.sort(list(sort.items()))
        if skip:
            cursor = cursor.skip(skip)
        if limit:
            cursor = cursor.limit(limit)
        return cursor

    def find_one(self, filter=None, **_kwargs):
        return self._coll.find_one(filter or {})

    # --- write ---

    def insert_one(self, document):
        return self._coll.insert_one(document)

    def update_one(self, filter, update, upsert=False, **_kwargs):
        return self._coll.update_one(filter, update, upsert=upsert)

    def find_one_and_update(self, filter, update, upsert=False,
                            return_document=None, **_kwargs):
        """
        astrapy-compatible find_one_and_update. Accepts return_document as
        either the astrapy string ("after"/"before") or a pymongo
        ReturnDocument constant — both are handled correctly.
        """
        from pymongo import ReturnDocument
        kwargs = {"upsert": upsert}
        if return_document is not None:
            if return_document in ("after", ReturnDocument.AFTER):
                kwargs["return_document"] = ReturnDocument.AFTER
            elif return_document in ("before", ReturnDocument.BEFORE):
                kwargs["return_document"] = ReturnDocument.BEFORE
        return self._coll.find_one_and_update(filter, update, **kwargs)

    def delete_one(self, filter):
        return self._coll.delete_one(filter)

    def delete_many(self, filter=None):
        return self._coll.delete_many(filter or {})


# ---------------------------------------------------------------------------
# Adapter: makes a pymongo Database look like an astrapy Database
# ---------------------------------------------------------------------------

class MongoDatabaseAdapter:
    """
    Wraps a pymongo Database so that get_collection() returns a
    MongoCollectionAdapter rather than a raw pymongo Collection.
    """

    def __init__(self, db):
        self._db = db

    def get_collection(self, name: str) -> MongoCollectionAdapter:
        return MongoCollectionAdapter(self._db[name])


# ---------------------------------------------------------------------------
# Connection
# ---------------------------------------------------------------------------

def get_db_connection():
    """
    Connect to MongoDB Atlas and return a MongoDatabaseAdapter.

    Returns:
        MongoDatabaseAdapter, or None if connection fails.
    """
    try:
        import pymongo  # noqa: PLC0415 — optional dependency
    except ImportError:
        logging.error("pymongo is not installed. Run: pip install pymongo")
        return None

    try:
        if not MONGODB_URI:
            logging.error("Missing required MongoDB configuration (MONGODB_URI)")
            return None

        client = pymongo.MongoClient(MONGODB_URI, serverSelectionTimeoutMS=8000)
        client.server_info()  # raises if connection fails
        db = client[MONGODB_DB_NAME]
        logging.debug("MongoDB connection established (database: %s)", MONGODB_DB_NAME)
        return MongoDatabaseAdapter(db)
    except Exception as e:
        logging.error("Error establishing MongoDB connection: %s", e)
        return None
