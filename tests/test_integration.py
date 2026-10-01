"""
End-to-End Integration Tests for Mock Workflow.

Proves that:
AI Command Engine → Orchestrator → ImageEngine → PhotoRoom → ListingGen → Vendoo → DB
works flawlessly end-to-end.
"""

import pytest
from pathlib import Path
from PIL import Image

from app.database.db import Database
from app.database.job_repo import JobRepository
from app.database.product_repo import ProductRepository
from app.config.settings import Settings
from app.config.constants import JobStatus
from app.photoroom.mock_client import MockPhotoRoomClient
from app.listings.generator import MockListingGenerator
from app.vendoo.mock_connector import MockVendooConnector
from app.ai.mock_interpreter import MockCommandInterpreter
from app.ai.schemas import CommandType, ProcessImageCommand
from app.workflow.orchestrator import WorkflowOrchestrator
from app.photoroom.client import ProcessingStatus


@pytest.fixture
def settings(tmp_path):
    return Settings(
        database_path=str(tmp_path / "integration.db"),
        output_dir=str(tmp_path / "output")
    )


@pytest.fixture
def db(settings):
    database = Database(settings.database_path)
    database.initialize()
    return database


@pytest.fixture
def repos(db):
    return JobRepository(db), ProductRepository(db)


@pytest.fixture
def interpreter():
    return MockCommandInterpreter()


@pytest.fixture
def dummy_image(tmp_path) -> Path:
    img_path = tmp_path / "test_sneaker.jpg"
    img = Image.new('RGB', (100, 100), color='red')
    img.save(img_path)
    return img_path


def create_orchestrator(
    db: Database, settings: Settings, 
    pr_error=None, vendoo_error=False
) -> WorkflowOrchestrator:
    """Helper to wire up the orchestrator with configurable mocks."""
    pr_client = MockPhotoRoomClient(simulate_delay_ms=0, simulate_error=pr_error)
    listing_gen = MockListingGenerator()
    vendoo_conn = MockVendooConnector(simulate_delay_ms=0, simulate_error=vendoo_error)
    
    return WorkflowOrchestrator(
        db=db,
        photoroom_client=pr_client,
        listing_generator=listing_gen,
        vendoo_connector=vendoo_conn,
        settings=settings
    )


# =====================================================================
# Happy Path Tests
# =====================================================================

def test_single_image_e2e(db, settings, repos, interpreter, dummy_image):
    job_repo, prod_repo = repos
    orchestrator = create_orchestrator(db, settings)
    
    # 1. User provides natural language
    nl_input = f'process "{dummy_image}" brand Nike color Red price $49.99 category Shoes'
    
    # 2. AI interprets
    intent = interpreter.interpret(nl_input)
    assert intent.command_type == CommandType.PROCESS_IMAGE
    cmd: ProcessImageCommand = intent.command
    
    # 3. Create Job
    job = job_repo.create(cmd.image_path)
    assert job.status == JobStatus.QUEUED
    
    # 4. Orchestrator Runs
    status = orchestrator.run(job.job_id, cmd)
    
    # 5. Verify In-Memory Status
    assert status.state.value == "completed"
    assert not status.error_message
    
    # 6. Verify Database State
    db_job = job_repo.get(job.job_id)
    assert db_job.status == JobStatus.COMPLETED
    assert db_job.photoroom_status == "complete"
    assert db_job.listing_status == "complete"
    assert db_job.vendoo_status == "complete"
    
    # 7. Verify Product Creation & Data Mapping
    assert db_job.product_id is not None
    product = prod_repo.get(db_job.product_id)
    assert product is not None
    assert product.title == "Nike Red Test Sneaker"  # Dynamic generation
    assert product.price == 49.99
    assert product.brand == "Nike"
    assert product.color == "Red"
    
    # 8. Verify Job History
    history = job_repo.get_history(job.job_id)
    transitions = [h.new_status for h in history]
    assert JobStatus.PHOTOROOM_COMPLETE in transitions
    assert JobStatus.LISTING_GENERATED in transitions
    assert JobStatus.VENDOO_COMPLETE in transitions
    assert JobStatus.COMPLETED in transitions
    orchestrator.shutdown()


def test_batch_processing_e2e(db, settings, repos, interpreter, tmp_path):
    job_repo, prod_repo = repos
    orchestrator = create_orchestrator(db, settings)
    
    # Create 3 images
    images = []
    for i in range(3):
        p = tmp_path / f"batch_img_{i}.jpg"
        Image.new('RGB', (100, 100), color='blue').save(p)
        images.append(p)
        
    # Queue them
    jobs = [job_repo.create(str(p)) for p in images]
    job_ids = [j.job_id for j in jobs]
    
    # Run batch with a command
    nl_input = f'batch "{tmp_path}" brand Zara condition Used'
    intent = interpreter.interpret(nl_input)
    # The batch command itself in Task 6 maps to BatchProcessCommand, but for Orchestrator
    # we can map it to a generic ProcessImageCommand that applies to all in the batch,
    # or just run them with None.
    # We will pass a ProcessImageCommand constructed from the batch command's shared attributes.
    shared_cmd = ProcessImageCommand(
        image_path="dummy", 
        brand=intent.command.brand, 
        condition=intent.command.condition
    )
    
    results = orchestrator.run_batch(job_ids, shared_cmd)
    
    assert len(results) == 3
    for r in results:
        assert r.state.value == "completed"
        
    # Verify DB
    db_jobs = [job_repo.get(jid) for jid in job_ids]
    for db_job in db_jobs:
        assert db_job.status == JobStatus.COMPLETED
        product = prod_repo.get(db_job.product_id)
        assert product.brand == "Zara"
        assert product.condition == "USED"
    orchestrator.shutdown()


# =====================================================================
# Failure & Recovery Tests
# =====================================================================

def test_missing_image_fails_safely(db, settings, repos, dummy_image):
    job_repo, _ = repos
    orchestrator = create_orchestrator(db, settings)
    
    job = job_repo.create("/path/does/not/exist.jpg")
    status = orchestrator.run(job.job_id)
    
    assert status.state.value == "failed"
    assert "not found" in status.error_message.lower()
    
    db_job = job_repo.get(job.job_id)
    assert db_job.status == JobStatus.FAILED
    orchestrator.shutdown()


def test_photoroom_failure_preserves_error(db, settings, repos, dummy_image):
    job_repo, _ = repos
    # Inject PhotoRoom error
    orchestrator = create_orchestrator(db, settings, pr_error=ProcessingStatus.TIMEOUT)
    
    job = job_repo.create(str(dummy_image))
    status = orchestrator.run(job.job_id)
    
    assert status.state.value == "failed"
    assert "photoroom" in status.error_message.lower()
    
    db_job = job_repo.get(job.job_id)
    assert db_job.status == JobStatus.FAILED
    assert db_job.photoroom_status == "failed"
    assert db_job.listing_status is None  # Should not have reached listing
    assert "photoroom" in db_job.error_message.lower()
    
    history = job_repo.get_history(job.job_id)
    assert any(h.new_status == JobStatus.FAILED for h in history)
    orchestrator.shutdown()


def test_vendoo_failure_preserves_error(db, settings, repos, dummy_image):
    job_repo, _ = repos
    # Inject Vendoo error
    orchestrator = create_orchestrator(db, settings, vendoo_error=True)
    
    job = job_repo.create(str(dummy_image))
    status = orchestrator.run(job.job_id)
    
    assert status.state.value == "failed"
    
    db_job = job_repo.get(job.job_id)
    assert db_job.status == JobStatus.FAILED
    assert db_job.photoroom_status == "complete"
    assert db_job.listing_status == "complete"
    assert db_job.vendoo_status == "failed"
    assert "timeout" in db_job.error_message.lower()
    
    history = job_repo.get_history(job.job_id)
    orchestrator.shutdown()


def test_partial_batch_failure_isolation(db, settings, repos, tmp_path):
    job_repo, _ = repos
    # Real image
    img1 = tmp_path / "good.jpg"
    Image.new('RGB', (100, 100), color='red').save(img1)
    
    # Missing image
    img2 = tmp_path / "bad.jpg"
    
    job1 = job_repo.create(str(img1))
    job2 = job_repo.create(str(img2))
    
    orchestrator = create_orchestrator(db, settings)
    
    results = orchestrator.run_batch([job1.job_id, job2.job_id])
    
    assert results[0].state.value == "completed"
    assert results[1].state.value == "failed"
    
    db_job1 = job_repo.get(job1.job_id)
    db_job2 = job_repo.get(job2.job_id)
    
    assert db_job1.status == JobStatus.COMPLETED
    assert db_job2.status == JobStatus.FAILED
    assert db_job1.product_id is not None
    assert db_job2.product_id is None
    orchestrator.shutdown()
