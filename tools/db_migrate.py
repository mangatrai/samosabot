#!/usr/bin/env python3
"""
SamosaBot Database Migration Tool

Interactive script for exporting, importing, and migrating data between
supported database providers. Works standalone — does not depend on the
bot's runtime db_connection.py.

Supported providers:
  - AstraDB    (uses astrapy, reads ASTRA_API_ENDPOINT / ASTRA_API_TOKEN)
  - MongoDB    (uses pymongo,  reads MONGODB_URI)

Actions:
  1. Export  — dump collections from a database to local timestamped JSON files
  2. Import  — load collections from local JSON files into a database
  3. Migrate — export from source then import into target (any provider combo)
  4. Schema  — create collections / indexes on a target without moving data

Usage:
    cd /path/to/discord
    python tools/db_migrate.py

Exports land in:  migration_export/<YYYY-MM-DD_HHMMSS>/
Each collection   → <collection_name>.json
Metadata          → _meta.json  (timestamp, provider, record counts)
"""

import datetime
import getpass
import json
import logging
import os
import sys
from abc import ABC, abstractmethod

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

ALL_COLLECTIONS = [
    "registered_servers",
    "user_requests",
    "daily_counters",
    "trivia_leaderboard",
    "truth_dare_questions",
    "qotd_channels",
    "bot_status_channels",
    "verification_attempts",
    "guild_verification_settings",
    "active_verifications",
]

# Indexes to create on MongoDB. AstraDB manages its own indexing.
MONGODB_INDEXES = {
    "registered_servers": [
        {"key": {"guild_id": 1}, "name": "guild_id"},
    ],
    "user_requests": [
        {"key": {"user_id": 1}, "name": "user_id"},
        {"key": {"guild_id": 1, "request_type": 1}, "name": "guild_request_type"},
        {"key": {"confession_id": 1, "guild_id": 1}, "name": "confession_lookup"},
    ],
    "daily_counters": [
        # Not unique — backward-compat rows may lack guild_id
        {"key": {"user_id": 1, "date": 1, "guild_id": 1}, "name": "user_date_guild"},
    ],
    "trivia_leaderboard": [
        {"key": {"user_id": 1}, "name": "user_id"},
        {"key": {"total_correct": -1}, "name": "leaderboard_sort"},
    ],
    "truth_dare_questions": [
        {"key": {"type": 1, "rating": 1, "approved": 1}, "name": "question_lookup"},
    ],
    "qotd_channels": [
        {"key": {"guild_id": 1}, "name": "guild_id"},
    ],
    "bot_status_channels": [
        {"key": {"guild_id": 1}, "name": "guild_id"},
    ],
    "verification_attempts": [
        {"key": {"user_id": 1, "guild_id": 1}, "name": "user_guild"},
    ],
    "guild_verification_settings": [
        {"key": {"guild_id": 1}, "name": "guild_id"},
    ],
    "active_verifications": [
        {"key": {"user_id": 1, "guild_id": 1}, "name": "user_guild"},
    ],
}

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EXPORT_BASE_DIR = os.path.join(PROJECT_ROOT, "migration_export")

CONFLICT_SKIP = "skip"
CONFLICT_OVERWRITE = "overwrite"
CONFLICT_ABORT = "abort"

# ---------------------------------------------------------------------------
# Provider base class
# ---------------------------------------------------------------------------

class DatabaseProvider(ABC):
    """
    Abstract base for database providers. To add a new provider:
      1. Subclass DatabaseProvider
      2. Implement all abstract methods
      3. Add an entry to PROVIDERS dict at the bottom of this file
    """

    name: str = ""

    @abstractmethod
    def connect(self) -> bool:
        """Establish and verify connection. Returns True on success."""

    @abstractmethod
    def get_collection(self, name: str):
        """Return a collection handle supporting find/insert_one/update_one/delete_one."""

    @abstractmethod
    def create_schema(self, collections: list) -> dict:
        """
        Create collections and any required indexes.
        Returns {collection_name: True/False} indicating success per collection.
        """

    @abstractmethod
    def list_existing_collections(self) -> list:
        """Return names of collections that currently exist."""

    def close(self):
        """Optional cleanup on exit."""


# ---------------------------------------------------------------------------
# AstraDB provider
# ---------------------------------------------------------------------------

class AstraProvider(DatabaseProvider):
    name = "AstraDB"

    def __init__(self):
        self._db = None

    def connect(self) -> bool:
        try:
            from astrapy import DataAPIClient  # noqa: PLC0415
        except ImportError:
            print("  ERROR: astrapy not installed. Run: pip install astrapy")
            return False
        try:
            endpoint = _prompt_env("ASTRA_API_ENDPOINT", "AstraDB endpoint URL")
            token = _prompt_env("ASTRA_API_TOKEN", "AstraDB token", sensitive=True)
            namespace = os.getenv("ASTRA_NAMESPACE", "default_keyspace")
            client = DataAPIClient(token)
            self._db = client.get_database(endpoint, keyspace=namespace)
            # Verify with list_collection_names() — uses the Data API (same as all
            # regular operations). Avoid info() which uses the Admin DevOps API and
            # fails with regular application tokens.
            self._db.list_collection_names()
            print(f"  Connected to AstraDB  (keyspace: {namespace})")
            return True
        except Exception as e:
            print(f"  ERROR connecting to AstraDB: {e}")
            return False

    def get_collection(self, name: str):
        return self._db.get_collection(name)

    def create_schema(self, collections: list) -> dict:
        results = {}
        for name in collections:
            try:
                self._db.create_collection(name)
                print(f"  [OK]   {name} — created")
                results[name] = True
            except Exception as e:
                # astrapy raises an exception when the collection already exists;
                # treat that as success rather than a failure.
                err = str(e).lower()
                if "already exist" in err or "existing" in err or "already" in err:
                    print(f"  [SKIP] {name} — already exists")
                    results[name] = True
                else:
                    print(f"  [FAIL] {name} — {e}")
                    results[name] = False
        return results

    def list_existing_collections(self) -> list:
        try:
            return self._db.list_collection_names()
        except Exception:
            return []


# ---------------------------------------------------------------------------
# MongoDB provider
# ---------------------------------------------------------------------------

class MongoDBProvider(DatabaseProvider):
    name = "MongoDB Atlas"

    def __init__(self):
        self._client = None
        self._db = None

    def connect(self) -> bool:
        try:
            import pymongo  # noqa: PLC0415
        except ImportError:
            print("  ERROR: pymongo not installed. Run: pip install pymongo")
            return False
        try:
            uri = _prompt_env("MONGODB_URI", "MongoDB URI (mongodb+srv://...)", sensitive=True)
            db_name = os.getenv("MONGODB_DB_NAME", "samosabot")
            self._client = pymongo.MongoClient(uri, serverSelectionTimeoutMS=8000)
            # Trigger a real network call to verify credentials
            self._client.server_info()
            self._db = self._client[db_name]
            print(f"  Connected to MongoDB: database '{db_name}'")
            return True
        except Exception as e:
            print(f"  ERROR connecting to MongoDB: {e}")
            return False

    def get_collection(self, name: str):
        return self._db[name]

    def create_schema(self, collections: list) -> dict:
        existing = self.list_existing_collections()
        results = {}
        for name in collections:
            try:
                if name not in existing:
                    self._db.create_collection(name)
                    print(f"  [OK]   {name} — created")
                else:
                    print(f"  [SKIP] {name} — already exists")

                # Always ensure indexes (idempotent)
                indexes = MONGODB_INDEXES.get(name, [])
                if indexes:
                    coll = self._db[name]
                    for idx in indexes:
                        key_pairs = list(idx["key"].items())
                        opts = {k: v for k, v in idx.items() if k != "key"}
                        try:
                            coll.create_index(key_pairs, **opts)
                        except Exception as idx_err:
                            print(f"    [WARN] index '{idx.get('name')}' on {name}: {idx_err}")
                    print(f"         {len(indexes)} index(es) ensured")

                results[name] = True
            except Exception as e:
                print(f"  [FAIL] {name} — {e}")
                results[name] = False
        return results

    def list_existing_collections(self) -> list:
        try:
            return self._db.list_collection_names()
        except Exception:
            return []

    def close(self):
        if self._client:
            self._client.close()


# ---------------------------------------------------------------------------
# Provider registry — add new providers here
# ---------------------------------------------------------------------------

PROVIDERS = {
    "1": ("AstraDB", AstraProvider),
    "2": ("MongoDB Atlas", MongoDBProvider),
}


# ---------------------------------------------------------------------------
# Serialization helpers
# ---------------------------------------------------------------------------

def _serialize_doc(doc: dict) -> dict:
    """
    Convert a document to a JSON-safe dict. Preserves _id as a string so it
    can be restored exactly on import (both AstraDB UUIDs and MongoDB ObjectIds).
    """
    out = {}
    for k, v in doc.items():
        if k == "_id":
            out["_id"] = str(v)
        elif isinstance(v, dict):
            out[k] = _serialize_doc(v)
        elif isinstance(v, list):
            out[k] = [_serialize_doc(i) if isinstance(i, dict) else _coerce(i) for i in v]
        else:
            out[k] = _coerce(v)
    return out


def _coerce(v):
    """Coerce non-JSON-native types (ObjectId, datetime, etc.) to strings."""
    # datetime objects
    if hasattr(v, "isoformat"):
        return v.isoformat()
    # bson ObjectId and similar
    type_name = type(v).__name__
    if type_name in ("ObjectId", "UUID", "Decimal128"):
        return str(v)
    return v


def _restore_id(id_str: str):
    """
    Try to restore a MongoDB ObjectId from its string form when importing
    back into MongoDB. Falls back to the plain string (e.g. AstraDB UUIDs).
    """
    try:
        from bson import ObjectId  # noqa: PLC0415
        if len(id_str) == 24 and all(c in "0123456789abcdef" for c in id_str.lower()):
            return ObjectId(id_str)
    except ImportError:
        pass
    return id_str


# ---------------------------------------------------------------------------
# Export
# ---------------------------------------------------------------------------

def export_data(provider: DatabaseProvider, collections: list, export_path: str) -> dict:
    """
    Dump each collection to <export_path>/<name>.json.
    Returns {collection_name: document_count}  (-1 on failure).
    """
    os.makedirs(export_path, exist_ok=True)
    counts = {}
    for name in collections:
        print(f"  Exporting {name} ...", end=" ", flush=True)
        try:
            coll = provider.get_collection(name)
            docs = [_serialize_doc(doc) for doc in coll.find({})]
            filepath = os.path.join(export_path, f"{name}.json")
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(docs, f, indent=2, default=str)
            print(f"{len(docs)} documents")
            counts[name] = len(docs)
        except Exception as e:
            print(f"FAILED — {e}")
            counts[name] = -1
    return counts


def write_meta(export_path: str, provider_name: str, counts: dict):
    meta = {
        "exported_at": datetime.datetime.utcnow().isoformat(),
        "provider": provider_name,
        "collections": counts,
    }
    with open(os.path.join(export_path, "_meta.json"), "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2)


def read_meta(export_path: str) -> dict:
    meta_path = os.path.join(export_path, "_meta.json")
    if os.path.exists(meta_path):
        with open(meta_path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


# ---------------------------------------------------------------------------
# Import
# ---------------------------------------------------------------------------

def import_data(provider: DatabaseProvider, collections: list,
                export_path: str, conflict: str) -> dict:
    """
    Load each collection from <export_path>/<name>.json into the provider.
    Returns {collection_name: (imported, skipped, failed)}.
    """
    is_mongo = isinstance(provider, MongoDBProvider)
    results = {}

    for name in collections:
        filepath = os.path.join(export_path, f"{name}.json")
        if not os.path.exists(filepath):
            print(f"  [SKIP] {name} — export file not found")
            results[name] = (0, 0, 0)
            continue

        try:
            with open(filepath, "r", encoding="utf-8") as f:
                docs = json.load(f)
        except Exception as e:
            print(f"  [FAIL] {name} — could not read file: {e}")
            results[name] = (0, 0, 0)
            continue

        print(f"  Importing {name} ({len(docs)} docs) ...")
        coll = provider.get_collection(name)
        imported = skipped = failed = 0
        aborted = False

        for doc in docs:
            try:
                raw_id = doc.get("_id")
                # Restore ObjectId format when target is MongoDB
                doc_id = _restore_id(raw_id) if (is_mongo and raw_id) else raw_id
                if doc_id is not None:
                    doc["_id"] = doc_id

                # Conflict check
                existing = coll.find_one({"_id": doc_id}) if doc_id else None

                if existing:
                    if conflict == CONFLICT_SKIP:
                        skipped += 1
                        continue
                    elif conflict == CONFLICT_ABORT:
                        print(f"    ABORTED — _id={doc_id} already exists in target")
                        aborted = True
                        break
                    elif conflict == CONFLICT_OVERWRITE:
                        coll.delete_one({"_id": doc_id})

                coll.insert_one(doc)
                imported += 1

            except Exception as e:
                logging.warning(f"Failed to insert doc in {name}: {e}")
                failed += 1

        status = f"    {imported} imported, {skipped} skipped, {failed} failed"
        if aborted:
            status += "  [ABORTED on first conflict]"
        print(status)
        results[name] = (imported, skipped, failed)

    return results


# ---------------------------------------------------------------------------
# CLI helpers
# ---------------------------------------------------------------------------

def _prompt_env(env_key: str, label: str, sensitive: bool = False) -> str:
    """Return env var value, or interactively prompt if not set.
    Use sensitive=True for tokens/passwords — input will be masked."""
    val = os.getenv(env_key, "").strip()
    if val:
        return val
    if sensitive:
        val = getpass.getpass(f"    Enter {label} [{env_key}]: ")
    else:
        val = input(f"    Enter {label} [{env_key}]: ").strip()
    if not val:
        raise ValueError(f"Missing required value: {label}")
    return val


def _prompt_provider(prompt_text: str) -> DatabaseProvider:
    """Prompt user to pick a provider and connect. Exits on failure."""
    print(f"\n{prompt_text}")
    for k, (label, _) in PROVIDERS.items():
        print(f"  {k}. {label}")
    while True:
        key = input("  > ").strip()
        if key in PROVIDERS:
            break
        print(f"  Pick one of: {', '.join(PROVIDERS.keys())}")

    label, cls = PROVIDERS[key]
    print(f"\nConnecting to {label} ...")
    provider = cls()
    if not provider.connect():
        print("Connection failed. Exiting.")
        sys.exit(1)
    return provider


def _select_collections() -> list:
    print("\nWhich collections?")
    print("  1. All collections")
    print("  2. Select specific collections")
    choice = input("  > ").strip()

    if choice != "2":
        return list(ALL_COLLECTIONS)

    print("\nAvailable collections:")
    for i, name in enumerate(ALL_COLLECTIONS, 1):
        print(f"  {i:2}. {name}")
    raw = input("  Enter numbers (comma-separated, e.g. 1,3,5): ").strip()

    selected = []
    for part in raw.split(","):
        part = part.strip()
        if part.isdigit():
            idx = int(part) - 1
            if 0 <= idx < len(ALL_COLLECTIONS):
                selected.append(ALL_COLLECTIONS[idx])

    if not selected:
        print("  No valid selection — defaulting to all collections.")
        return list(ALL_COLLECTIONS)
    return selected


def _prompt_conflict() -> str:
    print("\nConflict resolution (when _id already exists in target):")
    print("  1. Skip       — keep existing document, skip import  [default]")
    print("  2. Overwrite  — delete existing, insert from source")
    print("  3. Abort      — stop on first conflict")
    choice = input("  > ").strip()
    return {"1": CONFLICT_SKIP, "2": CONFLICT_OVERWRITE, "3": CONFLICT_ABORT}.get(
        choice, CONFLICT_SKIP
    )


def _pick_export_dir_for_write() -> str:
    """Return a new timestamped export path (directory not yet created)."""
    ts = datetime.datetime.now().strftime("%Y-%m-%d_%H%M%S")
    return os.path.join(EXPORT_BASE_DIR, ts)


def _pick_export_dir_for_read() -> str:
    """Let user choose an existing export directory to import from."""
    if not os.path.isdir(EXPORT_BASE_DIR):
        print(f"  No migration_export/ directory found at {EXPORT_BASE_DIR}")
        path = input("  Enter full path to export directory: ").strip()
        return path

    subdirs = sorted(
        [d for d in os.listdir(EXPORT_BASE_DIR)
         if os.path.isdir(os.path.join(EXPORT_BASE_DIR, d))],
        reverse=True,
    )

    if not subdirs:
        print(f"  No exports found in {EXPORT_BASE_DIR}")
        path = input("  Enter full path to export directory: ").strip()
        return path

    print(f"\nAvailable exports  ({EXPORT_BASE_DIR}):")
    for i, d in enumerate(subdirs[:15], 1):
        path = os.path.join(EXPORT_BASE_DIR, d)
        meta = read_meta(path)
        provider_label = meta.get("provider", "unknown source")
        n_files = len([f for f in os.listdir(path)
                       if f.endswith(".json") and not f.startswith("_")])
        print(f"  {i:2}. {d}   ({n_files} collections, from {provider_label})")
    print("   c. Enter custom path")

    while True:
        choice = input("  > ").strip()
        if choice.lower() == "c":
            return input("  Path: ").strip()
        if choice.isdigit():
            idx = int(choice) - 1
            if 0 <= idx < len(subdirs[:15]):
                return os.path.join(EXPORT_BASE_DIR, subdirs[idx])
        print("  Invalid choice, try again.")


def _yn(question: str, default: bool = True) -> bool:
    suffix = "[Y/n]" if default else "[y/N]"
    answer = input(f"  {question} {suffix}: ").strip().lower()
    if not answer:
        return default
    return answer in ("y", "yes")


def _print_banner():
    print()
    print("=" * 56)
    print("  SamosaBot — Database Migration Tool")
    print("=" * 56)


def _print_summary(label: str, results: dict):
    total_ok = sum(1 for v in results.values() if v)
    total = len(results)
    print(f"\n{label}: {total_ok}/{total} collections succeeded")
    for name, ok in results.items():
        mark = "[OK]  " if ok else "[FAIL]"
        print(f"  {mark} {name}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s: %(message)s")
    _print_banner()

    # ── Action ──────────────────────────────────────────────────────────────
    print("\nWhat do you want to do?")
    print("  1. Export  — dump collections from a database to local JSON files")
    print("  2. Import  — load collections from local JSON files into a database")
    print("  3. Migrate — export from source, then import into target")
    print("  4. Schema  — create collections / indexes only (no data transfer)")
    action = input("  > ").strip()
    if action not in ("1", "2", "3", "4"):
        print("Invalid choice. Exiting.")
        sys.exit(1)

    src_provider = None
    tgt_provider = None
    export_path = None

    # ── Connect providers ────────────────────────────────────────────────────
    if action in ("1", "3"):
        src_provider = _prompt_provider("Source database (export from):")

    if action in ("2", "3", "4"):
        tgt_provider = _prompt_provider("Target database (import into / create schema on):")

    # ── Collection selection ─────────────────────────────────────────────────
    collections = _select_collections()
    print(f"\n  {len(collections)} collection(s) selected: {', '.join(collections)}")

    # ── Export ───────────────────────────────────────────────────────────────
    if action in ("1", "3"):
        export_path = _pick_export_dir_for_write()
        print(f"\nExporting from {src_provider.name}  →  {export_path}")
        counts = export_data(src_provider, collections, export_path)
        write_meta(export_path, src_provider.name, counts)
        total_docs = sum(c for c in counts.values() if c >= 0)
        failed_cols = [n for n, c in counts.items() if c < 0]
        print(f"\nExport complete: {total_docs} documents across {len(counts)} collections")
        if failed_cols:
            print(f"  WARNING — failed collections: {', '.join(failed_cols)}")

    # ── Schema creation ──────────────────────────────────────────────────────
    if action == "4":
        print(f"\nCreating schema on {tgt_provider.name} ...")
        results = tgt_provider.create_schema(collections)
        _print_summary("Schema", results)

    if action == "3":
        # Always create schema before migrating
        print(f"\nEnsuring schema on {tgt_provider.name} ...")
        tgt_provider.create_schema(collections)

    if action == "2":
        if _yn("Create / ensure schema on target before importing?"):
            print(f"\nEnsuring schema on {tgt_provider.name} ...")
            tgt_provider.create_schema(collections)

    # ── Import ───────────────────────────────────────────────────────────────
    if action in ("2", "3"):
        if action == "2":
            export_path = _pick_export_dir_for_read()
            if not export_path:
                print("No export path selected. Exiting.")
                sys.exit(1)

        conflict = _prompt_conflict()
        print(f"\nImporting into {tgt_provider.name}  from  {export_path} ...")
        results = import_data(tgt_provider, collections, export_path, conflict)

        total_imported = sum(r[0] for r in results.values())
        total_skipped = sum(r[1] for r in results.values())
        total_failed = sum(r[2] for r in results.values())
        print(
            f"\nImport complete: {total_imported} imported, "
            f"{total_skipped} skipped, {total_failed} failed"
        )

    # ── Cleanup ──────────────────────────────────────────────────────────────
    for p in (src_provider, tgt_provider):
        if p:
            p.close()

    print("\nDone.")


if __name__ == "__main__":
    main()
