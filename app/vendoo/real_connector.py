"""
Real Vendoo Connector — Generic CSV Handoff.

Because Vendoo does not provide a public developer API, and we are
strictly avoiding reverse-engineering, scraping, or bypassing access controls,
this connector implements a generic CSV handoff.

Note: Vendoo's standard workflow imports directly from other marketplaces. 
Bulk CSV imports usually require Vendoo's enterprise "white glove" support 
or manual column mapping. This CSV provides a safe, generic data dump 
that users can use as a reference for manual listing or support tickets, 
without us violating TOS or guessing private API structures.
"""

import csv
import time
from pathlib import Path
from datetime import datetime, timezone

from app.vendoo.connector import VendooConnector, VendooResult
from app.listings.schemas import ProductListing
from app.logging import get_logger

logger = get_logger("vendoo.real")


class RealVendooConnector(VendooConnector):
    """
    Exports prepared listings into a generic CSV format, avoiding 
    unauthorized scraping or private API usage.
    """

    def __init__(self, output_dir: str):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.csv_path = self.output_dir / "vendoo_import_handoff.csv"
        
        # Create CSV with headers if it doesn't exist
        if not self.csv_path.exists():
            self._write_headers()
            
        logger.info(f"RealVendooConnector initialized. Handoff CSV: {self.csv_path}")

    def _write_headers(self):
        """Initialize the CSV file with generic descriptive headers."""
        headers = [
            "Title", "Description", "Price", "Brand", "Color", 
            "Condition", "Category", "Image Path", "Date Generated"
        ]
        # utf-8-sig adds the BOM, which helps Excel and other tools safely parse special characters
        with open(self.csv_path, mode="w", newline="", encoding="utf-8-sig") as f:
            writer = csv.writer(f)
            writer.writerow(headers)

    def submit_listing(
        self,
        listing: ProductListing,
        image_path: Path,
    ) -> VendooResult:
        """
        Validates and appends the listing to the handoff CSV.
        """
        start_time = time.time()
        
        if not image_path.exists():
            return VendooResult(
                success=False,
                error_message=f"Image file not found: {image_path}",
                is_retryable=False
            )

        # Basic validation (Pydantic already validated most during creation,
        # but we ensure it's safe for CSV).
        if not listing.title:
            return VendooResult(
                success=False,
                error_message="Listing is missing a title.",
                is_retryable=False
            )
            
        row = [
            listing.title,
            listing.description,
            str(listing.price),
            listing.brand or "",
            listing.color or "",
            listing.condition or "",
            listing.category or "",
            str(image_path.absolute()),
            datetime.now(timezone.utc).isoformat()
        ]

        try:
            with open(self.csv_path, mode="a", newline="", encoding="utf-8-sig") as f:
                writer = csv.writer(f)
                writer.writerow(row)
                
            elapsed = int((time.time() - start_time) * 1000)
            
            # Since this is a manual handoff, there is no remote Vendoo item ID yet.
            # We use a prefixed local ID to indicate it's in the CSV.
            handoff_id = f"csv_handoff_{int(time.time())}"
            
            logger.info(f"Successfully appended '{listing.title}' to Vendoo handoff CSV.")
            
            return VendooResult(
                success=True,
                vendoo_item_id=handoff_id,
                item_url=f"file://{self.csv_path.absolute()}",
                processing_time_ms=elapsed
            )
            
        except Exception as e:
            logger.error(f"Failed to write to Vendoo handoff CSV: {e}")
            return VendooResult(
                success=False,
                error_message=f"File system error writing CSV: {e}",
                is_retryable=True
            )

    def get_connector_info(self) -> dict:
        return {
            "type": "real_csv_handoff",
            "version": "1.0.0",
            "is_mock": False,
            "export_path": str(self.csv_path),
            "note": "Generic CSV handoff. Manual import/mapping required."
        }
