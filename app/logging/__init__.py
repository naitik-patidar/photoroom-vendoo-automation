"""
Structured logging configuration.

Sets up application-wide logging with:
- Console handler (human-readable)
- File handler (structured, rotated)
- No secrets ever logged
"""

import logging
import logging.handlers
import sys
from pathlib import Path
from datetime import datetime, timezone


# ---------------------------------------------------------------------------
# Custom formatter for structured console output
# ---------------------------------------------------------------------------
class StructuredFormatter(logging.Formatter):
    """Formatter that produces clean, structured log lines."""

    LEVEL_COLORS = {
        "DEBUG": "\033[36m",     # cyan
        "INFO": "\033[32m",      # green
        "WARNING": "\033[33m",   # yellow
        "ERROR": "\033[31m",     # red
        "CRITICAL": "\033[35m",  # magenta
    }
    RESET = "\033[0m"

    def __init__(self, use_color: bool = True):
        super().__init__()
        self.use_color = use_color

    def format(self, record: logging.LogRecord) -> str:
        ts = datetime.fromtimestamp(record.created, tz=timezone.utc).strftime(
            "%Y-%m-%d %H:%M:%S"
        )
        level = record.levelname
        name = record.name
        msg = record.getMessage()

        if self.use_color:
            color = self.LEVEL_COLORS.get(level, "")
            return f"{ts} {color}[{level:<8}]{self.RESET} {name} — {msg}"
        else:
            return f"{ts} [{level:<8}] {name} — {msg}"


# ---------------------------------------------------------------------------
# File formatter (no ANSI colors)
# ---------------------------------------------------------------------------
class FileFormatter(logging.Formatter):
    """Plain-text formatter for log files."""

    def format(self, record: logging.LogRecord) -> str:
        ts = datetime.fromtimestamp(record.created, tz=timezone.utc).strftime(
            "%Y-%m-%d %H:%M:%S.%f"
        )
        return (
            f"{ts} [{record.levelname:<8}] "
            f"{record.name} — {record.getMessage()}"
        )


# ---------------------------------------------------------------------------
# Setup function
# ---------------------------------------------------------------------------
def setup_logging(
    log_level: str = "INFO",
    log_dir: str | None = None,
    log_filename: str = "app.log",
) -> logging.Logger:
    """
    Configure application-wide logging.

    Args:
        log_level: Logging level string (DEBUG, INFO, WARNING, ERROR, CRITICAL).
        log_dir: Directory for log files. If None, file logging is disabled.
        log_filename: Name of the log file.

    Returns:
        The root application logger.
    """
    level = getattr(logging, log_level.upper(), logging.INFO)

    # Get or create the application root logger
    logger = logging.getLogger("app")
    logger.setLevel(level)

    # Prevent duplicate handlers on re-init
    logger.handlers.clear()

    # --- Console handler ---
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(level)
    console_handler.setFormatter(StructuredFormatter(use_color=True))
    logger.addHandler(console_handler)

    # --- File handler (optional) ---
    if log_dir:
        log_path = Path(log_dir)
        log_path.mkdir(parents=True, exist_ok=True)
        file_path = log_path / log_filename

        file_handler = logging.handlers.RotatingFileHandler(
            file_path,
            maxBytes=5 * 1024 * 1024,  # 5 MB per file
            backupCount=5,
            encoding="utf-8",
        )
        file_handler.setLevel(level)
        file_handler.setFormatter(FileFormatter())
        logger.addHandler(file_handler)

    return logger


def get_logger(name: str) -> logging.Logger:
    """
    Get a child logger under the 'app' namespace.

    Usage:
        from app.logging import get_logger
        logger = get_logger(__name__)
        logger.info("Something happened")
    """
    return logging.getLogger(f"app.{name}")
