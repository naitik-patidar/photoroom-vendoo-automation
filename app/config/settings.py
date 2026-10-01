"""
Application configuration management.

Loads settings from environment variables and .env files.
Never hardcodes secrets — all credentials come from environment.
"""

import os
from pathlib import Path
from dataclasses import dataclass, field
from dotenv import load_dotenv


# ---------------------------------------------------------------------------
# Resolve project root (two levels up from this file: app/config/settings.py)
# ---------------------------------------------------------------------------
_THIS_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = _THIS_DIR.parent.parent

def get_app_data_dir() -> Path:
    """Return persistent user data directory for the application."""
    import sys
    if getattr(sys, 'frozen', False):
        # Running as bundled executable (PyInstaller)
        # Use ~/.photoroom_vendoo for persistence across restarts
        app_dir = Path.home() / ".photoroom_vendoo"
    else:
        # Running from source
        app_dir = PROJECT_ROOT / "data"
    
    app_dir.mkdir(parents=True, exist_ok=True)
    return app_dir

APP_DATA_DIR = get_app_data_dir()


def _load_env() -> None:
    """Load .env file from project root or executable dir if it exists."""
    import sys
    if getattr(sys, 'frozen', False):
        env_path = Path(sys.executable).parent / ".env"
    else:
        env_path = PROJECT_ROOT / ".env"
        
    if env_path.exists():
        load_dotenv(env_path)


# Load on import
_load_env()


# ---------------------------------------------------------------------------
# Settings dataclass
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class Settings:
    """Immutable application settings loaded from environment."""

    # -- Application --
    app_mode: str = field(default_factory=lambda: os.getenv("APP_MODE", "mock"))
    batch_max_workers: int = field(
        default_factory=lambda: int(os.getenv("BATCH_MAX_WORKERS", "5"))
    )

    # -- PhotoRoom --
    photoroom_api_key: str = field(
        default_factory=lambda: os.getenv("PHOTOROOM_API_KEY", "YOUR_API_KEY_HERE")
    )
    photoroom_sandbox_mode: bool = field(
        default_factory=lambda: os.getenv("PHOTOROOM_SANDBOX_MODE", "true").lower() == "true"
    )

    # -- AI / LLM --
    llm_provider: str = field(
        default_factory=lambda: os.getenv("LLM_PROVIDER", "mock")
    )
    openai_api_key: str = field(
        default_factory=lambda: os.getenv("OPENAI_API_KEY", "YOUR_API_KEY_HERE")
    )
    google_ai_api_key: str = field(
        default_factory=lambda: os.getenv("GOOGLE_AI_API_KEY", "YOUR_API_KEY_HERE")
    )

    # -- Database --
    database_path: str = field(
        default_factory=lambda: os.getenv(
            "DATABASE_PATH",
            str(APP_DATA_DIR / "db" / "app.db"),
        )
    )

    # -- Storage --
    output_dir: str = field(
        default_factory=lambda: os.getenv(
            "OUTPUT_DIR",
            str(APP_DATA_DIR / "output"),
        )
    )

    # -- Logging --
    log_level: str = field(
        default_factory=lambda: os.getenv("LOG_LEVEL", "INFO")
    )
    log_dir: str = field(
        default_factory=lambda: os.getenv(
            "LOG_DIR",
            str(APP_DATA_DIR / "logs"),
        )
    )

    # -- Derived --
    @property
    def is_mock_mode(self) -> bool:
        return self.app_mode == "mock"

    @property
    def is_production_mode(self) -> bool:
        return self.app_mode == "production"

    @property
    def has_real_photoroom_key(self) -> bool:
        return (
            self.photoroom_api_key
            and self.photoroom_api_key != "YOUR_API_KEY_HERE"
        )

    @property
    def has_real_llm_key(self) -> bool:
        if self.llm_provider == "openai":
            return self.openai_api_key and self.openai_api_key != "YOUR_API_KEY_HERE"
        elif self.llm_provider == "google":
            return self.google_ai_api_key and self.google_ai_api_key != "YOUR_API_KEY_HERE"
        return False

    def validate(self) -> list[str]:
        """
        Return a list of validation warnings (not errors — mock mode is valid).
        """
        warnings = []

        if self.is_production_mode:
            if not self.has_real_photoroom_key:
                warnings.append(
                    "APP_MODE=production but PHOTOROOM_API_KEY is a placeholder."
                )
            if not self.has_real_llm_key:
                warnings.append(
                    f"APP_MODE=production but {self.llm_provider.upper()} API key is a placeholder."
                )

        return warnings

    def __repr__(self) -> str:
        """Safe repr that never leaks secrets."""
        return (
            f"Settings("
            f"app_mode={self.app_mode!r}, "
            f"photoroom_key={'***SET***' if self.has_real_photoroom_key else '***PLACEHOLDER***'}, "
            f"llm_provider={self.llm_provider!r}, "
            f"database_path={self.database_path!r}, "
            f"log_level={self.log_level!r}"
            f")"
        )


def get_settings() -> Settings:
    """Create and return a new Settings instance from current environment."""
    return Settings()
