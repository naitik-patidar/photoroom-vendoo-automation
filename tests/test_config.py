"""
Tests for app.config — Settings and Constants.
"""

import os
from pathlib import Path

import pytest

from app.config.settings import Settings, get_settings
from app.config.constants import (
    APP_NAME,
    APP_VERSION,
    JobStatus,
    SUPPORTED_INPUT_FORMATS,
    PHOTOROOM_API_BASE_URL,
    MAX_RETRY_COUNT,
)


class TestSettings:
    """Test Settings configuration loading."""

    def test_settings_loads_from_env(self):
        """Settings should load values from environment variables."""
        settings = get_settings()
        assert settings.app_mode == "mock"
        assert settings.log_level == "DEBUG"

    def test_settings_mock_mode_detection(self):
        """is_mock_mode should be True when APP_MODE=mock."""
        settings = get_settings()
        assert settings.is_mock_mode is True
        assert settings.is_production_mode is False

    def test_settings_placeholder_key_detection(self):
        """Placeholder keys should not be considered real."""
        settings = Settings(photoroom_api_key="YOUR_API_KEY_HERE")
        assert settings.has_real_photoroom_key is False

    def test_settings_real_key_detection(self):
        """Non-placeholder keys should be considered real."""
        settings = Settings(photoroom_api_key="pr_live_abc123xyz")
        assert settings.has_real_photoroom_key is True

    def test_settings_repr_no_secrets(self):
        """repr() must never contain actual API keys."""
        settings = Settings(
            photoroom_api_key="pr_live_SUPER_SECRET_KEY_123"
        )
        repr_str = repr(settings)
        assert "SUPER_SECRET_KEY" not in repr_str
        assert "***SET***" in repr_str

    def test_settings_repr_placeholder(self):
        """repr() should show PLACEHOLDER when key is not set."""
        settings = Settings(photoroom_api_key="YOUR_API_KEY_HERE")
        repr_str = repr(settings)
        assert "***PLACEHOLDER***" in repr_str

    def test_settings_validation_mock_mode(self):
        """Mock mode should produce no warnings even with placeholder keys."""
        settings = Settings(app_mode="mock")
        warnings = settings.validate()
        assert len(warnings) == 0

    def test_settings_validation_production_missing_keys(self):
        """Production mode with placeholder keys should produce warnings."""
        settings = Settings(
            app_mode="production",
            photoroom_api_key="YOUR_API_KEY_HERE",
            llm_provider="openai",
            openai_api_key="YOUR_API_KEY_HERE",
        )
        warnings = settings.validate()
        assert len(warnings) >= 2
        assert any("PHOTOROOM" in w for w in warnings)
        assert any("OPENAI" in w for w in warnings)

    def test_settings_database_path(self):
        """Database path should be set from environment."""
        settings = get_settings()
        assert settings.database_path is not None
        assert "test.db" in settings.database_path


class TestConstants:
    """Test application constants."""

    def test_app_name(self):
        assert APP_NAME == "PhotoRoom-Vendoo Automation"

    def test_app_version(self):
        assert APP_VERSION == "0.1.0"

    def test_supported_formats(self):
        assert ".jpg" in SUPPORTED_INPUT_FORMATS
        assert ".png" in SUPPORTED_INPUT_FORMATS
        assert ".webp" in SUPPORTED_INPUT_FORMATS

    def test_job_statuses(self):
        assert JobStatus.QUEUED == "QUEUED"
        assert JobStatus.COMPLETED == "COMPLETED"
        assert JobStatus.FAILED == "FAILED"
        assert "QUEUED" in JobStatus.ALL
        assert "COMPLETED" in JobStatus.ALL

    def test_photoroom_api_url(self):
        assert "sdk.photoroom.com" in PHOTOROOM_API_BASE_URL

    def test_retry_config(self):
        assert MAX_RETRY_COUNT >= 1
        assert MAX_RETRY_COUNT <= 10
