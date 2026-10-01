"""
Command Interpreter — Abstract interface for AI-powered instruction parsing.

The interpreter takes natural language text and returns a structured command.
All implementations must follow this interface:
- MockCommandInterpreter: pattern-matching (no API calls)
- RealCommandInterpreter: calls LLM API (Task 14+)
"""

from abc import ABC, abstractmethod

from app.ai.schemas import CommandResult


class CommandInterpreter(ABC):
    """
    Abstract interface for natural language → structured command interpretation.

    Usage:
        interpreter = MockCommandInterpreter()
        result = interpreter.interpret("Process the shirt photo at /img/shirt.jpg for $25")
        # result.command_type == CommandType.PROCESS_IMAGE
        # result.command.image_path == "/img/shirt.jpg"
        # result.command.price == 25.0
    """

    @abstractmethod
    def interpret(self, user_input: str) -> CommandResult:
        """
        Interpret a natural language instruction.

        Args:
            user_input: Raw text from the user.

        Returns:
            CommandResult with the parsed command, confidence, and notes.
        """
        ...

    @abstractmethod
    def get_interpreter_info(self) -> dict:
        """Return metadata about this interpreter implementation."""
        ...
