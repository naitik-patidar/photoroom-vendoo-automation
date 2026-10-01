"""
Tests for app.logging — Structured logging.
"""

import logging
from pathlib import Path

from app.logging import setup_logging, get_logger


class TestLogging:
    """Test logging configuration."""

    def test_setup_logging_returns_logger(self, tmp_path):
        """setup_logging should return a configured logger."""
        logger = setup_logging(log_level="DEBUG", log_dir=str(tmp_path))
        assert logger is not None
        assert isinstance(logger, logging.Logger)
        assert logger.name == "app"

    def test_logger_level_set(self, tmp_path):
        """Logger level should match the requested level."""
        logger = setup_logging(log_level="WARNING", log_dir=str(tmp_path))
        assert logger.level == logging.WARNING

    def test_get_logger_child(self, tmp_path):
        """get_logger should create child loggers under 'app' namespace."""
        setup_logging(log_level="DEBUG", log_dir=str(tmp_path))
        child = get_logger("photoroom.client")
        assert child.name == "app.photoroom.client"

    def test_log_file_created(self, tmp_path):
        """A log file should be created in the specified directory."""
        logger = setup_logging(log_level="INFO", log_dir=str(tmp_path))
        logger.info("Test log entry")

        log_files = list(tmp_path.glob("*.log"))
        assert len(log_files) >= 1

    def test_log_file_contains_message(self, tmp_path):
        """Log file should contain the logged message."""
        logger = setup_logging(log_level="INFO", log_dir=str(tmp_path))
        logger.info("UNIQUE_TEST_MESSAGE_12345")

        log_file = tmp_path / "app.log"
        content = log_file.read_text()
        assert "UNIQUE_TEST_MESSAGE_12345" in content

    def test_console_only_no_crash(self):
        """Logging without a log_dir should work (console only)."""
        logger = setup_logging(log_level="INFO", log_dir=None)
        logger.info("Console-only log — no crash expected")
        assert True  # No exception means success

    def test_no_duplicate_handlers(self, tmp_path):
        """Calling setup_logging twice should not duplicate handlers."""
        setup_logging(log_level="INFO", log_dir=str(tmp_path))
        logger = setup_logging(log_level="INFO", log_dir=str(tmp_path))
        # Should have exactly 2 handlers (console + file)
        assert len(logger.handlers) == 2
