"""Database package — SQLite job and product tracking."""

from app.database.db import Database
from app.database.models import Job, Product, JobHistory
from app.database.job_repo import JobRepository, VALID_TRANSITIONS
from app.database.product_repo import ProductRepository


def create_database(db_path: str) -> Database:
    """Create and initialize a Database instance."""
    db = Database(db_path)
    db.initialize()
    return db


__all__ = [
    "Database",
    "Job",
    "Product",
    "JobHistory",
    "JobRepository",
    "ProductRepository",
    "VALID_TRANSITIONS",
    "create_database",
]
