"""
Listing Data Schemas — Pydantic models for product listings.

Represents the fully prepared data ready to be pushed to Vendoo.
Includes cross-platform specific fields (eBay, Vinted, Depop).
"""

from pydantic import BaseModel, Field
from typing import Optional


class EbayData(BaseModel):
    """eBay-specific listing fields."""
    category_id: Optional[str] = None
    item_specifics: dict[str, str] = Field(default_factory=dict)
    shipping_profile: Optional[str] = None


class VintedData(BaseModel):
    """Vinted-specific listing fields."""
    catalog_id: Optional[str] = None
    package_size: Optional[str] = Field(None, description="Small, Medium, Large")


class DepopData(BaseModel):
    """Depop-specific listing fields."""
    category_slug: Optional[str] = None
    age_group: Optional[str] = None


class ProductListing(BaseModel):
    """
    Complete product listing data.
    
    This is what the ListingGenerator produces and what the
    VendooConnector consumes.
    """
    # Core Data
    title: str = Field(..., min_length=1, max_length=120)
    description: str = Field(...)
    price: float = Field(..., ge=0)
    
    # Categorization
    category: Optional[str] = None
    subcategory: Optional[str] = None
    brand: Optional[str] = None
    
    # Attributes
    condition: Optional[str] = None
    color: Optional[str] = None
    size: Optional[str] = None
    material: Optional[str] = None
    
    # SEO / Discovery
    tags: list[str] = Field(default_factory=list, max_length=30)
    
    # Platform-specific overrides/data
    ebay: EbayData = Field(default_factory=EbayData)
    vinted: VintedData = Field(default_factory=VintedData)
    depop: DepopData = Field(default_factory=DepopData)
