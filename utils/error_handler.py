"""
Standardized Error Handling Framework

Provides consistent error handling, logging, and user-facing messages
across all bot commands and operations.

Distinguishes between:
- Functional Errors: Business logic, validation, user input issues
- Runtime Errors: Technical failures (API, DB, network, etc.)
"""

import logging
from enum import Enum
from typing import Optional, Union
import discord
from discord.ext import commands
import discord.errors
import asyncio
import requests.exceptions

class ErrorCategory(Enum):
    """Error categories - distinguishes functional vs runtime errors"""
    # Functional Errors (Business Logic - User/Input Related)
    VALIDATION_ERROR = "validation_error"      # Invalid input format/type
    BUSINESS_RULE_ERROR = "business_rule_error" # Business logic violation (e.g., daily limit)
    USER_INPUT_ERROR = "user_input_error"     # Missing/wrong arguments
    
    # Runtime Errors (Technical Failures)
    API_ERROR = "api_error"                   # External API failures (OpenAI, etc.)
    DATABASE_ERROR = "database_error"         # Database operation failures
    NETWORK_ERROR = "network_error"           # Network/connection issues
    TIMEOUT_ERROR = "timeout_error"           # Request/operation timeouts
    PERMISSION_ERROR = "permission_error"     # Discord permission issues
    RATE_LIMIT_ERROR = "rate_limit_error"     # Rate limiting (Discord or custom)
    INTERACTION_ERROR = "interaction_error"    # Discord interaction expired/invalid
    UNKNOWN_ERROR = "unknown_error"           # Unexpected errors

class ErrorSeverity(Enum):
    """Error severity levels for logging"""
    LOW = "low"          # Non-critical, user can retry
    MEDIUM = "medium"    # May affect functionality
    HIGH = "high"        # Critical, needs attention
    CRITICAL = "critical" # System failure

# Standard error messages by category
ERROR_MESSAGES = {
    # Functional Errors (point to help)
    ErrorCategory.VALIDATION_ERROR: "❌ Invalid input. Please check your request. Use `!help` for usage.",
    ErrorCategory.BUSINESS_RULE_ERROR: "❌ Request cannot be processed. {details} Use `!help` for available commands.",
    ErrorCategory.USER_INPUT_ERROR: "❌ Invalid input. Use `!help` for usage.",
    
    # Runtime Errors (point to ping and help)
    ErrorCategory.API_ERROR: "❌ Service temporarily unavailable. Please try again later. Use `!ping` to check bot status or `!help` for available commands.",
    ErrorCategory.DATABASE_ERROR: "❌ Database error. Please try again later. Use `!ping` to check bot status or `!help` for available commands.",
    ErrorCategory.NETWORK_ERROR: "❌ Network error. Please check your connection. Use `!ping` to check bot status or `!help` for available commands.",
    ErrorCategory.TIMEOUT_ERROR: "⏳ Request timed out. Please try again. Use `!ping` to check bot status or `!help` for available commands.",
    ErrorCategory.PERMISSION_ERROR: "❌ You don't have permission for this action. Use `!help` for available commands.",
    ErrorCategory.RATE_LIMIT_ERROR: "⏳ Rate limit exceeded. Please slow down.",
    ErrorCategory.INTERACTION_ERROR: "❌ Interaction expired. Please try the command again. Use `!help` for available commands.",
    ErrorCategory.UNKNOWN_ERROR: "❌ An unexpected error occurred. Please try again later. Use `!ping` to check bot status or `!help` for available commands.",
}

def categorize_error(error: Exception) -> tuple[ErrorCategory, ErrorSeverity]:
    """
    Categorize error and determine severity.
    Distinguishes functional (business logic) vs runtime (technical) errors.
    """
    # Discord-specific errors (Runtime)
    if isinstance(error, discord.errors.NotFound):
        return ErrorCategory.INTERACTION_ERROR, ErrorSeverity.LOW
    elif isinstance(error, discord.errors.Forbidden):
        return ErrorCategory.PERMISSION_ERROR, ErrorSeverity.MEDIUM
    elif isinstance(error, discord.errors.HTTPException):
        if error.status == 429:  # Rate limited
            return ErrorCategory.RATE_LIMIT_ERROR, ErrorSeverity.MEDIUM
        elif error.status == 403:
            return ErrorCategory.PERMISSION_ERROR, ErrorSeverity.MEDIUM
        elif error.status == 404:
            return ErrorCategory.INTERACTION_ERROR, ErrorSeverity.LOW
        else:
            return ErrorCategory.API_ERROR, ErrorSeverity.HIGH
    elif isinstance(error, discord.errors.RateLimited):
        return ErrorCategory.RATE_LIMIT_ERROR, ErrorSeverity.MEDIUM
    
    # Command framework errors (Functional - User Input)
    elif isinstance(error, commands.CommandNotFound):
        return ErrorCategory.USER_INPUT_ERROR, ErrorSeverity.LOW
    elif isinstance(error, commands.MissingRequiredArgument):
        return ErrorCategory.VALIDATION_ERROR, ErrorSeverity.LOW
    elif isinstance(error, (commands.BadArgument, commands.TooManyArguments)):
        return ErrorCategory.VALIDATION_ERROR, ErrorSeverity.LOW
    elif isinstance(error, commands.CommandOnCooldown):
        return ErrorCategory.RATE_LIMIT_ERROR, ErrorSeverity.LOW
    
    # Network/Timeout errors (Runtime)
    elif isinstance(error, (asyncio.TimeoutError, requests.exceptions.Timeout)):
        return ErrorCategory.TIMEOUT_ERROR, ErrorSeverity.MEDIUM
    elif isinstance(error, (requests.exceptions.ConnectionError, 
                            requests.exceptions.ConnectTimeout)):
        return ErrorCategory.NETWORK_ERROR, ErrorSeverity.HIGH
    
    # Validation errors (Functional - Data Format)
    elif isinstance(error, (ValueError, KeyError, AttributeError, TypeError, IndexError)):
        return ErrorCategory.VALIDATION_ERROR, ErrorSeverity.LOW
    elif isinstance(error, __import__('json').JSONDecodeError):
        return ErrorCategory.VALIDATION_ERROR, ErrorSeverity.MEDIUM
    
    # API/Database errors (Runtime - based on error message)
    error_str = str(error).lower()
    if "api" in error_str or "openai" in error_str or "http" in error_str:
        return ErrorCategory.API_ERROR, ErrorSeverity.HIGH
    elif "database" in error_str or "astra" in error_str or "db" in error_str:
        return ErrorCategory.DATABASE_ERROR, ErrorSeverity.HIGH
    
    # Default (Runtime - Unknown)
    return ErrorCategory.UNKNOWN_ERROR, ErrorSeverity.MEDIUM

async def send_error_safely(
    context: Union[discord.Interaction, commands.Context],
    message: str,
    ephemeral: bool = True
) -> None:
    """
    Safely send error message, handling all interaction states.
    
    Handles:
    - Interaction not responded to yet
    - Interaction already responded to
    - Interaction expired (NotFound)
    - Rate limiting when sending error
    """
    try:
        if isinstance(context, discord.Interaction):
            # Check if interaction response is available
            if not context.response.is_done():
                await context.response.send_message(message, ephemeral=ephemeral)
            else:
                await context.followup.send(message, ephemeral=ephemeral)
        else:
            # Prefix command context
            await context.send(message)
    except discord.errors.NotFound:
        # Interaction expired - try to send in channel if possible
        if isinstance(context, discord.Interaction) and context.channel:
            try:
                await context.channel.send(f"{context.user.mention} {message}")
            except Exception:
                logging.error(f"Failed to send error message to channel for expired interaction")
    except discord.errors.HTTPException as e:
        if e.status == 429:  # Rate limited
            logging.warning(f"Discord rate limited when sending error message")
        else:
            logging.error(f"HTTP error sending error message: {e}")
    except Exception as e:
        logging.error(f"Failed to send error message: {e}", exc_info=True)

async def handle_error(
    error: Exception,
    context: Union[discord.Interaction, commands.Context],
    command_name: str = "",
    additional_context: Optional[dict] = None
) -> None:
    """
    Centralized error handler that logs errors and sends user-friendly messages.
    
    Distinguishes functional (business logic) vs runtime (technical) errors.
    
    Args:
        error: The exception that occurred
        context: Discord interaction or context object
        command_name: Name of the command that failed
        additional_context: Additional context for logging
    """
    # Categorize error (determines if functional or runtime)
    category, severity = categorize_error(error)
    
    # Determine if this is a functional or runtime error
    is_functional = category in [
        ErrorCategory.VALIDATION_ERROR,
        ErrorCategory.BUSINESS_RULE_ERROR,
        ErrorCategory.USER_INPUT_ERROR
    ]
    
    # Build log context
    log_context = {
        "command": command_name,
        "category": category.value,
        "severity": severity.value,
        "error_type": type(error).__name__,
        "is_functional": is_functional,
    }
    
    # Add user/guild context
    if isinstance(context, discord.Interaction):
        log_context.update({
            "user_id": context.user.id,
            "user_name": context.user.display_name,
            "guild_id": context.guild_id,
            "guild_name": context.guild.name if context.guild else None,
        })
    else:
        log_context.update({
            "user_id": context.author.id,
            "user_name": context.author.display_name,
            "guild_id": context.guild.id if context.guild else None,
            "guild_name": context.guild.name if context.guild else None,
        })
    
    if additional_context:
        log_context.update(additional_context)
    
    # Build log message with key info: command, user, guild
    user_name = log_context.get("user_name", "Unknown")
    guild_name = log_context.get("guild_name", "DM/Unknown")
    log_message = f"Error in command '{command_name}' | User: {user_name} | Guild: {guild_name} | Error: {str(error)}"
    
    if severity == ErrorSeverity.CRITICAL:
        logging.critical(log_message, extra=log_context, exc_info=True)
    elif severity == ErrorSeverity.HIGH:
        logging.error(log_message, extra=log_context, exc_info=True)
    else:
        logging.warning(log_message, extra=log_context)
    
    # Get user-friendly message
    user_message = ERROR_MESSAGES.get(category, ERROR_MESSAGES[ErrorCategory.UNKNOWN_ERROR])
    
    # Handle special cases with dynamic messages
    if isinstance(error, commands.CommandOnCooldown):
        import math
        retry = math.ceil(error.retry_after)
        user_message = f"⏳ Slow down! Try again in {retry} seconds."
    elif isinstance(error, discord.errors.RateLimited):
        import math
        retry = math.ceil(error.retry_after)
        user_message = f"⏳ Discord rate limit. Try again in {retry} seconds."
    elif isinstance(error, commands.MissingRequiredArgument):
        cmd_name = command_name or "command"
        user_message = f"❌ Missing required arguments. Use `!help {cmd_name}` for usage."
    
    # Send error message
    await send_error_safely(context, user_message)

async def handle_functional_error(
    message: str,
    context: Union[discord.Interaction, commands.Context],
    command_name: str = "",
    details: Optional[str] = None
) -> None:
    """
    Handle functional/business logic errors (not exceptions).
    
    Use this for business rule violations, validation failures, etc.
    that are not exceptions but need to be reported to the user.
    
    Args:
        message: Error message for logging
        context: Discord interaction or context
        command_name: Name of the command
        details: Optional details to include in user message
    """
    user_message = ERROR_MESSAGES[ErrorCategory.BUSINESS_RULE_ERROR].format(
        details=details or message
    )
    await send_error_safely(context, user_message)
    
    # Build log context for functional error
    log_context = {
        "command": command_name,
        "category": ErrorCategory.BUSINESS_RULE_ERROR.value,
        "severity": ErrorSeverity.LOW.value,
        "is_functional": True,
    }
    
    # Add user/guild context
    if isinstance(context, discord.Interaction):
        log_context.update({
            "user_id": context.user.id,
            "user_name": context.user.display_name,
            "guild_id": context.guild_id,
            "guild_name": context.guild.name if context.guild else None,
        })
    else:
        log_context.update({
            "user_id": context.author.id,
            "user_name": context.author.display_name,
            "guild_id": context.guild.id if context.guild else None,
            "guild_name": context.guild.name if context.guild else None,
        })
    
    # Build log message with key info
    user_name = log_context.get("user_name", "Unknown")
    guild_name = log_context.get("guild_name", "DM/Unknown")
    log_message = f"Functional error in command '{command_name}' | User: {user_name} | Guild: {guild_name} | Message: {message}"
    
    logging.info(log_message, extra=log_context)
