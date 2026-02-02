"""
Keep Alive Module

This module runs a lightweight web server to keep the bot process active in hosting environments
that automatically shut down inactive applications (e.g., Repl.it or Heroku). By serving a simple
HTTP endpoint, the module ensures continuous uptime by responding to periodic ping requests.

Optional: init_reload(bot) registers a /reload endpoint for developer use (reload cogs without
restarting the process). Requires RELOAD_SECRET in env. Not an end-user feature.
"""

import os
import asyncio
from flask import Flask, request, jsonify
from threading import Thread

app = Flask(__name__)
_bot_ref = None


@app.route('/')
def home():
    return "I'm alive!"


@app.route('/reload', methods=["GET", "POST"])
def reload_extensions():
    """Reload one cog or all. Query params: cog=<name or 'all'>, secret=<RELOAD_SECRET>. Developer only."""
    secret = os.getenv("RELOAD_SECRET")
    if not secret or secret != request.args.get("secret"):
        return jsonify({"ok": False, "error": "Forbidden"}), 403
    cog = request.args.get("cog")
    if not cog:
        return jsonify({"ok": False, "error": "Missing 'cog' (extension name or 'all')"}), 400
    global _bot_ref
    if not _bot_ref or not _bot_ref.loop:
        return jsonify({"ok": False, "error": "Reload not initialized"}), 503
    extensions = [e.strip() for e in os.getenv("EXTENSIONS", "").split(",") if e.strip()]
    if cog.lower() == "all":
        to_reload = extensions
    else:
        if cog not in extensions:
            return jsonify({"ok": False, "error": f"Unknown cog: {cog}"}), 400
        to_reload = [cog]
    reloaded = []
    errors = []
    for ext in to_reload:
        try:
            future = asyncio.run_coroutine_threadsafe(_bot_ref.reload_extension(ext), _bot_ref.loop)
            future.result(timeout=15)
            reloaded.append(ext)
        except Exception as e:
            errors.append(f"{ext}: {e}")
    if errors:
        return jsonify({"ok": len(reloaded) > 0, "reloaded": reloaded, "errors": errors}), 200
    return jsonify({"ok": True, "reloaded": reloaded}), 200


def init_reload(bot):
    """Register /reload endpoint. Call before keep_alive(). Requires RELOAD_SECRET in env."""
    global _bot_ref
    _bot_ref = bot


def run():
    app.run(host="0.0.0.0", port=8080)


def keep_alive():
    t = Thread(target=run)
    t.start()