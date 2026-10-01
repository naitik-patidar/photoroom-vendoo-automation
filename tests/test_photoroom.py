"""
Tests for app.photoroom — PhotoRoom client interface, mock, and factory.
"""

import os
from pathlib import Path

import pytest
from PIL import Image

from app.photoroom.client import (
    PhotoRoomClient,
    PhotoRoomResult,
    ProcessingStatus,
)
from app.photoroom.mock_client import MockPhotoRoomClient
from app.photoroom.real_client import RealPhotoRoomClient
from app.photoroom import create_photoroom_client


# ======================================================================
# PhotoRoomResult tests
# ======================================================================

class TestPhotoRoomResult:
    """Test the result dataclass."""

    def test_success_result_summary(self, tmp_path):
        result = PhotoRoomResult(
            status=ProcessingStatus.SUCCESS,
            success=True,
            input_path=tmp_path / "input.jpg",
            output_path=tmp_path / "output.png",
            output_width=800,
            output_height=600,
            output_size_bytes=12345,
            processing_time_ms=250,
        )
        summary = result.summary
        assert "SUCCESS" in summary
        assert "input.jpg" in summary
        assert "output.png" in summary
        assert "800x600" in summary
        assert "250ms" in summary

    def test_failure_result_summary(self, tmp_path):
        result = PhotoRoomResult(
            status=ProcessingStatus.FAILED,
            success=False,
            input_path=tmp_path / "input.jpg",
            error_message="Something went wrong",
            is_retryable=True,
        )
        summary = result.summary
        assert "FAILED" in summary
        assert "Something went wrong" in summary
        assert "retryable=True" in summary


# ======================================================================
# MockPhotoRoomClient tests
# ======================================================================

class TestMockPhotoRoomClient:
    """Test the mock PhotoRoom client."""

    def test_is_photoroom_client(self):
        """Mock must be an instance of the abstract interface."""
        client = MockPhotoRoomClient()
        assert isinstance(client, PhotoRoomClient)

    def test_is_available(self):
        """Mock is always available."""
        client = MockPhotoRoomClient()
        assert client.is_available() is True

    def test_get_client_info(self):
        """Client info should identify as mock."""
        client = MockPhotoRoomClient()
        info = client.get_client_info()
        assert info["type"] == "mock"
        assert info["is_mock"] is True
        assert info["version"] == "1.0.0"

    def test_remove_background_success(self, sample_image_path, tmp_path):
        """Should successfully process a valid image."""
        client = MockPhotoRoomClient()
        output_path = tmp_path / "processed.png"

        result = client.remove_background(sample_image_path, output_path)

        assert result.success is True
        assert result.status == ProcessingStatus.SUCCESS
        assert result.output_path == output_path
        assert output_path.exists()
        assert result.output_size_bytes > 0
        assert result.output_width > 0
        assert result.output_height > 0
        assert result.processing_time_ms > 0
        assert result.error_message == ""

    def test_output_is_valid_png(self, sample_image_path, tmp_path):
        """Output should be a valid PNG image."""
        client = MockPhotoRoomClient()
        output_path = tmp_path / "processed.png"

        client.remove_background(sample_image_path, output_path)

        with Image.open(output_path) as img:
            assert img.format == "PNG"
            assert img.mode == "RGBA"  # Should have alpha channel

    def test_output_has_transparency(self, sample_image_path, tmp_path):
        """Output should have transparent areas (background removed)."""
        client = MockPhotoRoomClient()
        output_path = tmp_path / "processed.png"

        client.remove_background(sample_image_path, output_path)

        with Image.open(output_path) as img:
            assert img.mode == "RGBA"
            # Check that some pixels are transparent (alpha < 255)
            alpha = img.split()[3]
            alpha_bytes = alpha.tobytes()
            min_alpha = min(alpha_bytes)
            assert min_alpha < 255, "Output should have transparent regions"

    def test_original_image_not_modified(self, sample_image_path, tmp_path):
        """Original image must NEVER be overwritten."""
        original_size = sample_image_path.stat().st_size
        original_bytes = sample_image_path.read_bytes()

        client = MockPhotoRoomClient()
        output_path = tmp_path / "processed.png"
        client.remove_background(sample_image_path, output_path)

        assert sample_image_path.stat().st_size == original_size
        assert sample_image_path.read_bytes() == original_bytes

    def test_default_output_path(self, sample_image_path):
        """When no output_path given, should create one next to the input."""
        client = MockPhotoRoomClient()

        result = client.remove_background(sample_image_path)

        assert result.success is True
        expected_name = f"{sample_image_path.stem}_processed.png"
        assert result.output_path.name == expected_name
        assert result.output_path.parent == sample_image_path.parent
        assert result.output_path.exists()

    def test_output_directory_created(self, sample_image_path, tmp_path):
        """Should create output directory if it doesn't exist."""
        client = MockPhotoRoomClient()
        nested_output = tmp_path / "deep" / "nested" / "dir" / "out.png"

        result = client.remove_background(sample_image_path, nested_output)

        assert result.success is True
        assert nested_output.exists()

    def test_with_bg_color(self, sample_image_path, tmp_path):
        """Should apply background color when specified."""
        client = MockPhotoRoomClient()
        output_path = tmp_path / "processed.png"

        result = client.remove_background(
            sample_image_path, output_path, bg_color="#FFFFFF"
        )

        assert result.success is True
        assert output_path.exists()

    def test_with_output_size(self, sample_image_path, tmp_path):
        """Should resize output when output_size specified."""
        client = MockPhotoRoomClient()
        output_path = tmp_path / "processed.png"

        result = client.remove_background(
            sample_image_path, output_path, output_size=(50, 50)
        )

        assert result.success is True
        assert result.output_width == 50
        assert result.output_height == 50

        with Image.open(output_path) as img:
            assert img.size == (50, 50)

    def test_metadata_populated(self, sample_image_path, tmp_path):
        """Result should have all metadata fields populated."""
        client = MockPhotoRoomClient()
        output_path = tmp_path / "processed.png"

        result = client.remove_background(sample_image_path, output_path)

        assert result.input_path == sample_image_path
        assert result.input_size_bytes > 0
        assert result.output_path == output_path
        assert result.output_format == "png"
        assert result.api_credits_used == 0  # mock never uses credits
        assert result.is_sandbox is True
        assert result.started_at is not None
        assert result.completed_at is not None
        assert result.completed_at >= result.started_at

    # --- Input validation tests ---

    def test_file_not_found(self, tmp_path):
        """Should return INVALID_IMAGE when file doesn't exist."""
        client = MockPhotoRoomClient()
        fake_path = tmp_path / "nonexistent.jpg"

        result = client.remove_background(fake_path)

        assert result.success is False
        assert result.status == ProcessingStatus.INVALID_IMAGE
        assert "not found" in result.error_message.lower()
        assert result.error_code == "FILE_NOT_FOUND"
        assert result.is_retryable is False

    def test_unsupported_format(self, tmp_path):
        """Should return INVALID_IMAGE for unsupported file formats."""
        client = MockPhotoRoomClient()
        bad_file = tmp_path / "document.pdf"
        bad_file.write_bytes(b"fake pdf content")

        result = client.remove_background(bad_file)

        assert result.success is False
        assert result.status == ProcessingStatus.INVALID_IMAGE
        assert "unsupported" in result.error_message.lower()
        assert result.error_code == "UNSUPPORTED_FORMAT"

    def test_corrupted_image(self, tmp_path):
        """Should return INVALID_IMAGE for corrupted image files."""
        client = MockPhotoRoomClient()
        corrupt_file = tmp_path / "corrupt.png"
        corrupt_file.write_bytes(b"this is not a real PNG file at all")

        result = client.remove_background(corrupt_file)

        assert result.success is False
        assert result.status == ProcessingStatus.INVALID_IMAGE
        assert result.error_code == "CORRUPTED_IMAGE"

    def test_file_too_large(self, tmp_path):
        """Should return INVALID_IMAGE for oversized files."""
        client = MockPhotoRoomClient()

        # Create a file that exceeds the max size
        large_file = tmp_path / "huge.png"
        # Create a valid PNG that's very large by making it huge resolution
        img = Image.new("RGB", (100, 100), color=(128, 128, 128))
        img.save(large_file)

        # Monkey-patch the max size to be tiny for this test
        import app.photoroom.mock_client as mock_module
        original_max = mock_module.MAX_IMAGE_FILE_SIZE_BYTES
        mock_module.MAX_IMAGE_FILE_SIZE_BYTES = 10  # 10 bytes

        try:
            result = client.remove_background(large_file)
            assert result.success is False
            assert result.status == ProcessingStatus.INVALID_IMAGE
            assert result.error_code == "FILE_TOO_LARGE"
        finally:
            mock_module.MAX_IMAGE_FILE_SIZE_BYTES = original_max

    # --- Error simulation tests ---

    def test_simulate_rate_limit(self, sample_image_path):
        """Should simulate rate-limit errors when configured."""
        client = MockPhotoRoomClient(simulate_error=ProcessingStatus.RATE_LIMITED)

        result = client.remove_background(sample_image_path)

        assert result.success is False
        assert result.status == ProcessingStatus.RATE_LIMITED
        assert result.is_retryable is True
        assert "rate limit" in result.error_message.lower()

    def test_simulate_auth_error(self, sample_image_path):
        """Should simulate auth errors when configured."""
        client = MockPhotoRoomClient(simulate_error=ProcessingStatus.AUTH_ERROR)

        result = client.remove_background(sample_image_path)

        assert result.success is False
        assert result.status == ProcessingStatus.AUTH_ERROR
        assert result.is_retryable is False

    def test_simulate_timeout(self, sample_image_path):
        """Should simulate timeout errors when configured."""
        client = MockPhotoRoomClient(simulate_error=ProcessingStatus.TIMEOUT)

        result = client.remove_background(sample_image_path)

        assert result.success is False
        assert result.status == ProcessingStatus.TIMEOUT
        assert result.is_retryable is True

    def test_set_simulate_error_after_creation(self, sample_image_path, tmp_path):
        """Should be able to change error simulation at runtime."""
        client = MockPhotoRoomClient()

        # First call succeeds
        result1 = client.remove_background(
            sample_image_path, tmp_path / "out1.png"
        )
        assert result1.success is True

        # Enable error simulation
        client.set_simulate_error(ProcessingStatus.RATE_LIMITED)
        result2 = client.remove_background(sample_image_path)
        assert result2.success is False

        # Disable error simulation
        client.set_simulate_error(None)
        result3 = client.remove_background(
            sample_image_path, tmp_path / "out3.png"
        )
        assert result3.success is True

    def test_reset(self, sample_image_path, tmp_path):
        """Reset should clear call count and error simulation."""
        client = MockPhotoRoomClient(simulate_error=ProcessingStatus.FAILED)
        client.remove_background(sample_image_path)

        client.reset()
        info = client.get_client_info()
        assert info["call_count"] == 0
        assert info["simulate_error"] is None

        # Should work after reset
        result = client.remove_background(
            sample_image_path, tmp_path / "after_reset.png"
        )
        assert result.success is True

    def test_call_count_increments(self, sample_image_path, tmp_path):
        """Call count should increment with each call."""
        client = MockPhotoRoomClient()

        for i in range(3):
            client.remove_background(
                sample_image_path, tmp_path / f"out_{i}.png"
            )

        info = client.get_client_info()
        assert info["call_count"] == 3

    # --- Multiple image formats ---

    def test_jpg_input(self, tmp_path):
        """Should handle JPEG input."""
        client = MockPhotoRoomClient()
        img = Image.new("RGB", (80, 80), color=(0, 100, 200))
        jpg_path = tmp_path / "test.jpg"
        img.save(jpg_path, "JPEG")

        result = client.remove_background(jpg_path, tmp_path / "out.png")
        assert result.success is True

    def test_webp_input(self, tmp_path):
        """Should handle WebP input."""
        client = MockPhotoRoomClient()
        img = Image.new("RGB", (80, 80), color=(200, 100, 0))
        webp_path = tmp_path / "test.webp"
        img.save(webp_path, "WebP")

        result = client.remove_background(webp_path, tmp_path / "out.png")
        assert result.success is True


# ======================================================================
# RealPhotoRoomClient stub tests
# ======================================================================

import responses
import requests

class TestRealPhotoRoomClient:
    """Test the real client."""

    def test_is_photoroom_client(self):
        client = RealPhotoRoomClient(api_key="test")
        assert isinstance(client, PhotoRoomClient)

    def test_is_available(self):
        client = RealPhotoRoomClient(api_key="test_key")
        assert client.is_available() is True

    def test_is_not_available_placeholder(self):
        client = RealPhotoRoomClient(api_key="YOUR_API_KEY_HERE")
        assert client.is_available() is False

    def test_client_info(self):
        client = RealPhotoRoomClient(api_key="test")
        info = client.get_client_info()
        assert info["type"] == "real"
        assert info["is_stub"] is False
        assert info["is_mock"] is False

    @responses.activate
    def test_remove_background_success(self, sample_image_path, tmp_path):
        client = RealPhotoRoomClient(api_key="test_key")
        output_path = tmp_path / "out.png"
        
        # Mock successful response
        fake_png = b"\\x89PNG\\r\\n\\x1a\\n\\x00\\x00\\x00\\rIHDR\\x00\\x00\\x00\\x01\\x00\\x00\\x00\\x01\\x08\\x06\\x00\\x00\\x00\\x1f\\x15\\xc4\\x89"
        responses.add(
            responses.POST, 
            "https://sdk.photoroom.com/v1/segment",
            body=fake_png, 
            status=200
        )
        
        result = client.remove_background(sample_image_path, output_path)
        
        assert result.success is True
        assert result.status == ProcessingStatus.SUCCESS
        assert output_path.exists()
        assert output_path.read_bytes() == fake_png
        assert len(responses.calls) == 1
        
        # Verify request details
        req = responses.calls[0].request
        assert req.headers["x-api-key"] == "test_key"
        # It's multipart/form-data
        assert "multipart/form-data" in req.headers["Content-Type"]

    @responses.activate
    def test_remove_background_auth_error(self, sample_image_path, tmp_path):
        client = RealPhotoRoomClient(api_key="bad_key")
        
        responses.add(
            responses.POST, 
            "https://sdk.photoroom.com/v1/segment",
            json={"error": "Unauthorized"}, 
            status=401
        )
        
        result = client.remove_background(sample_image_path, tmp_path / "out.png")
        
        assert result.success is False
        assert result.status == ProcessingStatus.AUTH_ERROR
        assert result.is_retryable is False

    @responses.activate
    def test_remove_background_rate_limit(self, sample_image_path, tmp_path):
        client = RealPhotoRoomClient(api_key="test_key")
        
        responses.add(
            responses.POST, 
            "https://sdk.photoroom.com/v1/segment",
            json={"error": "Too Many Requests"}, 
            status=429
        )
        
        result = client.remove_background(sample_image_path, tmp_path / "out.png")
        
        assert result.success is False
        assert result.status == ProcessingStatus.RATE_LIMITED
        assert result.is_retryable is True

    @responses.activate
    def test_remove_background_server_error(self, sample_image_path, tmp_path):
        client = RealPhotoRoomClient(api_key="test_key")
        
        responses.add(
            responses.POST, 
            "https://sdk.photoroom.com/v1/segment",
            json={"error": "Internal Server Error"}, 
            status=500
        )
        
        result = client.remove_background(sample_image_path, tmp_path / "out.png")
        
        assert result.success is False
        assert result.status == ProcessingStatus.FAILED
        assert result.is_retryable is True
        
    @responses.activate
    def test_remove_background_timeout(self, sample_image_path, tmp_path):
        client = RealPhotoRoomClient(api_key="test_key")
        
        responses.add(
            responses.POST, 
            "https://sdk.photoroom.com/v1/segment",
            body=requests.exceptions.Timeout("Connection timed out")
        )
        
        result = client.remove_background(sample_image_path, tmp_path / "out.png")
        
        assert result.success is False
        assert result.status == ProcessingStatus.TIMEOUT
        assert result.is_retryable is True

    def test_missing_input_file(self, tmp_path):
        client = RealPhotoRoomClient(api_key="test_key")
        result = client.remove_background(tmp_path / "missing.jpg", tmp_path / "out.png")
        
        assert result.success is False
        assert result.status == ProcessingStatus.INVALID_IMAGE

    def test_missing_api_key_aborts_early(self, sample_image_path, tmp_path):
        client = RealPhotoRoomClient(api_key="YOUR_API_KEY_HERE")
        result = client.remove_background(sample_image_path, tmp_path / "out.png")
        
        assert result.success is False
        assert result.status == ProcessingStatus.AUTH_ERROR
        assert result.error_code == "MISSING_API_KEY"


# ======================================================================
# Factory function tests
# ======================================================================

class TestCreatePhotoRoomClient:
    """Test the client factory function."""

    def test_mock_mode(self):
        """Should create MockPhotoRoomClient in mock mode."""
        client = create_photoroom_client(mode="mock")
        assert isinstance(client, MockPhotoRoomClient)

    def test_production_mode(self):
        """Should create RealPhotoRoomClient in production mode."""
        client = create_photoroom_client(mode="production", api_key="key")
        assert isinstance(client, RealPhotoRoomClient)

    def test_default_is_mock(self):
        """Default mode should be mock."""
        client = create_photoroom_client()
        assert isinstance(client, MockPhotoRoomClient)
