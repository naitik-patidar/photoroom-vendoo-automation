"""
Product repository — CRUD for product records.
"""

from datetime import datetime, timezone

from app.database.db import Database
from app.database.models import Product
from app.logging import get_logger

logger = get_logger("database.product_repo")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class ProductRepository:
    """Repository for product CRUD operations."""

    def __init__(self, db: Database):
        self.db = db

    def create(self, product: Product) -> Product:
        """Insert a product record. Returns the saved product."""
        row = product.to_db_row()
        with self.db.connection() as conn:
            conn.execute("""
                INSERT INTO products (
                    product_id, sku, title, description, brand, category,
                    subcategory, size, color, material, condition, price,
                    currency, tags, quantity, created_at, updated_at
                ) VALUES (
                    :product_id, :sku, :title, :description, :brand, :category,
                    :subcategory, :size, :color, :material, :condition, :price,
                    :currency, :tags, :quantity, :created_at, :updated_at
                )
            """, row)
        logger.info(f"Product created: {product.product_id} | {product.title!r}")
        return product

    def get(self, product_id: str) -> Product | None:
        """Get a product by ID. Returns None if not found."""
        with self.db.connection() as conn:
            row = conn.execute(
                "SELECT * FROM products WHERE product_id = ?", (product_id,)
            ).fetchone()
        return Product.from_db_row(row) if row else None

    def get_all(self) -> list[Product]:
        """Return all products, newest first."""
        with self.db.connection() as conn:
            rows = conn.execute(
                "SELECT * FROM products ORDER BY created_at DESC"
            ).fetchall()
        return [Product.from_db_row(r) for r in rows]

    def update(self, product: Product) -> Product:
        """Update all fields of an existing product."""
        product.updated_at = _now()
        row = product.to_db_row()
        with self.db.connection() as conn:
            conn.execute("""
                UPDATE products SET
                    sku=:sku, title=:title, description=:description,
                    brand=:brand, category=:category, subcategory=:subcategory,
                    size=:size, color=:color, material=:material,
                    condition=:condition, price=:price, currency=:currency,
                    tags=:tags, quantity=:quantity, updated_at=:updated_at
                WHERE product_id=:product_id
            """, row)
        logger.info(f"Product updated: {product.product_id}")
        return product

    def delete(self, product_id: str) -> bool:
        """Delete a product. Returns True if deleted."""
        with self.db.connection() as conn:
            cursor = conn.execute(
                "DELETE FROM products WHERE product_id = ?", (product_id,)
            )
        return cursor.rowcount > 0

    def count(self) -> int:
        """Return total number of products."""
        with self.db.connection() as conn:
            row = conn.execute("SELECT COUNT(*) as cnt FROM products").fetchone()
        return row["cnt"] if row else 0
