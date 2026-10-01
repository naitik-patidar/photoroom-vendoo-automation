"""
Listing Generation Package.
"""

from app.listings.schemas import ProductListing, EbayData, VintedData, DepopData
from app.listings.generator import ListingGenerator, MockListingGenerator, GenerationResult
from app.config.settings import get_settings


def create_listing_generator(mode: str | None = None) -> ListingGenerator:
    """
    Factory function to create the appropriate ListingGenerator.
    
    Args:
        mode: "mock" or "production". Defaults to settings.APP_MODE.
    """
    if mode is None:
        mode = get_settings().app_mode

    if mode == "production":
        import logging
        logger = logging.getLogger("app.listings.factory")
        logger.warning("Real AI listing generator not yet implemented. Falling back to MockListingGenerator.")
        return MockListingGenerator()

    return MockListingGenerator()


__all__ = [
    "ProductListing",
    "EbayData",
    "VintedData",
    "DepopData",
    "ListingGenerator",
    "MockListingGenerator",
    "GenerationResult",
    "create_listing_generator",
]
