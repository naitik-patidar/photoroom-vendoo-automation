"""
Workflow Orchestrator — connects all components and drives jobs to completion.

Pipeline for a single job:
    1. VALIDATE     — check image is usable
    2. PRESERVE     — copy original to output dir
    3. PHOTOROOM    — remove background
    4. LISTING      — generate product listing data (AI stub for now)
    5. VENDOO       — hand off to Vendoo connector (mock for now)
    6. COMPLETE     — mark job done

Each step updates the database status. Any step failure → FAILED with
error message stored. All steps are independently observable via WorkflowStatus.

Design constraints enforced here:
- Original images are NEVER modified (enforced by image engine)
- Each step is logged
- Errors in one step never corrupt other steps or other jobs
- The orchestrator does NOT know which implementations are injected —
  it only depends on interfaces (PhotoRoomClient, VendooConnector)
"""

import time
import concurrent.futures
from pathlib import Path
from typing import Callable

from app.database.db import Database
from app.database.job_repo import JobRepository
from app.database.product_repo import ProductRepository
from app.database.models import Job, Product
from app.images.validator import validate_image
from app.images.file_manager import preserve_original, build_processed_path, ensure_output_dir
from app.photoroom.client import PhotoRoomClient, ProcessingStatus
from app.listings.generator import ListingGenerator
from app.listings.schemas import ProductListing
from app.vendoo.connector import VendooConnector
from app.ai.schemas import ProcessImageCommand
from app.config.constants import JobStatus
from app.config.settings import Settings
from app.workflow.steps import StepResult, StepStatus
from app.workflow.status import WorkflowStatus, WorkflowState
from app.logging import get_logger

logger = get_logger("workflow.orchestrator")

# Type alias for progress callbacks (used by UI in Task 10)
ProgressCallback = Callable[[WorkflowStatus], None]


class WorkflowOrchestrator:
    """
    Drives a single image through the full automation pipeline.

    Injected dependencies (all are interfaces, not concrete classes):
    - db: Database
    - photoroom_client: PhotoRoomClient
    - vendoo_connector: VendooConnector (Task 8)
    - settings: Settings

    Usage:
        orchestrator = WorkflowOrchestrator(db, photoroom_client, settings)
        status = orchestrator.run(job_id, on_progress=my_callback)
    """

    def __init__(
        self,
        db: Database,
        photoroom_client: PhotoRoomClient,
        settings: Settings,
        listing_generator: ListingGenerator = None,
        vendoo_connector: VendooConnector = None,
        on_progress: ProgressCallback | None = None,
    ):
        self.db = db
        self.photoroom_client = photoroom_client
        self.listing_generator = listing_generator
        self.vendoo_connector = vendoo_connector
        self.settings = settings
        self._on_progress = on_progress

        self.job_repo = JobRepository(db)
        self.product_repo = ProductRepository(db)
        
        # Persistent ThreadPoolExecutor for graceful shutdown and batching
        max_workers = getattr(self.settings, 'batch_max_workers', 5)
        self.executor = concurrent.futures.ThreadPoolExecutor(
            max_workers=max_workers,
            thread_name_prefix="WorkflowWorker"
        )

        logger.info(
            f"WorkflowOrchestrator initialized "
            f"(mode={settings.app_mode}, "
            f"photoroom={photoroom_client.get_client_info()['type']})"
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def run(self, job_id: str, command: ProcessImageCommand | None = None) -> WorkflowStatus:
        """
        Execute the full pipeline for a job.

        Args:
            job_id: ID of the job to process (must be in QUEUED status).
            command: Optional parsed command with constraints (price, title, etc).

        Returns:
            WorkflowStatus with final state and step history.
        """
        job = self.job_repo.get(job_id)
        if not job:
            raise ValueError(f"Job not found: {job_id}")

        status = WorkflowStatus(
            job_id=job_id,
            original_file=job.original_file,
        )

        logger.info(f"Starting workflow for job {job_id[:8]} | {Path(job.original_file).name}")

        try:
            # Step 1: Validate
            result = self._step_validate(job, status)
            if result.failed:
                return self._fail(job, status, result)

            # Step 2: Preserve original
            result = self._step_preserve(job, status)
            if result.failed:
                return self._fail(job, status, result)

            # Step 3: PhotoRoom
            result = self._step_photoroom(job, status)
            if result.failed:
                return self._fail(job, status, result)

            processed_path = result.output_path

            # Step 4: Generate listing
            result = self._step_generate_listing(job, status, processed_path, command)
            if result.failed:
                return self._fail(job, status, result)

            product_id = result.product_id

            # Step 5: Vendoo
            result = self._step_vendoo(job, status, product_id, processed_path)
            if result.failed:
                return self._fail(job, status, result)

            # Step 6: Complete
            self.job_repo.transition(
                job_id, JobStatus.COMPLETED,
                note="All steps completed successfully"
            )
            status.finish()
            self._notify(status)

            logger.info(
                f"Workflow COMPLETED for job {job_id[:8]} "
                f"in {status.elapsed_seconds:.1f}s"
            )
            return status

        except Exception as e:
            logger.exception(f"Unexpected error in workflow for job {job_id[:8]}: {e}")
            self._safe_fail_job(job_id, str(e))
            status.fail(str(e))
            return status

    def run_batch(self, job_ids: list[str], command: ProcessImageCommand | None = None) -> list[WorkflowStatus]:
        """
        Run multiple jobs concurrently using the persistent ThreadPoolExecutor.
        One job failing does NOT stop others.
        """
        logger.info(f"Starting batch of {len(job_ids)} jobs.")
        
        results = []
        
        def _process_job(job_id):
            logger.info(f"Batch worker picked up job {job_id[:8]}")
            try:
                return self.run(job_id, command)
            except Exception as e:
                logger.error(f"Batch: job {job_id[:8]} raised unhandled error: {e}")
                return WorkflowStatus(
                    job_id=job_id, 
                    state=WorkflowState.FAILED,
                    error_message=str(e)
                )

        # Map preserves order of job_ids
        for result in self.executor.map(_process_job, job_ids):
            results.append(result)
                
        return results

    def retry_failed_jobs(self) -> int:
        """
        Finds all retryable FAILED jobs and re-queues them.
        Returns the number of jobs queued for retry.
        """
        retryable_jobs = self.job_repo.get_retryable()
        if not retryable_jobs:
            logger.info("No retryable jobs found.")
            return 0
            
        queued_count = 0
        job_ids = []
        for job in retryable_jobs:
            try:
                self.job_repo.transition(
                    job.job_id, 
                    JobStatus.RETRYING,
                    note="Retrying failed job"
                )
                self.job_repo.transition(
                    job.job_id,
                    JobStatus.QUEUED,
                    note="Re-queued for retry"
                )
                job_ids.append(job.job_id)
                queued_count += 1
            except Exception as e:
                logger.error(f"Failed to requeue job {job.job_id[:8]}: {e}")
                
        if queued_count > 0:
            logger.info(f"Re-queued {queued_count} jobs for retry. Processing...")
            # We can run them using run_batch or let the caller do it. 
            # We'll dispatch them asynchronously via submit so we don't block.
            for jid in job_ids:
                self.executor.submit(self.run, jid, None)
                
        return queued_count

    def shutdown(self) -> None:
        """Gracefully shut down the thread pool."""
        logger.info("Shutting down WorkflowOrchestrator thread pool...")
        self.executor.shutdown(wait=True, cancel_futures=True)
        logger.info("Orchestrator shutdown complete.")

    # ------------------------------------------------------------------
    # Individual steps
    # ------------------------------------------------------------------

    def _step_validate(self, job: Job, status: WorkflowStatus) -> StepResult:
        """Step 1: Validate the source image."""
        step = "validate"
        status.start(step)
        self._notify(status)

        self.job_repo.transition(job.job_id, JobStatus.PROCESSING, note="Validating image")

        validation = validate_image(Path(job.original_file))
        if not validation.is_valid:
            status.fail_step(step, validation.error_message)
            return StepResult(
                step_name=step,
                status=StepStatus.FAILED,
                success=False,
                error_message=validation.error_message,
                is_retryable=False,
            )

        logger.info(f"[validate] OK — {validation.summary}")
        status.complete_step(step)
        return StepResult(step_name=step, status=StepStatus.SUCCESS, success=True)

    def _step_preserve(self, job: Job, status: WorkflowStatus) -> StepResult:
        """Step 2: Copy original to output directory."""
        step = "preserve_original"
        status.start(step)
        self._notify(status)

        try:
            output_dir = ensure_output_dir(Path(self.settings.output_dir))
            preserve_original(Path(job.original_file), output_dir)
            logger.info(f"[preserve] Original copied to {output_dir}")
            status.complete_step(step)
            return StepResult(step_name=step, status=StepStatus.SUCCESS, success=True)
        except Exception as e:
            msg = f"Failed to preserve original: {e}"
            status.fail_step(step, msg)
            return StepResult(
                step_name=step, status=StepStatus.FAILED,
                success=False, error_message=msg, is_retryable=True,
            )

    def _step_photoroom(self, job: Job, status: WorkflowStatus) -> StepResult:
        """Step 3: Remove background via PhotoRoom client."""
        step = "photoroom"
        status.start(step)
        self._notify(status)

        self.job_repo.transition(job.job_id, JobStatus.PHOTOROOM_PROCESSING,
                                 note="Sending to PhotoRoom")
        self.job_repo.set_photoroom_status(job.job_id, "processing")

        output_dir = ensure_output_dir(Path(self.settings.output_dir))
        output_path = build_processed_path(Path(job.original_file), output_dir)

        result = self.photoroom_client.remove_background(
            Path(job.original_file),
            output_path,
            sandbox=self.settings.photoroom_sandbox_mode,
        )

        if result.success:
            self.job_repo.set_photoroom_status(job.job_id, "complete")
            self.job_repo.transition(
                job.job_id, JobStatus.PHOTOROOM_COMPLETE,
                processed_file=str(result.output_path),
                note=f"PhotoRoom OK — {result.processing_time_ms}ms",
            )
            status.processed_file = str(result.output_path)
            status.complete_step(step)
            logger.info(f"[photoroom] {result.summary}")
            return StepResult(
                step_name=step, status=StepStatus.SUCCESS, success=True,
                output_path=result.output_path,
            )
        else:
            self.job_repo.set_photoroom_status(job.job_id, "failed")
            msg = f"PhotoRoom failed: {result.error_message}"
            status.fail_step(step, msg)
            return StepResult(
                step_name=step, status=StepStatus.FAILED, success=False,
                error_message=msg,
                is_retryable=result.is_retryable,
            )

    def _step_generate_listing(
        self, job: Job, status: WorkflowStatus, processed_path: Path | None,
        command: ProcessImageCommand | None = None
    ) -> StepResult:
        """
        Step 4: Generate product listing data using the injected ListingGenerator.
        """
        step = "generate_listing"
        status.start(step)
        self._notify(status)

        self.job_repo.transition(job.job_id, JobStatus.LISTING_GENERATED,
                                 note="Generating listing")
        self.job_repo.set_listing_status(job.job_id, "processing")

        if not self.listing_generator:
            # Fallback stub if generator not injected
            logger.warning("[listing] No ListingGenerator injected, using stub.")
            product = Product(
                title=f"Product from {Path(job.original_file).stem}",
                description="[Fallback generated description]",
            )
            self.product_repo.create(product)
            self._link_product_to_job(job.job_id, product.product_id)
            self.job_repo.set_listing_status(job.job_id, "complete")
            status.complete_step(step)
            return StepResult(step_name=step, status=StepStatus.SUCCESS, success=True, product_id=product.product_id)

        try:
            # We pass the original file if processed is missing (e.g. photoroom skipped)
            path_to_analyze = processed_path or Path(job.original_file)
            gen_result = self.listing_generator.generate(path_to_analyze, command)

            if gen_result.success and gen_result.listing:
                ls = gen_result.listing
                product = Product(
                    title=ls.title,
                    description=ls.description,
                    price=ls.price,
                    category=ls.category,
                    brand=ls.brand,
                    condition=ls.condition,
                    color=ls.color,
                    size=ls.size,
                    tags=ls.tags
                )
                self.product_repo.create(product)
                self._link_product_to_job(job.job_id, product.product_id)
                self.job_repo.set_listing_status(job.job_id, "complete")
                logger.info(f"[listing] Product generated: {product.product_id[:8]}")
                status.complete_step(step)
                return StepResult(step_name=step, status=StepStatus.SUCCESS, success=True, product_id=product.product_id)
            else:
                msg = f"Listing generator failed: {gen_result.error_message}"
                self.job_repo.set_listing_status(job.job_id, "failed")
                status.fail_step(step, msg)
                return StepResult(step_name=step, status=StepStatus.FAILED, success=False, error_message=msg, is_retryable=gen_result.is_retryable)
                
        except Exception as e:
            msg = f"Listing generation exception: {e}"
            self.job_repo.set_listing_status(job.job_id, "failed")
            status.fail_step(step, msg)
            return StepResult(step_name=step, status=StepStatus.FAILED, success=False, error_message=msg, is_retryable=False)

    def _link_product_to_job(self, job_id: str, product_id: str) -> None:
        """Helper to link a product to a job."""
        with self.db.connection() as conn:
            conn.execute(
                "UPDATE jobs SET product_id = ?, updated_at = ? WHERE job_id = ?",
                (product_id, _now(), job_id),
            )

    def _step_vendoo(
        self, job: Job, status: WorkflowStatus,
        product_id: str | None, processed_path: Path | None
    ) -> StepResult:
        """
        Step 5: Hand off to Vendoo connector.

        This is a STUB if vendoo_connector is None.
        Full MockVendooConnector will be built in Task 8.
        """
        step = "vendoo"
        status.start(step)
        self._notify(status)

        self.job_repo.transition(job.job_id, JobStatus.VENDOO_PENDING,
                                 note="Sending to Vendoo")
        self.job_repo.set_vendoo_status(job.job_id, "pending")

        if self.vendoo_connector is None:
            # Stub behavior: simulate success
            logger.info("[vendoo] No connector injected — simulating success (stub)")
            self.job_repo.set_vendoo_status(job.job_id, "stub_complete")
            self.job_repo.transition(job.job_id, JobStatus.VENDOO_COMPLETE,
                                     note="Vendoo stub complete")
            status.complete_step(step)
            return StepResult(step_name=step, status=StepStatus.SUCCESS, success=True)

        if not product_id:
            msg = "No product ID available for Vendoo step."
            self.job_repo.set_vendoo_status(job.job_id, "failed")
            status.fail_step(step, msg)
            return StepResult(step_name=step, status=StepStatus.FAILED, success=False, error_message=msg)

        # Map Product DB model to ProductListing schema for the connector
        db_product = self.product_repo.get(product_id)
        if not db_product:
            msg = f"Product {product_id} not found."
            self.job_repo.set_vendoo_status(job.job_id, "failed")
            status.fail_step(step, msg)
            return StepResult(step_name=step, status=StepStatus.FAILED, success=False, error_message=msg)

        try:
            listing = ProductListing(
                title=db_product.title,
                description=db_product.description,
                price=db_product.price,
                category=db_product.category,
                brand=db_product.brand,
                condition=db_product.condition,
                color=db_product.color,
                size=db_product.size,
                tags=db_product.tags,
            )
        except Exception as e:
            msg = f"Failed to build ProductListing from DB product: {e}"
            self.job_repo.set_vendoo_status(job.job_id, "failed")
            status.fail_step(step, msg)
            return StepResult(step_name=step, status=StepStatus.FAILED, success=False, error_message=msg)

        # We pass the original file if processed is missing
        path_to_analyze = processed_path or Path(job.original_file)

        # Real connector path
        try:
            connector_result = self.vendoo_connector.submit_listing(listing, path_to_analyze)
            if connector_result.success:
                self.job_repo.set_vendoo_status(job.job_id, "complete")
                note = f"Vendoo success ({connector_result.vendoo_item_id})"
                self.job_repo.transition(job.job_id, JobStatus.VENDOO_COMPLETE, note=note)
                status.complete_step(step)
                return StepResult(step_name=step, status=StepStatus.SUCCESS, success=True)
            else:
                msg = f"Vendoo connector failed: {connector_result.error_message}"
                self.job_repo.set_vendoo_status(job.job_id, "failed")
                status.fail_step(step, msg)
                return StepResult(
                    step_name=step, status=StepStatus.FAILED, success=False,
                    error_message=msg, is_retryable=connector_result.is_retryable,
                )
        except Exception as e:
            msg = f"Vendoo connector exception: {e}"
            status.fail_step(step, msg)
            return StepResult(
                step_name=step, status=StepStatus.FAILED, success=False,
                error_message=msg, is_retryable=True,
            )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _fail(self, job: Job, status: WorkflowStatus, result: StepResult) -> WorkflowStatus:
        """Handle a step failure: update DB, update status, return."""
        self._safe_fail_job(job.job_id, result.error_message)
        status.fail(result.error_message)
        self._notify(status)
        logger.error(
            f"Workflow FAILED at step '{result.step_name}' for job {job.job_id[:8]}: "
            f"{result.error_message}"
        )
        return status

    def _safe_fail_job(self, job_id: str, error_message: str) -> None:
        """Fail a job safely — handles cases where the job is already in a non-transitionable state."""
        try:
            job = self.job_repo.get(job_id)
            if job and not job.is_terminal:
                # Find current status's allowed transitions to see if FAILED is possible
                from app.database.job_repo import VALID_TRANSITIONS
                allowed = VALID_TRANSITIONS.get(job.status, set())
                if JobStatus.FAILED in allowed:
                    self.job_repo.transition(
                        job_id, JobStatus.FAILED,
                        error_message=error_message,
                        note="Step failed",
                    )
        except Exception as e:
            logger.error(f"Could not update job {job_id[:8]} to FAILED: {e}")

    def _notify(self, status: WorkflowStatus) -> None:
        """Call the progress callback if one is registered."""
        if self._on_progress:
            try:
                self._on_progress(status)
            except Exception as e:
                logger.warning(f"Progress callback error (ignored): {e}")


def _now() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat()
