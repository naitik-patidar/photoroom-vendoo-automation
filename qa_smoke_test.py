"""
Final QA Smoke Test Script.

Runs the full end-to-end pipeline in PRODUCTION mode to verify:
1. Orchestrator connects to RealPhotoRoomClient.
2. PhotoRoom API auth fails safely if no valid key is present.
3. Database correctly logs the job history and failure reason.
4. Generates a valid test image.
"""

import os
from PIL import Image
from pathlib import Path

# Force Production Mode for the smoke test
os.environ["APP_MODE"] = "production"
os.environ["PHOTOROOM_API_KEY"] = "TEST_INVALID_KEY_FOR_QA" # ensures a secure 401 fail

from app.database.db import Database
from app.database.job_repo import JobRepository
from app.database.product_repo import ProductRepository
from app.config.settings import get_settings
from app.workflow.orchestrator import WorkflowOrchestrator
from app.ai.mock_interpreter import MockCommandInterpreter
from app.photoroom import create_photoroom_client
from app.listings.generator import MockListingGenerator
from app.vendoo import create_vendoo_connector

def run_qa():
    settings = get_settings()
    
    # 1. Init DB
    db = Database(settings.database_path)
    db.initialize()
    job_repo = JobRepository(db)
    
    # 2. Setup Real Clients
    pr_client = create_photoroom_client(mode="production")
    listing_gen = MockListingGenerator()
    vendoo_conn = create_vendoo_connector(mode="production")
    
    orchestrator = WorkflowOrchestrator(
        db=db,
        photoroom_client=pr_client,
        listing_generator=listing_gen,
        vendoo_connector=vendoo_conn,
        settings=settings
    )
    
    interpreter = MockCommandInterpreter()
    
    # 3. Create dummy image
    test_img = Path("qa_test_image.jpg")
    Image.new('RGB', (100, 100), color='green').save(test_img)
    
    print("\n--- STARTING E2E SMOKE TEST ---")
    
    # 4. Execute AI Command
    cmd = interpreter.interpret(f'process "{test_img}" brand Nike').command
    job = job_repo.create(cmd.image_path)
    
    # 5. Run Workflow
    status = orchestrator.run(job.job_id, cmd)
    
    # 6. Verify Output
    print(f"\nFinal State: {status.state.value}")
    print(f"Error Message: {status.error_message}")
    
    db_job = job_repo.get(job.job_id)
    print(f"\nDB Status: {db_job.status}")
    print(f"PhotoRoom Status: {db_job.photoroom_status}")
    
    print("\nJob History:")
    for h in job_repo.get_history(job.job_id):
        print(f" - {h.old_status} -> {h.new_status} | Note: {h.note}")
        
    orchestrator.shutdown()
    
if __name__ == "__main__":
    run_qa()
