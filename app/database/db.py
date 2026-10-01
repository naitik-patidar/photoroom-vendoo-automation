"""
SQLite database connection management.

Provides:
- Database initialization (schema creation)
- Connection context manager (thread-safe, WAL mode)
- Schema version tracking
"""

import sqlite3
import threading
from contextlib import contextmanager
from pathlib import Path
from datetime import datetime, timezone

from app.database.schema import ALL_MIGRATIONS, SCHEMA_VERSION
from app.logging import get_logger

logger = get_logger("database.db")

# Thread-local storage for connections (each thread gets its own)
_local = threading.local()


class Database:
    """
    SQLite database manager.

    Usage:
        db = Database("./data/db/app.db")
        db.initialize()

        with db.connection() as conn:
            conn.execute("SELECT * FROM jobs")
    """

    def __init__(self, db_path: str | Path):
        self.db_path = Path(db_path)
        self._initialized = False

    def initialize(self) -> None:
        """
        Create the database file and apply all schema migrations.
        Idempotent — safe to call multiple times.
        """
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        with self.connection() as conn:
            # Enable WAL mode for better concurrency
            conn.execute("PRAGMA journal_mode=WAL;")
            conn.execute("PRAGMA foreign_keys=ON;")

            # Apply all DDL statements
            for sql in ALL_MIGRATIONS:
                conn.execute(sql)

            # Store schema version
            conn.execute("""
                CREATE TABLE IF NOT EXISTS schema_version (
                    version INTEGER PRIMARY KEY,
                    applied_at TEXT NOT NULL
                );
            """)
            conn.execute("""
                INSERT OR IGNORE INTO schema_version (version, applied_at)
                VALUES (?, ?);
            """, (SCHEMA_VERSION, _now()))

        self._initialized = True
        logger.info(f"Database initialized: {self.db_path} (schema v{SCHEMA_VERSION})")

    @contextmanager
    def connection(self):
        """
        Context manager that yields a sqlite3 connection.

        - Commits on clean exit
        - Rolls back on exception
        - Uses row_factory for dict-like access
        """
        conn = sqlite3.connect(
            str(self.db_path),
            detect_types=sqlite3.PARSE_DECLTYPES,
            check_same_thread=False,
        )
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys=ON;")
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def get_schema_version(self) -> int:
        """Return the current schema version stored in the database."""
        try:
            with self.connection() as conn:
                row = conn.execute(
                    "SELECT MAX(version) as v FROM schema_version"
                ).fetchone()
                return row["v"] if row and row["v"] else 0
        except Exception:
            return 0

    def is_initialized(self) -> bool:
        """Check if the database has been initialized."""
        if not self.db_path.exists():
            return False
        try:
            with self.connection() as conn:
                conn.execute("SELECT 1 FROM jobs LIMIT 1")
            return True
        except Exception:
            return False


def _now() -> str:
    """Return current UTC time as ISO 8601 string."""
    return datetime.now(timezone.utc).isoformat()
