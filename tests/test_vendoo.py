"""
Tests for app.vendoo — Vendoo connector and integration.
"""

import pytest
from pathlib import Path

from app.vendoo.mock_connector import MockVendooConnector
from app.vendoo.real_connector import RealVendooConnector
from app.vendoo import create_vendoo_connector
from app.listings.schemas import ProductListing


@pytest.fixture
def dummy_image(tmp_path) -> Path:
    p = tmp_path / "test_image.jpg"
    p.touch()
    return p

@pytest.fixture
def sample_listing() -> ProductListing:
    return ProductListing(
        title="Test Shirt",
        description="A great shirt.",
        price=15.0
    )


# ======================================================================
# MockVendooConnector Tests
# ======================================================================

class TestMockVendooConnector:

    def test_submit_success(self, dummy_image, sample_listing):
        connector = MockVendooConnector(simulate_delay_ms=0)
        result = connector.submit_listing(sample_listing, dummy_image)
        
        assert result.success is True
        assert result.vendoo_item_id is not None
        assert result.vendoo_item_id.startswith("vdo_")
        assert result.item_url is not None
        assert result.error_message == ""
        
    def test_submit_missing_image_fails(self, tmp_path, sample_listing):
        connector = MockVendooConnector(simulate_delay_ms=0)
        result = connector.submit_listing(sample_listing, tmp_path / "ghost.jpg")
        
        assert result.success is False
        assert "not found" in result.error_message
        assert result.is_retryable is False

    def test_submit_simulated_error(self, dummy_image, sample_listing):
        connector = MockVendooConnector(simulate_delay_ms=0, simulate_error=True)
        result = connector.submit_listing(sample_listing, dummy_image)
        
        assert result.success is False
        assert "timeout" in result.error_message
        assert result.is_retryable is True


# ======================================================================
# RealVendooConnector Tests
# ======================================================================

class TestRealVendooConnector:
    def test_submit_success_writes_csv(self, tmp_path, dummy_image, sample_listing):
        connector = RealVendooConnector(output_dir=str(tmp_path))
        result = connector.submit_listing(sample_listing, dummy_image)
        
        assert result.success is True
        assert result.vendoo_item_id.startswith("csv_handoff_")
        
        csv_path = tmp_path / "vendoo_import_handoff.csv"
        assert csv_path.exists()
        
        content = csv_path.read_text(encoding="utf-8-sig")
        assert "Test Shirt" in content
        assert "A great shirt." in content
        assert "15.0" in content
        assert str(dummy_image.absolute()) in content
        
        # Verify deterministic headers
        lines = content.strip().split("\n")
        assert lines[0] == "Title,Description,Price,Brand,Color,Condition,Category,Image Path,Date Generated"

    def test_special_characters_in_csv(self, tmp_path, dummy_image):
        connector = RealVendooConnector(output_dir=str(tmp_path))
        listing = ProductListing.model_construct(
            title='Shirt, with "quotes" & commas',
            description="Line 1\nLine 2, and more",
            price=20.5
        )
        result = connector.submit_listing(listing, dummy_image)
        assert result.success is True
        
        csv_path = tmp_path / "vendoo_import_handoff.csv"
        # The csv module should safely enclose these in quotes
        content = csv_path.read_text(encoding="utf-8-sig")
        assert '"Shirt, with ""quotes"" & commas"' in content
        assert '"Line 1' in content

    def test_multiple_listings_appended(self, tmp_path, dummy_image):
        connector = RealVendooConnector(output_dir=str(tmp_path))
        
        listing1 = ProductListing.model_construct(title="First", description="Desc", price=1.0)
        listing2 = ProductListing.model_construct(title="Second", description="Desc", price=2.0)
        
        connector.submit_listing(listing1, dummy_image)
        connector.submit_listing(listing2, dummy_image)
        
        # Instantiate another connector to test repeated execution
        connector2 = RealVendooConnector(output_dir=str(tmp_path))
        listing3 = ProductListing.model_construct(title="Third", description="Desc", price=3.0)
        connector2.submit_listing(listing3, dummy_image)
        
        csv_path = tmp_path / "vendoo_import_handoff.csv"
        lines = csv_path.read_text(encoding="utf-8-sig").strip().split("\n")
        
        assert len(lines) == 4 # 1 header + 3 listings
        assert lines[0].startswith("Title,")
        assert "First" in lines[1]
        assert "Second" in lines[2]
        assert "Third" in lines[3]

    def test_missing_image_fails(self, tmp_path, sample_listing):
        connector = RealVendooConnector(output_dir=str(tmp_path))
        result = connector.submit_listing(sample_listing, tmp_path / "missing.jpg")
        
        assert result.success is False
        assert "not found" in result.error_message
        assert result.is_retryable is False

    def test_missing_title_fails(self, tmp_path, dummy_image):
        connector = RealVendooConnector(output_dir=str(tmp_path))
        listing = ProductListing.model_construct(title="", description="Desc", price=10.0)
        result = connector.submit_listing(listing, dummy_image)
        
        assert result.success is False
        assert "missing a title" in result.error_message
        assert result.is_retryable is False


# ======================================================================
# Factory Tests
# ======================================================================

def test_create_vendoo_connector_mock():
    conn = create_vendoo_connector(mode="mock")
    assert isinstance(conn, MockVendooConnector)

def test_create_vendoo_connector_production(tmp_path, monkeypatch):
    monkeypatch.setenv("OUTPUT_DIR", str(tmp_path))
    conn = create_vendoo_connector(mode="production")
    assert isinstance(conn, RealVendooConnector)
