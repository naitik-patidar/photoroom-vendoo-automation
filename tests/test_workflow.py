"""
Tests for app.workflow — Orchestrator, WorkflowStatus, StepResult.

These tests run end-to-end in full mock mode:
- MockPhotoRoomClient for image processing
- Real SQLite (in tmp_path) for DB
- No network calls, no external services
"""

import pytest
from pathlib import Path
from PIL import Image

from app.workflow.orchestrator import WorkflowOrchestrator
from app.workflow.status import WorkflowStatus, WorkflowState
from app.workflow.steps import StepResult, StepStatus
from app.database import create_database, Database
from app.database.job_repo import JobRepository
from app.database.product_repo import ProductRepository
from app.photoroom.mock_client import MockPhotoRoomClient
from app.photoroom.client import ProcessingStatus
from app.config.settings import get_settings
from app.config.constants import JobStatus


# ======================================================================
# Fixtures
# ======================================================================

@pytest.fixture
def db(tmp_path) -> Database:
    return create_database(str(tmp_path / "test.db"))


@pytest.fixture
def job_repo(db):
    return JobRepository(db)


@pytest.fixture
def photoroom_client():
    return MockPhotoRoomClient(simulate_delay_ms=0)


@pytest.fixture
def orchestrator(db, photoroom_client):
    settings = get_settings()
    orch = WorkflowOrchestrator(
        db=db,
        photoroom_client=photoroom_client,
        settings=settings,
    )
    yield orch
    orch.shutdown()


@pytest.fixture
def sample_image(tmp_path) -> Path:
    """A valid 100×100 PNG for workflow testing."""
    img = Image.new("RGB", (100, 100), color=(200, 100, 50))
    path = tmp_path / "product_shirt.png"
    img.save(path)
    return path


# ======================================================================
# WorkflowStatus tests
# ======================================================================

class TestWorkflowStatus:

    def test_initial_state(self):
        s = WorkflowStatus(job_id="abc")
        assert s.state == WorkflowState.IDLE
        assert s.current_step == ""
        assert s.steps_completed == []

    def test_start_sets_running(self):
        s = WorkflowStatus(job_id="abc")
        s.start("validate")
        assert s.state == WorkflowState.RUNNING
        assert s.current_step == "validate"
        assert s.started_at is not None

    def test_complete_step(self):
        s = WorkflowStatus(job_id="abc")
        s.start("validate")
        s.complete_step("validate")
        assert "validate" in s.steps_completed
        assert s.current_step == ""

    def test_fail_step(self):
        s = WorkflowStatus(job_id="abc")
        s.start("photoroom")
        s.fail_step("photoroom", "timeout")
        assert "photoroom" in s.steps_failed
        assert s.error_message == "timeout"

    def test_finish(self):
        s = WorkflowStatus(job_id="abc")
        s.start("validate")
        s.finish()
        assert s.state == WorkflowState.COMPLETED
        assert s.completed_at is not None

    def test_fail(self):
        s = WorkflowStatus(job_id="abc")
        s.fail("critical error")
        assert s.state == WorkflowState.FAILED
        assert s.error_message == "critical error"

    def test_elapsed_seconds(self):
        s = WorkflowStatus(job_id="abc")
        s.start("validate")
        s.finish()
        assert s.elapsed_seconds is not None
        assert s.elapsed_seconds >= 0

    def test_elapsed_none_before_start(self):
        s = WorkflowStatus(job_id="abc")
        assert s.elapsed_seconds is None

    def test_summary_string(self):
        s = WorkflowStatus(job_id="abc-123-xyz")
        s.start("photoroom")
        summary = s.summary()
        assert "abc-123" in summary
        assert "photoroom" in summary


# ======================================================================
# StepResult tests
# ======================================================================

class TestStepResult:

    def test_failed_property(self):
        r = StepResult(step_name="test", status=StepStatus.FAILED, success=False)
        assert r.failed is True

    def test_success_not_failed(self):
        r = StepResult(step_name="test", status=StepStatus.SUCCESS, success=True)
        assert r.failed is False


# ======================================================================
# WorkflowOrchestrator — Happy path
# ======================================================================

class TestWorkflowHappyPath:

    def test_full_pipeline_completes(self, orchestrator, job_repo, sample_image):
        """End-to-end: job goes from QUEUED → COMPLETED."""
        job = job_repo.create(str(sample_image))

        status = orchestrator.run(job.job_id)

        assert status.state == WorkflowState.COMPLETED
        assert status.error_message == ""

    def test_db_status_is_completed(self, orchestrator, job_repo, sample_image):
        """DB job record should be COMPLETED after successful run."""
        job = job_repo.create(str(sample_image))
        orchestrator.run(job.job_id)

        final_job = job_repo.get(job.job_id)
        assert final_job.status == "COMPLETED"
        assert final_job.is_terminal is True

    def test_processed_file_saved(self, orchestrator, job_repo, sample_image):
        """Job should have a processed_file path after PhotoRoom step."""
        job = job_repo.create(str(sample_image))
        status = orchestrator.run(job.job_id)

        final_job = job_repo.get(job.job_id)
        assert final_job.processed_file is not None
        assert Path(final_job.processed_file).exists()

    def test_product_created(self, orchestrator, job_repo, sample_image, db):
        """A product record should be created and linked to the job."""
        job = job_repo.create(str(sample_image))
        orchestrator.run(job.job_id)

        final_job = job_repo.get(job.job_id)
        assert final_job.product_id is not None

        product_repo = ProductRepository(db)
        product = product_repo.get(final_job.product_id)
        assert product is not None

    def test_status_steps_completed(self, orchestrator, job_repo, sample_image):
        """All 5 steps should be recorded as completed."""
        job = job_repo.create(str(sample_image))
        status = orchestrator.run(job.job_id)

        expected_steps = {
            "validate", "preserve_original", "photoroom",
            "generate_listing", "vendoo"
        }
        assert expected_steps == set(status.steps_completed)

    def test_job_history_records_all_transitions(self, orchestrator, job_repo, sample_image):
        """DB history should have entries for all status changes."""
        job = job_repo.create(str(sample_image))
        orchestrator.run(job.job_id)

        history = job_repo.get_history(job.job_id)
        statuses_seen = {h.new_status for h in history}

        # Must have gone through all these statuses
        for expected in [
            "QUEUED", "PROCESSING", "PHOTOROOM_PROCESSING",
            "PHOTOROOM_COMPLETE", "LISTING_GENERATED",
            "VENDOO_PENDING", "VENDOO_COMPLETE", "COMPLETED"
        ]:
            assert expected in statuses_seen, f"Missing status in history: {expected}"

    def test_output_file_is_png_with_transparency(self, orchestrator, job_repo, sample_image):
        """Processed output must be PNG with alpha channel."""
        job = job_repo.create(str(sample_image))
        orchestrator.run(job.job_id)

        final_job = job_repo.get(job.job_id)
        output_path = Path(final_job.processed_file)

        with Image.open(output_path) as img:
            assert img.format == "PNG"
            assert img.mode == "RGBA"

    def test_original_not_modified(self, orchestrator, job_repo, sample_image):
        """Original image must be byte-for-byte identical after workflow."""
        original_bytes = sample_image.read_bytes()

        job = job_repo.create(str(sample_image))
        orchestrator.run(job.job_id)

        assert sample_image.read_bytes() == original_bytes

    def test_progress_callback_called(self, db, photoroom_client, sample_image):
        """Progress callback should be called at least once per step."""
        events = []

        def capture(status: WorkflowStatus):
            events.append((status.state.value, status.current_step))

        settings = get_settings()
        orch = WorkflowOrchestrator(
            db=db, photoroom_client=photoroom_client,
            settings=settings, on_progress=capture,
        )
        job_repo = JobRepository(db)
        job = job_repo.create(str(sample_image))
        orch.run(job.job_id)

        assert len(events) > 0

    def test_elapsed_time_populated(self, orchestrator, job_repo, sample_image):
        """WorkflowStatus should have elapsed time after completion."""
        job = job_repo.create(str(sample_image))
        status = orchestrator.run(job.job_id)
        assert status.elapsed_seconds is not None
        assert status.elapsed_seconds >= 0


# ======================================================================
# WorkflowOrchestrator — Failure cases
# ======================================================================

class TestWorkflowFailure:

    def test_missing_image_fails(self, orchestrator, job_repo, tmp_path):
        """Non-existent image should fail at validate step."""
        job = job_repo.create(str(tmp_path / "ghost.png"))
        status = orchestrator.run(job.job_id)

        assert status.state == WorkflowState.FAILED
        assert "validate" in status.steps_failed

    def test_db_status_is_failed(self, orchestrator, job_repo, tmp_path):
        """DB job should be FAILED when workflow fails."""
        job = job_repo.create(str(tmp_path / "ghost.png"))
        orchestrator.run(job.job_id)

        final_job = job_repo.get(job.job_id)
        assert final_job.status == "FAILED"

    def test_error_message_stored_in_db(self, orchestrator, job_repo, tmp_path):
        """Error message should be persisted in the DB."""
        job = job_repo.create(str(tmp_path / "ghost.png"))
        orchestrator.run(job.job_id)

        final_job = job_repo.get(job.job_id)
        assert final_job.error_message is not None
        assert len(final_job.error_message) > 0

    def test_photoroom_failure(self, db, sample_image, job_repo):
        """PhotoRoom failure should fail the workflow at photoroom step."""
        broken_client = MockPhotoRoomClient(
            simulate_error=ProcessingStatus.RATE_LIMITED,
            simulate_delay_ms=0,
        )
        settings = get_settings()
        orch = WorkflowOrchestrator(db=db, photoroom_client=broken_client, settings=settings)

        job = job_repo.create(str(sample_image))
        status = orch.run(job.job_id)
        orch.shutdown()

        assert status.state == WorkflowState.FAILED
        assert "photoroom" in status.steps_failed

    def test_photoroom_failure_db_status(self, db, sample_image, job_repo):
        """DB status should be FAILED when PhotoRoom fails."""
        broken_client = MockPhotoRoomClient(
            simulate_error=ProcessingStatus.AUTH_ERROR,
            simulate_delay_ms=0,
        )
        settings = get_settings()
        orch = WorkflowOrchestrator(db=db, photoroom_client=broken_client, settings=settings)

        job = job_repo.create(str(sample_image))
        orch.run(job.job_id)
        orch.shutdown()

        final_job = job_repo.get(job.job_id)
        assert final_job.status == "FAILED"

    def test_job_not_found_raises(self, orchestrator):
        """Running a nonexistent job_id should raise ValueError."""
        with pytest.raises(ValueError, match="Job not found"):
            orchestrator.run("nonexistent-job-id")

    def test_one_failed_job_does_not_affect_next(
        self, orchestrator, job_repo, tmp_path, sample_image
    ):
        """Batch: failed job should not prevent subsequent jobs from running."""
        ghost_job = job_repo.create(str(tmp_path / "ghost.png"))
        real_job = job_repo.create(str(sample_image))

        results = orchestrator.run_batch([ghost_job.job_id, real_job.job_id])

        assert results[0].state == WorkflowState.FAILED
        assert results[1].state == WorkflowState.COMPLETED


# ======================================================================
# Batch workflow tests
# ======================================================================

class TestWorkflowBatch:

    def test_batch_all_complete(self, orchestrator, job_repo, sample_images_dir):
        """All valid images in a batch should complete."""
        images = list(sample_images_dir.glob("*.png"))
        jobs = [job_repo.create(str(p)) for p in images]

        results = orchestrator.run_batch([j.job_id for j in jobs])

        assert all(r.state == WorkflowState.COMPLETED for r in results)

    def test_batch_returns_one_result_per_job(self, orchestrator, job_repo, sample_images_dir):
        images = list(sample_images_dir.glob("*.png"))
        jobs = [job_repo.create(str(p)) for p in images]

        results = orchestrator.run_batch([j.job_id for j in jobs])

        assert len(results) == len(jobs)

    def test_batch_creates_separate_products(self, orchestrator, job_repo, sample_images_dir, db):
        images = list(sample_images_dir.glob("*.png"))
        jobs = [job_repo.create(str(p)) for p in images]
        orchestrator.run_batch([j.job_id for j in jobs])

        product_repo = ProductRepository(db)
        products = product_repo.get_all()
        products = product_repo.get_all()
        assert len(products) == len(jobs)


# ======================================================================
# Retry tests
# ======================================================================

class TestWorkflowRetry:
    
    def test_retry_failed_jobs(self, orchestrator, job_repo, sample_image):
        job1 = job_repo.create(str(sample_image))
        job_repo.transition(job1.job_id, "PROCESSING")
        job_repo.transition(job1.job_id, "FAILED")
        
        # Max out retries for job2
        job2 = job_repo.create(str(sample_image))
        job_repo.transition(job2.job_id, "PROCESSING")
        job_repo.transition(job2.job_id, "FAILED")
        
        for _ in range(3): # MAX_RETRY_COUNT is 3
            job_repo.transition(job2.job_id, "RETRYING")
            job_repo.transition(job2.job_id, "QUEUED")
            job_repo.transition(job2.job_id, "PROCESSING")
            job_repo.transition(job2.job_id, "FAILED")
            
        count = orchestrator.retry_failed_jobs()
        assert count == 1 # Only job1 should be queued for retry
        
        j1 = job_repo.get(job1.job_id)
        assert j1.status == "QUEUED" # It gets requeued by retry
        
    def test_retry_failed_jobs_none(self, orchestrator, job_repo, sample_image):
        job1 = job_repo.create(str(sample_image))
        orchestrator.run(job1.job_id) # completes successfully
        
        count = orchestrator.retry_failed_jobs()
        assert count == 0
