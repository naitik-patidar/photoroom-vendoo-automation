"""
Data models for database entities.

These are plain dataclasses — no ORM magic.
Serialization to/from sqlite3.Row is handled explicitly.
"""

import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _new_id() -> str:
    return str(uuid.uuid4())


# ---------------------------------------------------------------------------
# Product model
# ---------------------------------------------------------------------------

@dataclass
class Product:
    """
    Represents a product listing record.

    All fields are optional except product_id — AI generates most of them.
    The rule: AI must NEVER invent important product facts (price, condition, SKU).
    Those must come from the user or real product data.
    """

    product_id: str = field(default_factory=_new_id)
    sku: str = ""
    title: str = ""
    description: str = ""
    brand: str = ""
    category: str = ""
    subcategory: str = ""
    size: str = ""
    color: str = ""
    material: str = ""
    condition: str = ""
    price: float = 0.0
    currency: str = "USD"
    tags: list[str] = field(default_factory=list)
    quantity: int = 1
    created_at: str = field(default_factory=_now)
    updated_at: str = field(default_factory=_now)

    def to_db_row(self) -> dict:
        """Serialize to a dict suitable for INSERT/UPDATE."""
        return {
            "product_id": self.product_id,
            "sku": self.sku,
            "title": self.title,
            "description": self.description,
            "brand": self.brand,
            "category": self.category,
            "subcategory": self.subcategory,
            "size": self.size,
            "color": self.color,
            "material": self.material,
            "condition": self.condition,
            "price": self.price,
            "currency": self.currency,
            "tags": json.dumps(self.tags),
            "quantity": self.quantity,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_db_row(cls, row) -> "Product":
        """Deserialize from a sqlite3.Row."""
        d = dict(row)
        tags_raw = d.get("tags", "[]") or "[]"
        try:
            tags = json.loads(tags_raw)
        except (json.JSONDecodeError, TypeError):
            tags = []
        return cls(
            product_id=d["product_id"],
            sku=d.get("sku") or "",
            title=d.get("title") or "",
            description=d.get("description") or "",
            brand=d.get("brand") or "",
            category=d.get("category") or "",
            subcategory=d.get("subcategory") or "",
            size=d.get("size") or "",
            color=d.get("color") or "",
            material=d.get("material") or "",
            condition=d.get("condition") or "",
            price=d.get("price") or 0.0,
            currency=d.get("currency") or "USD",
            tags=tags,
            quantity=d.get("quantity") or 1,
            created_at=d.get("created_at") or _now(),
            updated_at=d.get("updated_at") or _now(),
        )


# ---------------------------------------------------------------------------
# Job model
# ---------------------------------------------------------------------------

@dataclass
class Job:
    """
    Represents a processing job for a single image.

    Tracks the full lifecycle from image receipt to Vendoo cross-listing.
    One job = one image = one product listing attempt.
    """

    job_id: str = field(default_factory=_new_id)
    product_id: str | None = None
    original_file: str = ""
    processed_file: str | None = None
    status: str = "QUEUED"
    photoroom_status: str | None = None
    listing_status: str | None = None
    vendoo_status: str | None = None
    retry_count: int = 0
    error_message: str | None = None
    created_at: str = field(default_factory=_now)
    updated_at: str = field(default_factory=_now)

    @property
    def original_path(self) -> Path | None:
        return Path(self.original_file) if self.original_file else None

    @property
    def processed_path(self) -> Path | None:
        return Path(self.processed_file) if self.processed_file else None

    @property
    def is_terminal(self) -> bool:
        """True if the job has reached a final state (no more transitions expected)."""
        return self.status in ("COMPLETED", "FAILED")

    @property
    def can_retry(self) -> bool:
        """True if the job can be retried."""
        from app.config.constants import MAX_RETRY_COUNT
        return self.status == "FAILED" and self.retry_count < MAX_RETRY_COUNT

    def to_db_row(self) -> dict:
        return {
            "job_id": self.job_id,
            "product_id": self.product_id,
            "original_file": self.original_file,
            "processed_file": self.processed_file,
            "status": self.status,
            "photoroom_status": self.photoroom_status,
            "listing_status": self.listing_status,
            "vendoo_status": self.vendoo_status,
            "retry_count": self.retry_count,
            "error_message": self.error_message,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_db_row(cls, row) -> "Job":
        d = dict(row)
        return cls(
            job_id=d["job_id"],
            product_id=d.get("product_id"),
            original_file=d.get("original_file") or "",
            processed_file=d.get("processed_file"),
            status=d.get("status") or "QUEUED",
            photoroom_status=d.get("photoroom_status"),
            listing_status=d.get("listing_status"),
            vendoo_status=d.get("vendoo_status"),
            retry_count=d.get("retry_count") or 0,
            error_message=d.get("error_message"),
            created_at=d.get("created_at") or _now(),
            updated_at=d.get("updated_at") or _now(),
        )


# ---------------------------------------------------------------------------
# JobHistory model
# ---------------------------------------------------------------------------

@dataclass
class JobHistory:
    """Records each status transition for a job."""

    history_id: int | None = None
    job_id: str = ""
    old_status: str | None = None
    new_status: str = ""
    note: str = ""
    occurred_at: str = field(default_factory=_now)

    @classmethod
    def from_db_row(cls, row) -> "JobHistory":
        d = dict(row)
        return cls(
            history_id=d.get("history_id"),
            job_id=d["job_id"],
            old_status=d.get("old_status"),
            new_status=d["new_status"],
            note=d.get("note") or "",
            occurred_at=d.get("occurred_at") or _now(),
        )
