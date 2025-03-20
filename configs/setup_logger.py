"""
Logging Configuration Module

This module sets up the logging configuration for the application by:
  - Loading environment variables using python-dotenv.
  - Retrieving the desired log level from the environment variable LOG_LEVEL (defaulting to INFO).
  - Converting the log level string to the appropriate logging level.
  - Configuring the logging output format to include the timestamp, log level, and message.

Any module that imports Python's logging after this configuration is loaded will use these settings.
"""
import os
import logging
from dotenv import load_dotenv

load_dotenv()

LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")

try:
    log_level = getattr(logging, LOG_LEVEL.upper())
except AttributeError:
    print(f"WARNING: Invalid LOG_LEVEL '{LOG_LEVEL}'. Defaulting to INFO.")
    log_level = logging.INFO

logging.basicConfig(level=log_level, format='%(asctime)s - %(levelname)s - %(message)s')
