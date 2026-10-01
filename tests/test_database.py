"""
Tests for app.database — Database, models, JobRepository, ProductRepository.
"""

import pytest
from pathlib import Path

from app.database.db import Database
from app.database.models import Job, Product, JobHistory
from app.database.job_repo import JobRepository, VALID_TRANSITIONS
from app.database.product_repo import ProductRepository
from app.database import create_database
from app.config.constants import JobStatus, MAX_RETRY_COUNT


# ======================================================================
# Fixtures
# ======================================================================

@pytest.fixture
def db(tmp_path) -> Database:
    """Provide a fresh initialized Database for each test."""
    database = Database(tmp_path / "test.db")
    database.initialize()
    return database


@pytest.fixture
def job_repo(db) -> JobRepository:
    return JobRepository(db)


@pytest.fixture
def product_repo(db) -> ProductRepository:
    return ProductRepository(db)


@pytest.fixture
def sample_product() -> Product:
    return Product(
        title="Vintage Nike Tee",
        brand="Nike",
        category="Clothing",
        size="M",
        color="White",
        condition="Good",
        price=25.00,
        tags=["vintage", "nike", "tshirt"],
    )


# ======================================================================
# Database initialization tests
# ======================================================================

class TestDatabase:

    def test_initialize_creates_file(self, tmp_path):
        db = Database(tmp_path / "new.db")
        db.initialize()
        assert (tmp_path / "new.db").exists()

    def test_initialize_idempotent(self, tmp_path):
        """Calling initialize twice must not raise."""
        db = Database(tmp_path / "app.db")
        db.initialize()
        db.initialize()  # Should not raise

    def test_is_initialized_after_init(self, db):
        assert db.is_initialized() is True

    def test_is_initialized_before_init(self, tmp_path):
        db = Database(tmp_path / "fresh.db")
        assert db.is_initialized() is False

    def test_schema_version(self, db):
        assert db.get_schema_version() >= 1

    def test_connection_commits_on_success(self, db):
        with db.connection() as conn:
            conn.execute(
                "INSERT INTO products (product_id, created_at, updated_at) VALUES (?, ?, ?)",
                ("test-id", "2025-01-01", "2025-01-01"),
            )

        with db.connection() as conn:
            row = conn.execute(
                "SELECT product_id FROM products WHERE product_id = ?", ("test-id",)
            ).fetchone()
        assert row is not None

    def test_connection_rollback_on_error(self, db):
        with pytest.raises(Exception):
            with db.connection() as conn:
                conn.execute(
                    "INSERT INTO products (product_id, created_at, updated_at) VALUES (?, ?, ?)",
                    ("rollback-test", "2025-01-01", "2025-01-01"),
                )
                raise RuntimeError("Force rollback")

        with db.connection() as conn:
            row = conn.execute(
                "SELECT product_id FROM products WHERE product_id = ?", ("rollback-test",)
            ).fetchone()
        assert row is None

    def test_create_database_factory(self, tmp_path):
        db = create_database(str(tmp_path / "factory.db"))
        assert db.is_initialized()


# ======================================================================
# Model tests
# ======================================================================

class TestJobModel:

    def test_default_status_is_queued(self):
        job = Job(original_file="/img/shirt.jpg")
        assert job.status == "QUEUED"

    def test_is_terminal_completed(self):
        job = Job(original_file="x.jpg", status="COMPLETED")
        assert job.is_terminal is True

    def test_is_terminal_failed(self):
        job = Job(original_file="x.jpg", status="FAILED")
        assert job.is_terminal is True

    def test_is_not_terminal_queued(self):
        job = Job(original_file="x.jpg", status="QUEUED")
        assert job.is_terminal is False

    def test_can_retry_failed_low_count(self):
        job = Job(original_file="x.jpg", status="FAILED", retry_count=0)
        assert job.can_retry is True

    def test_cannot_retry_max_count(self):
        job = Job(original_file="x.jpg", status="FAILED", retry_count=MAX_RETRY_COUNT)
        assert job.can_retry is False

    def test_cannot_retry_non_failed(self):
        job = Job(original_file="x.jpg", status="COMPLETED")
        assert job.can_retry is False

    def test_original_path(self):
        job = Job(original_file="/data/shirt.jpg")
        assert job.original_path == Path("/data/shirt.jpg")

    def test_original_path_none(self):
        job = Job(original_file="")
        assert job.original_path is None

    def test_roundtrip_serialization(self):
        job = Job(original_file="/img/shirt.jpg", status="QUEUED", retry_count=1)
        row = job.to_db_row()
        # Simulate a sqlite3.Row by using a dict — from_db_row accepts dict-like
        class FakeRow(dict):
            pass
        fake = FakeRow(row)
        restored = Job.from_db_row(fake)
        assert restored.job_id == job.job_id
        assert restored.status == job.status
        assert restored.retry_count == job.retry_count


class TestProductModel:

    def test_default_currency_usd(self):
        p = Product()
        assert p.currency == "USD"

    def test_tags_serialized_as_json(self):
        p = Product(tags=["a", "b", "c"])
        row = p.to_db_row()
        assert row["tags"] == '["a", "b", "c"]'

    def test_tags_deserialized_from_json(self):
        p = Product(tags=["x", "y"])
        row = p.to_db_row()

        class FakeRow(dict):
            pass
        restored = Product.from_db_row(FakeRow(row))
        assert restored.tags == ["x", "y"]

    def test_empty_tags_default(self):
        p = Product()
        assert p.tags == []

    def test_roundtrip(self):
        p = Product(title="Test", price=9.99, tags=["tag1"])
        row = p.to_db_row()

        class FakeRow(dict):
            pass
        restored = Product.from_db_row(FakeRow(row))
        assert restored.title == "Test"
        assert restored.price == 9.99
        assert restored.tags == ["tag1"]


# ======================================================================
# JobRepository tests
# ======================================================================

class TestJobRepository:

    def test_create_job(self, job_repo):
        job = job_repo.create("/img/shirt.jpg")
        assert job.job_id is not None
        assert job.status == "QUEUED"
        assert job.original_file == "/img/shirt.jpg"

    def test_create_with_product_id(self, job_repo, product_repo):
        product = product_repo.create(Product(title="Test Product"))
        job = job_repo.create("/img/shirt.jpg", product_id=product.product_id)
        assert job.product_id == product.product_id

    def test_get_returns_job(self, job_repo):
        created = job_repo.create("/img/shirt.jpg")
        fetched = job_repo.get(created.job_id)
        assert fetched is not None
        assert fetched.job_id == created.job_id

    def test_get_returns_none_for_missing(self, job_repo):
        assert job_repo.get("nonexistent-id") is None

    def test_get_all(self, job_repo):
        job_repo.create("/img/a.jpg")
        job_repo.create("/img/b.jpg")
        all_jobs = job_repo.get_all()
        assert len(all_jobs) == 2

    def test_get_by_status(self, job_repo):
        job_repo.create("/img/a.jpg")
        job_repo.create("/img/b.jpg")
        queued = job_repo.get_by_status("QUEUED")
        assert len(queued) == 2

    def test_get_by_status_empty(self, job_repo):
        results = job_repo.get_by_status("COMPLETED")
        assert results == []

    def test_count_by_status(self, job_repo):
        job_repo.create("/img/a.jpg")
        job_repo.create("/img/b.jpg")
        counts = job_repo.count_by_status()
        assert counts["QUEUED"] == 2

    def test_delete_job(self, job_repo):
        job = job_repo.create("/img/shirt.jpg")
        result = job_repo.delete(job.job_id)
        assert result is True
        assert job_repo.get(job.job_id) is None

    def test_delete_nonexistent(self, job_repo):
        assert job_repo.delete("fake-id") is False

    # -- Status transitions --

    def test_valid_transition_queued_to_processing(self, job_repo):
        job = job_repo.create("/img/shirt.jpg")
        updated = job_repo.transition(job.job_id, "PROCESSING")
        assert updated.status == "PROCESSING"

    def test_valid_transition_chain(self, job_repo):
        """Walk a job through the happy path."""
        job = job_repo.create("/img/shirt.jpg")
        job_repo.transition(job.job_id, "PROCESSING")
        job_repo.transition(job.job_id, "PHOTOROOM_PROCESSING")
        job_repo.transition(job.job_id, "PHOTOROOM_COMPLETE", processed_file="/out/shirt_processed.png")
        job_repo.transition(job.job_id, "LISTING_GENERATED")
        job_repo.transition(job.job_id, "VENDOO_PENDING")
        job_repo.transition(job.job_id, "VENDOO_COMPLETE")
        final = job_repo.transition(job.job_id, "COMPLETED")
        assert final.status == "COMPLETED"
        assert final.is_terminal is True

    def test_processed_file_set_on_transition(self, job_repo):
        job = job_repo.create("/img/shirt.jpg")
        job_repo.transition(job.job_id, "PROCESSING")
        job_repo.transition(job.job_id, "PHOTOROOM_PROCESSING")
        updated = job_repo.transition(
            job.job_id, "PHOTOROOM_COMPLETE",
            processed_file="/out/shirt_processed.png"
        )
        assert updated.processed_file == "/out/shirt_processed.png"

    def test_invalid_transition_raises(self, job_repo):
        job = job_repo.create("/img/shirt.jpg")
        with pytest.raises(ValueError, match="Invalid status transition"):
            job_repo.transition(job.job_id, "COMPLETED")

    def test_transition_to_terminal_raises_on_further_transition(self, job_repo):
        job = job_repo.create("/img/shirt.jpg")
        job_repo.transition(job.job_id, "PROCESSING")
        job_repo.transition(job.job_id, "PHOTOROOM_PROCESSING")
        job_repo.transition(job.job_id, "PHOTOROOM_COMPLETE")
        job_repo.transition(job.job_id, "LISTING_GENERATED")
        job_repo.transition(job.job_id, "VENDOO_PENDING")
        job_repo.transition(job.job_id, "VENDOO_COMPLETE")
        job_repo.transition(job.job_id, "COMPLETED")
        with pytest.raises(ValueError):
            job_repo.transition(job.job_id, "PROCESSING")

    def test_transition_to_failed_with_message(self, job_repo):
        job = job_repo.create("/img/shirt.jpg")
        job_repo.transition(job.job_id, "PROCESSING")
        updated = job_repo.transition(
            job.job_id, "FAILED",
            error_message="PhotoRoom API timeout"
        )
        assert updated.status == "FAILED"
        assert updated.error_message == "PhotoRoom API timeout"

    def test_retry_increments_count(self, job_repo):
        job = job_repo.create("/img/shirt.jpg")
        job_repo.transition(job.job_id, "PROCESSING")
        job_repo.transition(job.job_id, "PHOTOROOM_PROCESSING")
        job_repo.transition(job.job_id, "FAILED")
        job_repo.transition(job.job_id, "QUEUED")       # re-queue
        job_repo.transition(job.job_id, "PROCESSING")
        job_repo.transition(job.job_id, "PHOTOROOM_PROCESSING")
        updated = job_repo.transition(job.job_id, "RETRYING")
        assert updated.retry_count == 1

    def test_get_retryable(self, job_repo):
        job = job_repo.create("/img/shirt.jpg")
        job_repo.transition(job.job_id, "PROCESSING")
        job_repo.transition(job.job_id, "FAILED")
        retryable = job_repo.get_retryable()
        assert len(retryable) == 1

    def test_get_retryable_excludes_max_retries(self, job_repo):
        import app.database.job_repo as jr_module
        original = jr_module.MAX_RETRY_COUNT if hasattr(jr_module, "MAX_RETRY_COUNT") else None

        job = job_repo.create("/img/shirt.jpg")
        job_repo.transition(job.job_id, "PROCESSING")
        job_repo.transition(job.job_id, "FAILED")

        # Manually set retry_count to max
        with job_repo.db.connection() as conn:
            conn.execute(
                "UPDATE jobs SET retry_count = ? WHERE job_id = ?",
                (MAX_RETRY_COUNT, job.job_id),
            )

        retryable = job_repo.get_retryable()
        assert len(retryable) == 0

    def test_set_photoroom_status(self, job_repo):
        job = job_repo.create("/img/shirt.jpg")
        job_repo.set_photoroom_status(job.job_id, "processing")
        updated = job_repo.get(job.job_id)
        assert updated.photoroom_status == "processing"

    def test_set_listing_status(self, job_repo):
        job = job_repo.create("/img/shirt.jpg")
        job_repo.set_listing_status(job.job_id, "generated")
        updated = job_repo.get(job.job_id)
        assert updated.listing_status == "generated"

    def test_set_vendoo_status(self, job_repo):
        job = job_repo.create("/img/shirt.jpg")
        job_repo.set_vendoo_status(job.job_id, "pending")
        updated = job_repo.get(job.job_id)
        assert updated.vendoo_status == "pending"

    # -- History --

    def test_history_recorded_on_create(self, job_repo):
        job = job_repo.create("/img/shirt.jpg")
        history = job_repo.get_history(job.job_id)
        assert len(history) == 1
        assert history[0].new_status == "QUEUED"
        assert history[0].old_status is None

    def test_history_recorded_on_transition(self, job_repo):
        job = job_repo.create("/img/shirt.jpg")
        job_repo.transition(job.job_id, "PROCESSING", note="Starting work")
        history = job_repo.get_history(job.job_id)
        assert len(history) == 2
        assert history[1].old_status == "QUEUED"
        assert history[1].new_status == "PROCESSING"
        assert history[1].note == "Starting work"

    def test_history_empty_for_unknown_job(self, job_repo):
        assert job_repo.get_history("nonexistent") == []

    def test_transition_nonexistent_job_raises(self, job_repo):
        with pytest.raises(ValueError, match="Job not found"):
            job_repo.transition("fake-id", "PROCESSING")


# ======================================================================
# ProductRepository tests
# ======================================================================

class TestProductRepository:

    def test_create_product(self, product_repo, sample_product):
        saved = product_repo.create(sample_product)
        assert saved.product_id == sample_product.product_id
        assert saved.title == "Vintage Nike Tee"

    def test_get_product(self, product_repo, sample_product):
        product_repo.create(sample_product)
        fetched = product_repo.get(sample_product.product_id)
        assert fetched is not None
        assert fetched.title == sample_product.title
        assert fetched.tags == sample_product.tags

    def test_get_returns_none_for_missing(self, product_repo):
        assert product_repo.get("nonexistent") is None

    def test_get_all(self, product_repo):
        product_repo.create(Product(title="Item A"))
        product_repo.create(Product(title="Item B"))
        all_products = product_repo.get_all()
        assert len(all_products) == 2

    def test_update_product(self, product_repo, sample_product):
        product_repo.create(sample_product)
        sample_product.title = "Updated Title"
        sample_product.price = 35.00
        updated = product_repo.update(sample_product)
        fetched = product_repo.get(sample_product.product_id)
        assert fetched.title == "Updated Title"
        assert fetched.price == 35.00

    def test_delete_product(self, product_repo, sample_product):
        product_repo.create(sample_product)
        result = product_repo.delete(sample_product.product_id)
        assert result is True
        assert product_repo.get(sample_product.product_id) is None

    def test_delete_nonexistent(self, product_repo):
        assert product_repo.delete("fake-id") is False

    def test_count(self, product_repo):
        assert product_repo.count() == 0
        product_repo.create(Product(title="A"))
        product_repo.create(Product(title="B"))
        assert product_repo.count() == 2

    def test_tags_preserved_through_db(self, product_repo):
        p = Product(title="Tagged", tags=["vintage", "nike", "rare"])
        product_repo.create(p)
        fetched = product_repo.get(p.product_id)
        assert fetched.tags == ["vintage", "nike", "rare"]

    def test_price_preserved(self, product_repo):
        p = Product(title="Priced", price=49.99)
        product_repo.create(p)
        fetched = product_repo.get(p.product_id)
        assert abs(fetched.price - 49.99) < 0.001


# ======================================================================
# Valid transition map tests
# ======================================================================

class TestValidTransitions:

    def test_queued_can_go_to_processing(self):
        assert "PROCESSING" in VALID_TRANSITIONS["QUEUED"]

    def test_completed_has_no_transitions(self):
        assert VALID_TRANSITIONS["COMPLETED"] == set()

    def test_failed_can_requeue(self):
        assert "QUEUED" in VALID_TRANSITIONS["FAILED"]

    def test_all_statuses_have_transition_entries(self):
        for status in JobStatus.ALL:
            assert status in VALID_TRANSITIONS, f"{status} missing from VALID_TRANSITIONS"
