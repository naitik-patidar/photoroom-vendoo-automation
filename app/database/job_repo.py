"""
Job repository — CRUD and status tracking for processing jobs.

All database operations go through this repository.
Never write SQL elsewhere in the codebase.
"""

from datetime import datetime, timezone
from pathlib import Path

from app.database.db import Database
from app.database.models import Job, JobHistory
from app.config.constants import JobStatus
from app.logging import get_logger

logger = get_logger("database.job_repo")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# Valid status transitions
# ---------------------------------------------------------------------------

VALID_TRANSITIONS: dict[str, set[str]] = {
    JobStatus.QUEUED: {
        JobStatus.PROCESSING,
        JobStatus.FAILED,
    },
    JobStatus.PROCESSING: {
        JobStatus.PHOTOROOM_PROCESSING,
        JobStatus.FAILED,
    },
    JobStatus.PHOTOROOM_PROCESSING: {
        JobStatus.PHOTOROOM_COMPLETE,
        JobStatus.FAILED,
        JobStatus.RETRYING,
    },
    JobStatus.PHOTOROOM_COMPLETE: {
        JobStatus.LISTING_GENERATED,
        JobStatus.FAILED,
    },
    JobStatus.LISTING_GENERATED: {
        JobStatus.VENDOO_PENDING,
        JobStatus.FAILED,
    },
    JobStatus.VENDOO_PENDING: {
        JobStatus.VENDOO_COMPLETE,
        JobStatus.FAILED,
        JobStatus.RETRYING,
    },
    JobStatus.VENDOO_COMPLETE: {
        JobStatus.CROSSLISTING,
        JobStatus.COMPLETED,
    },
    JobStatus.CROSSLISTING: {
        JobStatus.COMPLETED,
        JobStatus.FAILED,
    },
    JobStatus.RETRYING: {
        JobStatus.PROCESSING,
        JobStatus.QUEUED,
        JobStatus.FAILED,
    },
    JobStatus.COMPLETED: set(),   # Terminal
    JobStatus.FAILED: {           # Can re-queue for retry
        JobStatus.RETRYING,
        JobStatus.QUEUED,
    },
}


class JobRepository:
    """
    Repository for job CRUD and status management.

    Usage:
        repo = JobRepository(db)
        job = repo.create(original_file="/path/to/image.jpg")
        repo.transition(job.job_id, "PROCESSING")
        job = repo.get(job.job_id)
    """

    def __init__(self, db: Database):
        self.db = db

    # ------------------------------------------------------------------
    # Create
    # ------------------------------------------------------------------

    def create(
        self,
        original_file: str | Path,
        product_id: str | None = None,
    ) -> Job:
        """
        Create a new job in QUEUED status.

        Args:
            original_file: Path to the source image.
            product_id: Optional linked product ID.

        Returns:
            The newly created Job.
        """
        job = Job(
            original_file=str(original_file),
            product_id=product_id,
            status=JobStatus.QUEUED,
        )
        row = job.to_db_row()

        with self.db.connection() as conn:
            conn.execute("""
                INSERT INTO jobs (
                    job_id, product_id, original_file, processed_file,
                    status, photoroom_status, listing_status, vendoo_status,
                    retry_count, error_message, created_at, updated_at
                ) VALUES (
                    :job_id, :product_id, :original_file, :processed_file,
                    :status, :photoroom_status, :listing_status, :vendoo_status,
                    :retry_count, :error_message, :created_at, :updated_at
                )
            """, row)

            self._record_history(conn, job.job_id, None, JobStatus.QUEUED, "Job created")

        logger.info(f"Job created: {job.job_id} | {Path(original_file).name}")
        return job

    # ------------------------------------------------------------------
    # Read
    # ------------------------------------------------------------------

    def get(self, job_id: str) -> Job | None:
        """Get a job by ID. Returns None if not found."""
        with self.db.connection() as conn:
            row = conn.execute(
                "SELECT * FROM jobs WHERE job_id = ?", (job_id,)
            ).fetchone()
        return Job.from_db_row(row) if row else None

    def get_all(self) -> list[Job]:
        """Return all jobs, newest first."""
        with self.db.connection() as conn:
            rows = conn.execute(
                "SELECT * FROM jobs ORDER BY created_at DESC"
            ).fetchall()
        return [Job.from_db_row(r) for r in rows]

    def get_by_status(self, status: str) -> list[Job]:
        """Return all jobs with a specific status."""
        with self.db.connection() as conn:
            rows = conn.execute(
                "SELECT * FROM jobs WHERE status = ? ORDER BY created_at DESC",
                (status,),
            ).fetchall()
        return [Job.from_db_row(r) for r in rows]

    def get_retryable(self) -> list[Job]:
        """Return all FAILED jobs that haven't exceeded max retry count."""
        from app.config.constants import MAX_RETRY_COUNT
        with self.db.connection() as conn:
            rows = conn.execute(
                """
                SELECT * FROM jobs
                WHERE status = 'FAILED' AND retry_count < ?
                ORDER BY created_at DESC
                """,
                (MAX_RETRY_COUNT,),
            ).fetchall()
        return [Job.from_db_row(r) for r in rows]

    def count_by_status(self) -> dict[str, int]:
        """Return count of jobs grouped by status."""
        with self.db.connection() as conn:
            rows = conn.execute(
                "SELECT status, COUNT(*) as cnt FROM jobs GROUP BY status"
            ).fetchall()
        return {row["status"]: row["cnt"] for row in rows}

    # ------------------------------------------------------------------
    # Status transitions
    # ------------------------------------------------------------------

    def transition(
        self,
        job_id: str,
        new_status: str,
        *,
        note: str = "",
        error_message: str | None = None,
        processed_file: str | Path | None = None,
    ) -> Job:
        """
        Transition a job to a new status.

        Validates the transition is legal (see VALID_TRANSITIONS).
        Records the change in job_history.

        Args:
            job_id: The job to update.
            new_status: Target status.
            note: Optional human-readable note for the history.
            error_message: Populated when transitioning to FAILED.
            processed_file: Populated when PhotoRoom processing completes.

        Returns:
            Updated Job object.

        Raises:
            ValueError: If job not found or transition is invalid.
        """
        job = self.get(job_id)
        if not job:
            raise ValueError(f"Job not found: {job_id}")

        old_status = job.status
        allowed = VALID_TRANSITIONS.get(old_status, set())

        if new_status not in allowed:
            raise ValueError(
                f"Invalid status transition: {old_status} → {new_status}. "
                f"Allowed: {sorted(allowed) or 'none (terminal)'}"
            )

        now = _now()
        updates: dict = {
            "status": new_status,
            "updated_at": now,
            "job_id": job_id,
        }

        # Increment retry_count when going to RETRYING
        if new_status == JobStatus.RETRYING:
            updates["retry_count"] = job.retry_count + 1

        if error_message is not None:
            updates["error_message"] = error_message

        if processed_file is not None:
            updates["processed_file"] = str(processed_file)

        with self.db.connection() as conn:
            # Build dynamic SET clause
            set_parts = [f"{k} = :{k}" for k in updates if k != "job_id"]
            conn.execute(
                f"UPDATE jobs SET {', '.join(set_parts)} WHERE job_id = :job_id",
                updates,
            )
            self._record_history(conn, job_id, old_status, new_status, note)

        logger.info(f"Job {job_id[:8]}: {old_status} → {new_status}")
        return self.get(job_id)

    def set_photoroom_status(self, job_id: str, status: str) -> None:
        """Update the photoroom_status sub-field."""
        with self.db.connection() as conn:
            conn.execute(
                "UPDATE jobs SET photoroom_status = ?, updated_at = ? WHERE job_id = ?",
                (status, _now(), job_id),
            )

    def set_listing_status(self, job_id: str, status: str) -> None:
        """Update the listing_status sub-field."""
        with self.db.connection() as conn:
            conn.execute(
                "UPDATE jobs SET listing_status = ?, updated_at = ? WHERE job_id = ?",
                (status, _now(), job_id),
            )

    def set_vendoo_status(self, job_id: str, status: str) -> None:
        """Update the vendoo_status sub-field."""
        with self.db.connection() as conn:
            conn.execute(
                "UPDATE jobs SET vendoo_status = ?, updated_at = ? WHERE job_id = ?",
                (status, _now(), job_id),
            )

    # ------------------------------------------------------------------
    # History
    # ------------------------------------------------------------------

    def get_history(self, job_id: str) -> list[JobHistory]:
        """Return full history for a job."""
        with self.db.connection() as conn:
            rows = conn.execute(
                """
                SELECT * FROM job_history
                WHERE job_id = ?
                ORDER BY occurred_at ASC
                """,
                (job_id,),
            ).fetchall()
        return [JobHistory.from_db_row(r) for r in rows]

    # ------------------------------------------------------------------
    # Delete
    # ------------------------------------------------------------------

    def delete(self, job_id: str) -> bool:
        """Delete a job and its history. Returns True if deleted."""
        with self.db.connection() as conn:
            conn.execute("DELETE FROM job_history WHERE job_id = ?", (job_id,))
            cursor = conn.execute("DELETE FROM jobs WHERE job_id = ?", (job_id,))
        return cursor.rowcount > 0

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _record_history(
        self,
        conn,
        job_id: str,
        old_status: str | None,
        new_status: str,
        note: str,
    ) -> None:
        conn.execute("""
            INSERT INTO job_history (job_id, old_status, new_status, note, occurred_at)
            VALUES (?, ?, ?, ?, ?)
        """, (job_id, old_status, new_status, note, _now()))
