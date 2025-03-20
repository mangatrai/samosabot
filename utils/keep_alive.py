"""
Keep Alive Module

This module runs a lightweight web server to keep the bot process active in hosting environments
that automatically shut down inactive applications (e.g., Repl.it or Heroku). By serving a simple
HTTP endpoint, the module ensures continuous uptime by responding to periodic ping requests.

Usage:
  Import and call the keep_alive() function to start the server, ensuring that your bot remains online.
"""

from flask import Flask
from threading import Thread

app = Flask(__name__)


@app.route('/')
def home():
    return "I'm alive!"


def run():
    app.run(host="0.0.0.0", port=8080)


def keep_alive():
    t = Thread(target=run)
    t.start()