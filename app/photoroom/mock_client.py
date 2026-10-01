"""
MockPhotoRoomClient — Simulates PhotoRoom background removal for development.

This mock implementation:
- Accepts real image files (validates they exist and are valid images)
- Simulates background removal by making non-subject pixels transparent
- Produces a realistic processed PNG output
- Returns structured metadata matching the real API behavior
- Simulates configurable errors for testing error-handling paths
- Adds a subtle visual indicator to distinguish mock output from real output

The entire application can be built and tested using this mock before
the real PhotoRoom API key is available.
"""

import time
import random
from pathlib import Path
from datetime import datetime, timezone

from PIL import Image, ImageDraw, ImageFont

from app.photoroom.client import (
    PhotoRoomClient,
    PhotoRoomResult,
    ProcessingStatus,
)
from app.config.constants import (
    SUPPORTED_INPUT_FORMATS,
    MAX_IMAGE_FILE_SIZE_BYTES,
    PROCESSED_SUFFIX,
    DEFAULT_OUTPUT_FORMAT,
)
from app.logging import get_logger

logger = get_logger("photoroom.mock")


class MockPhotoRoomClient(PhotoRoomClient):
    """
    Mock PhotoRoom client that simulates background removal locally.

    Uses Pillow to create a realistic processed output:
    - Removes pixels near the edges (simulating background removal)
    - Preserves the center of the image (simulating subject retention)
    - Saves as transparent PNG
    - Adds a small "MOCK" watermark to distinguish from real output

    Error simulation:
        Set `simulate_error` to a ProcessingStatus to force that error
        on the next call. Useful for testing error-handling paths.

    Processing delay:
        Set `simulate_delay_ms` to add artificial latency (default: 100-500ms).
    """

    def __init__(
        self,
        simulate_error: ProcessingStatus | None = None,
        simulate_delay_ms: int | None = None,
        sandbox: bool = True,
    ):
        self._simulate_error = simulate_error
        self._simulate_delay_ms = simulate_delay_ms
        self._sandbox = sandbox
        self._call_count = 0
        logger.info(
            "MockPhotoRoomClient initialized "
            f"(sandbox={sandbox}, simulate_error={simulate_error})"
        )

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def remove_background(
        self,
        image_path: Path,
        output_path: Path | None = None,
        *,
        bg_color: str | None = None,
        output_size: tuple[int, int] | None = None,
        sandbox: bool = False,
    ) -> PhotoRoomResult:
        """Simulate background removal on a local image."""
        self._call_count += 1
        started_at = datetime.now(timezone.utc)
        image_path = Path(image_path)

        logger.info(f"[Mock] Processing image: {image_path.name} (call #{self._call_count})")

        # --- Simulate delay ---
        delay_ms = self._simulate_delay_ms or random.randint(100, 500)
        time.sleep(delay_ms / 1000.0)

        # --- Simulate errors if configured ---
        if self._simulate_error is not None:
            return self._make_error_result(
                image_path, started_at, self._simulate_error
            )

        # --- Validate input image ---
        validation_error = self._validate_input(image_path)
        if validation_error:
            return validation_error

        # --- Process image ---
        try:
            output_path = self._resolve_output_path(image_path, output_path)
            result_meta = self._process_image(
                image_path, output_path, bg_color, output_size
            )

            completed_at = datetime.now(timezone.utc)
            processing_time_ms = int(
                (completed_at - started_at).total_seconds() * 1000
            )

            result = PhotoRoomResult(
                status=ProcessingStatus.SUCCESS,
                success=True,
                output_path=output_path,
                output_format="png",
                output_size_bytes=output_path.stat().st_size,
                output_width=result_meta["width"],
                output_height=result_meta["height"],
                input_path=image_path,
                input_size_bytes=image_path.stat().st_size,
                processing_time_ms=processing_time_ms,
                api_credits_used=0,  # mock uses no credits
                is_sandbox=self._sandbox or sandbox,
                started_at=started_at,
                completed_at=completed_at,
            )

            logger.info(f"[Mock] {result.summary}")
            return result

        except Exception as e:
            logger.error(f"[Mock] Unexpected error processing {image_path.name}: {e}")
            return PhotoRoomResult(
                status=ProcessingStatus.FAILED,
                success=False,
                input_path=image_path,
                input_size_bytes=image_path.stat().st_size if image_path.exists() else 0,
                error_message=f"Mock processing error: {e}",
                error_code="MOCK_INTERNAL_ERROR",
                is_retryable=False,
                started_at=started_at,
                completed_at=datetime.now(timezone.utc),
            )

    def is_available(self) -> bool:
        """Mock is always available."""
        return True

    def get_client_info(self) -> dict:
        """Return mock client metadata."""
        return {
            "type": "mock",
            "version": "1.0.0",
            "is_mock": True,
            "sandbox": self._sandbox,
            "call_count": self._call_count,
            "simulate_error": (
                self._simulate_error.value if self._simulate_error else None
            ),
        }

    # ------------------------------------------------------------------
    # Configuration methods
    # ------------------------------------------------------------------

    def set_simulate_error(self, error: ProcessingStatus | None) -> None:
        """Configure error simulation for subsequent calls."""
        self._simulate_error = error
        logger.info(f"[Mock] Error simulation set to: {error}")

    def reset(self) -> None:
        """Reset call count and error simulation."""
        self._call_count = 0
        self._simulate_error = None
        logger.info("[Mock] Client reset")

    # ------------------------------------------------------------------
    # Internal methods
    # ------------------------------------------------------------------

    def _validate_input(self, image_path: Path) -> PhotoRoomResult | None:
        """Validate the input image. Returns an error result or None if valid."""
        if not image_path.exists():
            return PhotoRoomResult(
                status=ProcessingStatus.INVALID_IMAGE,
                success=False,
                input_path=image_path,
                error_message=f"Image file not found: {image_path}",
                error_code="FILE_NOT_FOUND",
                is_retryable=False,
            )

        suffix = image_path.suffix.lower()
        if suffix not in SUPPORTED_INPUT_FORMATS:
            return PhotoRoomResult(
                status=ProcessingStatus.INVALID_IMAGE,
                success=False,
                input_path=image_path,
                error_message=(
                    f"Unsupported format: {suffix}. "
                    f"Supported: {', '.join(sorted(SUPPORTED_INPUT_FORMATS))}"
                ),
                error_code="UNSUPPORTED_FORMAT",
                is_retryable=False,
            )

        file_size = image_path.stat().st_size
        if file_size > MAX_IMAGE_FILE_SIZE_BYTES:
            return PhotoRoomResult(
                status=ProcessingStatus.INVALID_IMAGE,
                success=False,
                input_path=image_path,
                input_size_bytes=file_size,
                error_message=(
                    f"Image too large: {file_size:,} bytes "
                    f"(max: {MAX_IMAGE_FILE_SIZE_BYTES:,} bytes)"
                ),
                error_code="FILE_TOO_LARGE",
                is_retryable=False,
            )

        # Verify it's a valid image
        try:
            with Image.open(image_path) as img:
                img.verify()
        except Exception as e:
            return PhotoRoomResult(
                status=ProcessingStatus.INVALID_IMAGE,
                success=False,
                input_path=image_path,
                input_size_bytes=file_size,
                error_message=f"Invalid or corrupted image: {e}",
                error_code="CORRUPTED_IMAGE",
                is_retryable=False,
            )

        return None  # Valid

    def _resolve_output_path(
        self, image_path: Path, output_path: Path | None
    ) -> Path:
        """Determine the output file path."""
        if output_path is not None:
            output_path = Path(output_path)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            return output_path

        # Generate default: same directory, _processed suffix, .png
        stem = image_path.stem
        output = image_path.parent / f"{stem}{PROCESSED_SUFFIX}{DEFAULT_OUTPUT_FORMAT}"
        return output

    def _process_image(
        self,
        input_path: Path,
        output_path: Path,
        bg_color: str | None,
        output_size: tuple[int, int] | None,
    ) -> dict:
        """
        Simulate background removal using Pillow.

        Strategy:
        1. Open the image
        2. Convert to RGBA
        3. Create an elliptical mask centered on the image
           (simulating subject detection — keeps center, removes edges)
        4. Apply transparency to the "background" (outer region)
        5. Optionally apply bg_color instead of transparency
        6. Add "MOCK" watermark
        7. Optionally resize
        8. Save as PNG
        """
        with Image.open(input_path) as img:
            # Convert to RGBA for transparency support
            img = img.convert("RGBA")
            width, height = img.size

            # Create a mask: ellipse in the center = "subject"
            mask = Image.new("L", (width, height), 0)
            draw = ImageDraw.Draw(mask)

            # Ellipse covering ~70% of the image (simulates subject region)
            margin_x = int(width * 0.15)
            margin_y = int(height * 0.10)
            draw.ellipse(
                [margin_x, margin_y, width - margin_x, height - margin_y],
                fill=255,
            )

            # Apply the mask as alpha channel
            # Blend: keep original alpha where mask is white, make transparent where black
            r, g, b, a = img.split()
            # Combine existing alpha with our mask
            from PIL import ImageChops
            combined_alpha = ImageChops.multiply(a, mask)
            img.putalpha(combined_alpha)

            # Apply background color if specified
            if bg_color:
                bg_img = Image.new("RGBA", img.size, bg_color)
                bg_img.paste(img, mask=img.split()[3])
                img = bg_img

            # Add "MOCK" watermark in bottom-right corner
            img = self._add_watermark(img)

            # Resize if requested
            if output_size:
                img = img.resize(output_size, Image.Resampling.LANCZOS)

            final_width, final_height = img.size

            # Save
            output_path.parent.mkdir(parents=True, exist_ok=True)
            img.save(output_path, "PNG")

        return {
            "width": final_width,
            "height": final_height,
        }

    def _add_watermark(self, img: Image.Image) -> Image.Image:
        """Add a small 'MOCK' watermark to the bottom-right corner."""
        draw = ImageDraw.Draw(img)
        text = "MOCK"

        # Use default font (small)
        try:
            font = ImageFont.load_default()
        except Exception:
            font = None

        # Calculate position (bottom-right with padding)
        bbox = draw.textbbox((0, 0), text, font=font)
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]

        x = img.width - text_width - 8
        y = img.height - text_height - 8

        # Semi-transparent background for readability
        padding = 3
        draw.rectangle(
            [x - padding, y - padding, x + text_width + padding, y + text_height + padding],
            fill=(0, 0, 0, 128),
        )
        draw.text((x, y), text, fill=(255, 255, 0, 200), font=font)

        return img

    def _make_error_result(
        self,
        image_path: Path,
        started_at: datetime,
        error_type: ProcessingStatus,
    ) -> PhotoRoomResult:
        """Create an error result for simulated failures."""
        error_configs = {
            ProcessingStatus.RATE_LIMITED: {
                "message": "Rate limit exceeded. Try again later.",
                "code": "RATE_LIMIT",
                "retryable": True,
            },
            ProcessingStatus.AUTH_ERROR: {
                "message": "Invalid API key. Check PHOTOROOM_API_KEY.",
                "code": "AUTH_FAILED",
                "retryable": False,
            },
            ProcessingStatus.TIMEOUT: {
                "message": "Request timed out after 60 seconds.",
                "code": "TIMEOUT",
                "retryable": True,
            },
            ProcessingStatus.FAILED: {
                "message": "Internal server error (simulated).",
                "code": "SERVER_ERROR",
                "retryable": True,
            },
        }

        config = error_configs.get(error_type, {
            "message": f"Simulated error: {error_type.value}",
            "code": "SIMULATED",
            "retryable": False,
        })

        logger.warning(
            f"[Mock] Simulated error: {config['code']} — {config['message']}"
        )

        return PhotoRoomResult(
            status=error_type,
            success=False,
            input_path=image_path,
            input_size_bytes=image_path.stat().st_size if image_path.exists() else 0,
            error_message=config["message"],
            error_code=config["code"],
            is_retryable=config["retryable"],
            started_at=started_at,
            completed_at=datetime.now(timezone.utc),
        )
