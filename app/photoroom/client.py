"""
PhotoRoom API client — Abstract interface.

Defines the contract that all PhotoRoom implementations must follow.
The workflow engine depends on this interface, NOT on specific implementations.

Hierarchy:
    PhotoRoomClient (abstract)
    ├── MockPhotoRoomClient   — simulates processing for development/testing
    └── RealPhotoRoomClient   — calls the real PhotoRoom API (Task 14)
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from enum import Enum


# ---------------------------------------------------------------------------
# Result types
# ---------------------------------------------------------------------------

class ProcessingStatus(Enum):
    """Result status of a PhotoRoom processing operation."""
    SUCCESS = "success"
    FAILED = "failed"
    RATE_LIMITED = "rate_limited"
    AUTH_ERROR = "auth_error"
    TIMEOUT = "timeout"
    INVALID_IMAGE = "invalid_image"


@dataclass
class PhotoRoomResult:
    """
    Structured result from a PhotoRoom processing operation.

    Every call to remove_background() returns one of these, regardless
    of whether the operation succeeded or failed. This allows callers
    to inspect what happened without catching exceptions for expected
    failure modes (rate limits, invalid images, etc.).
    """

    # -- Status --
    status: ProcessingStatus
    success: bool

    # -- Output (populated on success) --
    output_path: Path | None = None
    output_format: str = "png"
    output_size_bytes: int = 0
    output_width: int = 0
    output_height: int = 0

    # -- Input metadata --
    input_path: Path | None = None
    input_size_bytes: int = 0

    # -- Processing metadata --
    processing_time_ms: int = 0
    api_credits_used: int = 0
    is_sandbox: bool = False

    # -- Error info (populated on failure) --
    error_message: str = ""
    error_code: str = ""
    is_retryable: bool = False

    # -- Timestamps --
    started_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    completed_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    @property
    def summary(self) -> str:
        """Human-readable one-line summary."""
        if self.success:
            return (
                f"SUCCESS: {self.input_path.name if self.input_path else '?'} → "
                f"{self.output_path.name if self.output_path else '?'} "
                f"({self.output_width}x{self.output_height}, "
                f"{self.output_size_bytes:,} bytes, "
                f"{self.processing_time_ms}ms)"
            )
        return (
            f"FAILED: {self.input_path.name if self.input_path else '?'} — "
            f"{self.error_message} "
            f"(retryable={self.is_retryable})"
        )


# ---------------------------------------------------------------------------
# Abstract client
# ---------------------------------------------------------------------------

class PhotoRoomClient(ABC):
    """
    Abstract interface for PhotoRoom background-removal operations.

    All implementations must provide:
    - remove_background(): core background removal
    - is_available(): connectivity/auth check
    - get_client_info(): metadata about the implementation
    """

    @abstractmethod
    def remove_background(
        self,
        image_path: Path,
        output_path: Path | None = None,
        *,
        bg_color: str | None = None,
        output_size: tuple[int, int] | None = None,
        sandbox: bool = False,
    ) -> PhotoRoomResult:
        """
        Remove the background from an image.

        Args:
            image_path: Path to the input image file.
            output_path: Where to save the processed image.
                         If None, a default path is generated next to the input.
            bg_color: Optional background color (hex, e.g., "#FFFFFF").
                      If None, the background is transparent (PNG).
            output_size: Optional (width, height) to resize the output.
            sandbox: If True, use sandbox mode (watermarked, no credits).

        Returns:
            PhotoRoomResult with processing outcome and metadata.
        """
        ...

    @abstractmethod
    def is_available(self) -> bool:
        """
        Check if the client is ready to process images.

        For MockPhotoRoomClient: always True.
        For RealPhotoRoomClient: tests API connectivity and auth.
        """
        ...

    @abstractmethod
    def get_client_info(self) -> dict:
        """
        Return metadata about this client implementation.

        Returns:
            Dict with keys like 'type', 'version', 'is_mock', 'sandbox', etc.
        """
        ...
