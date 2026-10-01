"""
Crash recovery and state reconciliation logic.

Handles jobs that were left in an active processing state due to unexpected shutdown.
"""

from app.database.job_repo import JobRepository
from app.config.constants import JobStatus
from app.logging import get_logger

logger = get_logger("workflow.recovery")

def reconcile_stuck_jobs(job_repo: JobRepository) -> int:
    """
    Find jobs that are stuck in a non-terminal, non-queued state 
    (e.g., app crashed mid-processing) and reset them to FAILED so they can be retried.
    
    Returns:
        Number of jobs reconciled.
    """
    stuck_statuses = [
        JobStatus.PROCESSING,
        JobStatus.PHOTOROOM_PROCESSING,
        JobStatus.PHOTOROOM_COMPLETE,
        JobStatus.LISTING_GENERATED,
        JobStatus.VENDOO_PENDING,
        JobStatus.RETRYING,
        JobStatus.CROSSLISTING
    ]
    
    reconciled_count = 0
    
    for status in stuck_statuses:
        stuck_jobs = job_repo.get_by_status(status)
        for job in stuck_jobs:
            logger.warning(
                f"Reconciling stuck job {job.job_id[:8]} (was '{status}'). "
                f"Marking as FAILED."
            )
            # We can't always guarantee a valid transition to FAILED from everywhere 
            # based on VALID_TRANSITIONS, so we might need a force transition or 
            # ensure FAILED is allowed from all active states.
            # In job_repo.py, we have defined transitions.
            try:
                job_repo.transition(
                    job.job_id, 
                    JobStatus.FAILED, 
                    error_message="Aborted due to unexpected shutdown/crash",
                    note="System reconciliation"
                )
                reconciled_count += 1
            except Exception as e:
                logger.error(f"Failed to reconcile stuck job {job.job_id[:8]}: {e}")
                
    if reconciled_count > 0:
        logger.info(f"Reconciled {reconciled_count} stuck jobs.")
        
    return reconciled_count
