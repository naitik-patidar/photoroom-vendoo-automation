"""
Tests for crash recovery and state reconciliation.
"""

import pytest
from app.database.db import Database
from app.database.job_repo import JobRepository
from app.config.constants import JobStatus
from app.workflow.recovery import reconcile_stuck_jobs


@pytest.fixture
def db(tmp_path):
    db_path = tmp_path / "test.db"
    db_inst = Database(db_path)
    db_inst.initialize()
    return db_inst


@pytest.fixture
def repo(db):
    return JobRepository(db)


def test_reconcile_stuck_jobs_no_stuck_jobs(repo):
    job1 = repo.create("test1.jpg")
    job2 = repo.create("test2.jpg")
    
    # Valid transition to COMPLETED
    repo.transition(job1.job_id, JobStatus.PROCESSING)
    repo.transition(job1.job_id, JobStatus.PHOTOROOM_PROCESSING)
    repo.transition(job1.job_id, JobStatus.PHOTOROOM_COMPLETE)
    repo.transition(job1.job_id, JobStatus.LISTING_GENERATED)
    repo.transition(job1.job_id, JobStatus.VENDOO_PENDING)
    repo.transition(job1.job_id, JobStatus.VENDOO_COMPLETE)
    repo.transition(job1.job_id, JobStatus.COMPLETED)
    
    # job2 is just QUEUED
    
    count = reconcile_stuck_jobs(repo)
    assert count == 0
    
    assert repo.get(job1.job_id).status == JobStatus.COMPLETED
    assert repo.get(job2.job_id).status == JobStatus.QUEUED


def test_reconcile_stuck_jobs_updates_to_failed(repo):
    job1 = repo.create("test1.jpg")
    job2 = repo.create("test2.jpg")
    job3 = repo.create("test3.jpg")
    
    # Valid transitions to stuck states
    repo.transition(job1.job_id, JobStatus.PROCESSING)
    
    repo.transition(job2.job_id, JobStatus.PROCESSING)
    repo.transition(job2.job_id, JobStatus.PHOTOROOM_PROCESSING)
    
    repo.transition(job3.job_id, JobStatus.PROCESSING)
    repo.transition(job3.job_id, JobStatus.PHOTOROOM_PROCESSING)
    repo.transition(job3.job_id, JobStatus.PHOTOROOM_COMPLETE)
    repo.transition(job3.job_id, JobStatus.LISTING_GENERATED)
    
    count = reconcile_stuck_jobs(repo)
    assert count == 3
    
    assert repo.get(job1.job_id).status == JobStatus.FAILED
    assert repo.get(job2.job_id).status == JobStatus.FAILED
    assert repo.get(job3.job_id).status == JobStatus.FAILED


def test_reconcile_stuck_jobs_adds_history_note(repo):
    job = repo.create("test.jpg")
    repo.transition(job.job_id, JobStatus.PROCESSING)
    
    reconcile_stuck_jobs(repo)
    
    history = repo.get_history(job.job_id)
    assert len(history) == 3 # QUEUED, PROCESSING, FAILED
    
    failed_event = history[-1]
    assert failed_event.new_status == JobStatus.FAILED
    assert failed_event.note == "System reconciliation"
