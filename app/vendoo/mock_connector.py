"""
Mock Vendoo Connector implementation.
"""

import time
import uuid
from pathlib import Path

from app.listings.schemas import ProductListing
from app.vendoo.connector import VendooConnector, VendooResult
from app.logging import get_logger

logger = get_logger("vendoo.mock_connector")


class MockVendooConnector(VendooConnector):
    """
    Simulates a successful Vendoo upload.
    Validates that the payload and image exist.
    """

    def __init__(self, simulate_delay_ms: int = 500, simulate_error: bool = False):
        self.simulate_delay_ms = simulate_delay_ms
        self.simulate_error = simulate_error
        logger.info(f"MockVendooConnector initialized (delay={simulate_delay_ms}ms)")

    def submit_listing(
        self,
        listing: ProductListing,
        image_path: Path,
    ) -> VendooResult:
        """Simulate submitting a listing to Vendoo."""
        
        start_time = time.time()
        
        if self.simulate_delay_ms > 0:
            time.sleep(self.simulate_delay_ms / 1000.0)
            
        elapsed_ms = int((time.time() - start_time) * 1000)

        # Basic validations
        if not image_path.exists():
            return VendooResult(
                success=False,
                error_message=f"Image file not found: {image_path}",
                is_retryable=False,
                processing_time_ms=elapsed_ms
            )
            
        if self.simulate_error:
            return VendooResult(
                success=False,
                error_message="Simulated Vendoo network timeout",
                is_retryable=True,
                processing_time_ms=elapsed_ms
            )
            
        # Simulate success
        fake_item_id = f"vdo_{uuid.uuid4().hex[:8]}"
        
        logger.info(f"Successfully simulated upload to Vendoo: {fake_item_id}")
        
        return VendooResult(
            success=True,
            vendoo_item_id=fake_item_id,
            item_url=f"https://mock.vendoo.co/item/{fake_item_id}",
            processing_time_ms=elapsed_ms
        )

    def get_connector_info(self) -> dict:
        return {
            "type": "mock",
            "version": "1.0.0",
            "is_mock": True
        }
