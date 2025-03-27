import time
import os
from dotenv import load_dotenv
import logging

# Force reload environment variables
load_dotenv(override=True)

# Configuration Variables
EXEMPT_COMMANDS = os.getenv("EXEMPT_COMMANDS", "trivia").lower().split(",")
logging.info(f"Loaded exempt commands: {EXEMPT_COMMANDS}")

DELAY_BETWEEN_COMMANDS = int(os.getenv("DELAY_BETWEEN_COMMANDS", "5"))
MAX_ALLOWED_PER_MINUTE = int(os.getenv("MAX_ALLOWED_PER_MINUTE", "10"))

# Dictionary to track user command timestamps
user_command_timestamps = {}

def check_command_throttle(user_id: int, command_name: str) -> float:
    """
    Check the throttle limits for a given user and command.
    
    Enforces:
      - A minimum gap of DELAY_BETWEEN_COMMANDS seconds between commands.
      - A maximum of MAX_ALLOWED_PER_MINUTE commands per minute.
    
    If the command is in the EXEMPT_COMMANDS set, no throttling is applied.
    
    Args:
        user_id (int): The ID of the user invoking the command.
        command_name (str): The name of the command.
    
    Returns:
        float: The number of seconds the user should wait before executing the command.
               Returns 0 if no delay is required.
    """
    now = time.time()
    
    # Strip only '!' prefix from command name
    command_name = command_name.lstrip('!').lower()
    
    # If command is exempt, skip throttling.
    if command_name in EXEMPT_COMMANDS:
        logging.info(f"Command '{command_name}' is exempt from throttling")
        return 0

    # Initialize or clean up the user's timestamp list (only consider the last 60 seconds)
    if user_id not in user_command_timestamps:
        user_command_timestamps[user_id] = []
    user_command_timestamps[user_id] = [t for t in user_command_timestamps[user_id] if now - t < 60]

    # Enforce a DELAY_BETWEEN_COMMANDS-second gap between commands
    if user_command_timestamps[user_id]:
        last_timestamp = user_command_timestamps[user_id][-1]
        gap = now - last_timestamp
        if gap < DELAY_BETWEEN_COMMANDS:
            wait_time = DELAY_BETWEEN_COMMANDS - gap
            logging.info(f"User {user_id} needs to wait {wait_time:.1f} seconds before using '{command_name}' (command gap)")
            return wait_time

    # Enforce a maximum of MAX_ALLOWED_PER_MINUTE commands per minute
    if len(user_command_timestamps[user_id]) >= MAX_ALLOWED_PER_MINUTE:
        earliest = user_command_timestamps[user_id][0]
        wait_time = 60 - (now - earliest)
        if wait_time > 0:
            logging.info(f"User {user_id} needs to wait {wait_time:.1f} seconds before using '{command_name}' (rate limit)")
            return wait_time

    # Record the current command timestamp if no throttling conditions are triggered
    user_command_timestamps[user_id].append(now)
    return 0