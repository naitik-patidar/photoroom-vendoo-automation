"""
Pytest configuration and shared fixtures.
"""

import os
import sys
import tempfile
from pathlib import Path

import pytest

# Ensure the project root is on sys.path for imports
PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


@pytest.fixture(autouse=True)
def mock_env(monkeypatch, tmp_path):
    """
    Set safe environment variables for all tests.
    Prevents tests from using real API keys or writing to real directories.
    """
    monkeypatch.setenv("APP_MODE", "mock")
    monkeypatch.setenv("PHOTOROOM_API_KEY", "TEST_KEY_NOT_REAL")
    monkeypatch.setenv("PHOTOROOM_SANDBOX_MODE", "true")
    monkeypatch.setenv("LLM_PROVIDER", "mock")
    monkeypatch.setenv("OPENAI_API_KEY", "TEST_KEY_NOT_REAL")
    monkeypatch.setenv("GOOGLE_AI_API_KEY", "TEST_KEY_NOT_REAL")
    monkeypatch.setenv("DATABASE_PATH", str(tmp_path / "test.db"))
    monkeypatch.setenv("OUTPUT_DIR", str(tmp_path / "output"))
    monkeypatch.setenv("LOG_LEVEL", "DEBUG")
    monkeypatch.setenv("LOG_DIR", str(tmp_path / "logs"))


@pytest.fixture
def sample_image_path(tmp_path) -> Path:
    """Create a minimal valid PNG file for testing."""
    from PIL import Image

    img = Image.new("RGB", (100, 100), color=(255, 0, 0))
    path = tmp_path / "test_image.png"
    img.save(path)
    return path


@pytest.fixture
def sample_images_dir(tmp_path) -> Path:
    """Create a directory with multiple test images."""
    from PIL import Image

    img_dir = tmp_path / "test_images"
    img_dir.mkdir()
    colors = [(255, 0, 0), (0, 255, 0), (0, 0, 255)]
    for i, color in enumerate(colors):
        img = Image.new("RGB", (100, 100), color=color)
        img.save(img_dir / f"product_{i+1}.png")
    return img_dir
