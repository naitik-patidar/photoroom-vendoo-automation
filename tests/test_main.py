"""
Tests for app.main — Application entry point.
"""

from app.main import main, ensure_directories
from app.config.settings import get_settings
from pathlib import Path
from unittest.mock import patch


class TestMain:
    """Test application main entry point."""

    @patch("PySide6.QtWidgets.QApplication.exec", return_value=0)
    @patch("app.ui.main_window.MainWindow.show")
    def test_main_returns_zero(self, mock_show, mock_exec):
        """main() should return 0 (success) in mock mode."""
        exit_code = main()
        assert exit_code == 0
        mock_show.assert_called_once()
        mock_exec.assert_called_once()

    def test_ensure_directories_creates_dirs(self, tmp_path, monkeypatch):
        """ensure_directories should create all required directories."""
        monkeypatch.setenv("OUTPUT_DIR", str(tmp_path / "output"))
        monkeypatch.setenv("DATABASE_PATH", str(tmp_path / "db" / "app.db"))
        monkeypatch.setenv("LOG_DIR", str(tmp_path / "logs"))

        settings = get_settings()
        ensure_directories(settings)

        assert (tmp_path / "output").exists()
        assert (tmp_path / "db").exists()
        assert (tmp_path / "logs").exists()

    @patch("PySide6.QtWidgets.QApplication.exec", return_value=0)
    @patch("app.ui.main_window.MainWindow.show")
    def test_main_creates_directories(self, mock_show, mock_exec, tmp_path, monkeypatch):
        """main() should create required directories on startup."""
        output_dir = tmp_path / "new_output"
        monkeypatch.setenv("OUTPUT_DIR", str(output_dir))

        main()

        assert output_dir.exists()
