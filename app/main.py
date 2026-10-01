"""
PhotoRoom + Vendoo Automation — Application Entry Point

This is the main entry point for the application.
Initializes logging, configuration, and launches the appropriate mode.
"""

import sys
from pathlib import Path

from app.config.settings import get_settings
from app.config.constants import APP_NAME, APP_VERSION
from app.logging import setup_logging, get_logger

from PySide6.QtWidgets import QApplication
from app.database.db import Database
from app.database.job_repo import JobRepository
from app.database.product_repo import ProductRepository
from app.photoroom import create_photoroom_client
from app.listings.generator import MockListingGenerator
from app.vendoo import create_vendoo_connector
from app.ai import create_interpreter
from app.workflow.orchestrator import WorkflowOrchestrator
from app.workflow.recovery import reconcile_stuck_jobs
from app.ui.main_window import MainWindow


def ensure_directories(settings) -> None:
    """Create required application directories if they don't exist."""
    dirs = [
        Path(settings.output_dir),
        Path(settings.database_path).parent,
        Path(settings.log_dir),
    ]
    for d in dirs:
        d.mkdir(parents=True, exist_ok=True)


def main() -> int:
    """
    Application main entry point.

    Returns:
        Exit code (0 = success, 1 = error).
    """
    # Load settings
    settings = get_settings()

    # Setup logging
    logger = setup_logging(
        log_level=settings.log_level,
        log_dir=settings.log_dir,
    )

    logger.info("=" * 60)
    logger.info(f"{APP_NAME} v{APP_VERSION}")
    logger.info("=" * 60)
    logger.info(f"Mode: {settings.app_mode.upper()}")
    logger.info(f"Settings: {settings}")

    # Validate settings
    warnings = settings.validate()
    for w in warnings:
        logger.warning(f"Config warning: {w}")

    # Ensure directories exist
    try:
        ensure_directories(settings)
        logger.info("Application directories verified.")
    except OSError as e:
        logger.error(f"Failed to create application directories: {e}")
        return 1

    # Initialize Core Components
    try:
        db = Database(settings.database_path)
        db.initialize()
        
        job_repo = JobRepository(db)
        
        pr_client = create_photoroom_client(settings)
        listing_gen = MockListingGenerator()
        vendoo_conn = create_vendoo_connector(settings.app_mode)
        
        orchestrator = WorkflowOrchestrator(
            db=db,
            photoroom_client=pr_client,
            listing_generator=listing_gen,
            vendoo_connector=vendoo_conn,
            settings=settings
        )
        
        interpreter = create_interpreter(settings.app_mode)
        
        # Crash Recovery: Reconcile any jobs stuck from a previous crash
        reconcile_stuck_jobs(job_repo)
        
    except Exception as e:
        logger.error(f"Failed to initialize core components: {e}")
        return 1

    logger.info("Core components initialized successfully. Launching UI...")
    
    # Launch UI
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
        
    window = MainWindow(
        settings=settings,
        db=db,
        job_repo=job_repo,
        orchestrator=orchestrator,
        interpreter=interpreter
    )
    window.show()
    
    
    try:
        exit_code = app.exec()
    finally:
        logger.info("Initiating graceful shutdown...")
        orchestrator.shutdown()
        logger.info("Shutting down complete.")
        
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
