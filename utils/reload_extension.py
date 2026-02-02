#!/usr/bin/env python3
"""
Standalone script to trigger cog reload on a running bot (developer use, not end-user).

The bot must be running with RELOAD_SECRET set. This script sends a request to the bot's
/reload endpoint to reload one extension or all.

Usage:
  python -m utils.reload_extension <cog>   # e.g. cogs.confession or all
  python utils/reload_extension.py all
  python utils/reload_extension.py cogs.confession

Env (or .env): RELOAD_SECRET (required), RELOAD_URL (default http://localhost:8080).
"""
import os
import sys
import requests
from dotenv import load_dotenv

load_dotenv()

RELOAD_URL = os.getenv("RELOAD_URL", "http://localhost:8080").rstrip("/")
RELOAD_SECRET = os.getenv("RELOAD_SECRET", "")


def main():
    if len(sys.argv) < 2:
        print("Usage: python -m utils.reload_extension <cog|all>")
        print("  cog: extension name (e.g. cogs.confession) or 'all'")
        sys.exit(1)
    cog = sys.argv[1].strip()
    if not RELOAD_SECRET:
        print("Error: RELOAD_SECRET not set in env or .env")
        sys.exit(1)
    url = f"{RELOAD_URL}/reload"
    params = {"cog": cog, "secret": RELOAD_SECRET}
    try:
        r = requests.get(url, params=params, timeout=15)
    except requests.RequestException as e:
        print(f"Request failed: {e}")
        sys.exit(1)
    try:
        data = r.json()
    except Exception:
        print(f"Response: {r.status_code} {r.text}")
        sys.exit(1)
    if r.status_code == 200:
        print("OK:", data.get("reloaded", []))
        if data.get("errors"):
            print("Errors:", data["errors"])
    else:
        print(f"Error {r.status_code}:", data.get("error", r.text))
        sys.exit(1)


if __name__ == "__main__":
    main()
