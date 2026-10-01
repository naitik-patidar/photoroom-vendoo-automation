"""
Vendoo Connector Interface.

Responsible for taking a finalized ProductListing and pushing it to Vendoo.
Since Vendoo lacks a public REST API, the real implementation will likely
use browser automation (Playwright/Selenium) or official partnerships.

This interface abstracts that complexity away from the Workflow Engine.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path

from app.listings.schemas import ProductListing
from app.logging import get_logger

logger = get_logger("vendoo.connector")


@dataclass
class VendooResult:
    """Outcome of submitting a listing to Vendoo."""
    success: bool
    vendoo_item_id: str | None = None
    item_url: str | None = None
    error_message: str = ""
    is_retryable: bool = False
    processing_time_ms: int = 0


class VendooConnector(ABC):
    """Abstract interface for Vendoo integration."""

    @abstractmethod
    def submit_listing(
        self,
        listing: ProductListing,
        image_path: Path,
    ) -> VendooResult:
        """
        Submit a listing and its image to Vendoo.
        
        Args:
            listing: The fully prepared listing data.
            image_path: Path to the processed image to upload.
            
        Returns:
            VendooResult with success status and Vendoo IDs.
        """
        ...

    @abstractmethod
    def get_connector_info(self) -> dict:
        """Return metadata about this connector implementation."""
        ...
