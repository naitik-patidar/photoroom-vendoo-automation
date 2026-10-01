"""
Tests for app.listings — Listing Data Models and Generator.
"""

import pytest
from pydantic import ValidationError
from pathlib import Path

from app.listings.schemas import ProductListing, EbayData, VintedData, DepopData
from app.listings.generator import MockListingGenerator, GenerationResult
from app.listings import create_listing_generator
from app.ai.schemas import ProcessImageCommand


# ======================================================================
# Schema Tests
# ======================================================================

class TestListingSchemas:

    def test_product_listing_valid(self):
        listing = ProductListing(
            title="Red Nike Running Shoes",
            description="Great condition, used once.",
            price=45.0,
            brand="Nike",
            category="Shoes",
            condition="Like New"
        )
        assert listing.title == "Red Nike Running Shoes"
        assert listing.price == 45.0
        assert listing.brand == "Nike"

    def test_product_listing_requires_title_desc_price(self):
        with pytest.raises(ValidationError):
            ProductListing(price=10.0)

    def test_product_listing_negative_price_invalid(self):
        with pytest.raises(ValidationError):
            ProductListing(title="T", description="D", price=-5.0)

    def test_product_listing_title_max_length(self):
        with pytest.raises(ValidationError):
            ProductListing(
                title="A" * 121,
                description="D",
                price=10.0
            )

    def test_platform_specific_defaults(self):
        listing = ProductListing(title="T", description="D", price=10.0)
        assert isinstance(listing.ebay, EbayData)
        assert isinstance(listing.vinted, VintedData)
        assert isinstance(listing.depop, DepopData)
        assert listing.ebay.category_id is None


# ======================================================================
# Generator Tests
# ======================================================================

class TestMockListingGenerator:

    @pytest.fixture
    def generator(self):
        return MockListingGenerator()

    @pytest.fixture
    def dummy_image(self, tmp_path) -> Path:
        p = tmp_path / "test_sneaker.jpg"
        p.touch()
        return p

    def test_generate_without_command(self, generator, dummy_image):
        result = generator.generate(dummy_image)
        
        assert result.success is True
        listing = result.listing
        assert listing is not None
        assert listing.title == "Test Sneaker Item"
        assert listing.price == 19.99
        assert "High-quality" in listing.description
        assert listing.category == "General"

    def test_generate_missing_image(self, generator, tmp_path):
        result = generator.generate(tmp_path / "ghost.jpg")
        assert result.success is False
        assert "not found" in result.error_message

    def test_generate_with_command_overrides(self, generator, dummy_image):
        command = ProcessImageCommand(
            image_path=str(dummy_image),
            title="Custom Title",
            price=99.0,
            brand="Gucci",
            color="Red",
            condition="New",
            category="Accessories"
        )
        result = generator.generate(dummy_image, command)
        
        assert result.success is True
        listing = result.listing
        
        assert listing.title == "Custom Title"
        assert listing.price == 99.0
        assert listing.brand == "Gucci"
        assert listing.color == "Red"
        assert listing.condition == "New"
        assert listing.category == "Accessories"
        
        # Tags should be derived from command
        assert "gucci" in listing.tags
        assert "red" in listing.tags

    def test_generate_dynamic_title_from_command(self, generator, dummy_image):
        # Without explicit title, should construct one from brand + color + category
        command = ProcessImageCommand(
            image_path=str(dummy_image),
            brand="Nike",
            color="Blue",
            category="Shoes",
            price=50.0
        )
        result = generator.generate(dummy_image, command)
        
        listing = result.listing
        assert listing.title == "Nike Blue Shoes"

    def test_generate_dynamic_description(self, generator, dummy_image):
        command = ProcessImageCommand(
            image_path=str(dummy_image),
            brand="Adidas",
            size="XL",
            condition="Used"
        )
        result = generator.generate(dummy_image, command)
        
        desc = result.listing.description
        assert "Brand: Adidas" in desc
        assert "Size: XL" in desc
        assert "Condition: Used" in desc


# ======================================================================
# Factory Tests
# ======================================================================

def test_create_listing_generator_mock():
    gen = create_listing_generator(mode="mock")
    assert isinstance(gen, MockListingGenerator)

def test_create_listing_generator_production_fallback():
    gen = create_listing_generator(mode="production")
    assert isinstance(gen, MockListingGenerator)
