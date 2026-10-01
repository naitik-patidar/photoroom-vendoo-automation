"""
AI Command Engine package.

Parses natural language instructions into structured, executable commands.
"""

from app.ai.schemas import (
    CommandType,
    CommandResult,
    ProcessImageCommand,
    BatchProcessCommand,
    CreateListingCommand,
    CheckStatusCommand,
    RetryCommand,
    HelpCommand,
    UnknownCommand,
)
from app.ai.command_interpreter import CommandInterpreter
from app.ai.mock_interpreter import MockCommandInterpreter
from app.config.settings import get_settings


def create_interpreter(mode: str | None = None) -> CommandInterpreter:
    """
    Factory function to create the appropriate CommandInterpreter.
    
    Args:
        mode: "mock" or "production". Defaults to settings.APP_MODE.
    
    Returns:
        A CommandInterpreter instance.
    """
    if mode is None:
        mode = get_settings().app_mode

    if mode == "production":
        # We will build the real LLM interpreter in a future task
        # For now, fallback to mock with a warning
        import logging
        logger = logging.getLogger("app.ai.factory")
        logger.warning("Real LLM interpreter not yet implemented. Falling back to MockCommandInterpreter.")
        return MockCommandInterpreter()

    return MockCommandInterpreter()


__all__ = [
    "CommandType",
    "CommandResult",
    "ProcessImageCommand",
    "BatchProcessCommand",
    "CreateListingCommand",
    "CheckStatusCommand",
    "RetryCommand",
    "HelpCommand",
    "UnknownCommand",
    "CommandInterpreter",
    "create_interpreter",
]
