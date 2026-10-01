"""
RealPhotoRoomClient — Calls the actual PhotoRoom API.

Endpoint: POST https://sdk.photoroom.com/v1/segment
Auth: x-api-key header
Input: multipart/form-data with image_file field
Output: PNG binary (transparent background)
"""

import time
import requests
from pathlib import Path
from datetime import datetime, timezone

from app.photoroom.client import (
    PhotoRoomClient,
    PhotoRoomResult,
    ProcessingStatus,
)
from app.logging import get_logger

logger = get_logger("photoroom.real")


class RealPhotoRoomClient(PhotoRoomClient):
    """
    Real PhotoRoom API client for removing backgrounds.
    """

    API_URL = "https://sdk.photoroom.com/v1/segment"

    def __init__(self, api_key: str, sandbox: bool = False):
        self._api_key = api_key
        self._sandbox = sandbox
        
        # In sandbox/test mode we can optionally hit a different endpoint or pass a flag if supported.
        # Currently, PhotoRoom uses API keys to differentiate billing/environments, 
        # but we'll store the sandbox flag just in case.
        logger.info(
            f"RealPhotoRoomClient initialized "
            f"(sandbox={sandbox}, key={'***SET***' if api_key and api_key != 'YOUR_API_KEY_HERE' else '***MISSING***'})"
        )

    def is_available(self) -> bool:
        """Returns True if the API key is configured and not the default placeholder."""
        return bool(self._api_key and self._api_key != "YOUR_API_KEY_HERE")

    def get_client_info(self) -> dict:
        """Return client metadata."""
        return {
            "type": "real",
            "version": "1.0.0",
            "is_mock": False,
            "is_stub": False,
            "sandbox": self._sandbox,
            "has_key": self.is_available(),
        }

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
        Calls POST https://sdk.photoroom.com/v1/segment to remove the background.
        """
        start_time = time.time()
        started_at = datetime.now(timezone.utc)
        
        # Ensure input exists
        image_path = Path(image_path)
        if not image_path.exists():
            return PhotoRoomResult(
                status=ProcessingStatus.INVALID_IMAGE,
                success=False,
                input_path=image_path,
                error_message=f"Input file not found: {image_path}",
                error_code="FILE_NOT_FOUND",
                is_retryable=False,
                started_at=started_at,
                completed_at=datetime.now(timezone.utc),
            )
            
        # Determine output path
        if output_path is None:
            output_path = image_path.parent / f"{image_path.stem}_processed.png"
        else:
            output_path = Path(output_path)
            
        output_path.parent.mkdir(parents=True, exist_ok=True)
            
        if not self.is_available():
            return PhotoRoomResult(
                status=ProcessingStatus.AUTH_ERROR,
                success=False,
                input_path=image_path,
                error_message="PhotoRoom API key is missing or invalid.",
                error_code="MISSING_API_KEY",
                is_retryable=False,
                started_at=started_at,
                completed_at=datetime.now(timezone.utc),
            )

        headers = {
            "x-api-key": self._api_key
        }
        
        data = {}
        if bg_color:
            data["bg_color"] = bg_color
        
        # If output_size is specified, PhotoRoom API supports 'size' parameter
        if output_size:
            data["size"] = f"{output_size[0]}x{output_size[1]}"

        try:
            with open(image_path, "rb") as f:
                files = {"image_file": (image_path.name, f, "image/jpeg")}
                
                logger.info(f"Sending request to PhotoRoom API for {image_path.name}")
                # Use a timeout so the thread doesn't hang forever
                response = requests.post(
                    self.API_URL, 
                    headers=headers, 
                    data=data, 
                    files=files,
                    timeout=30.0
                )
                
            if response.status_code == 200:
                # Success - write binary data
                output_path.write_bytes(response.content)
                end_time = time.time()
                
                # Fetch output info
                output_size_bytes = output_path.stat().st_size
                
                # Try to get image dimensions if PIL is available
                width, height = 0, 0
                try:
                    from PIL import Image
                    with Image.open(output_path) as img:
                        width, height = img.size
                except Exception:
                    pass
                
                return PhotoRoomResult(
                    status=ProcessingStatus.SUCCESS,
                    success=True,
                    input_path=image_path,
                    output_path=output_path,
                    output_size_bytes=output_size_bytes,
                    output_width=width,
                    output_height=height,
                    input_size_bytes=image_path.stat().st_size,
                    processing_time_ms=int((end_time - start_time) * 1000),
                    api_credits_used=1, # Real API uses 1 credit per image
                    started_at=started_at,
                    completed_at=datetime.now(timezone.utc),
                )
                
            elif response.status_code == 401 or response.status_code == 403:
                return self._create_error_result(image_path, ProcessingStatus.AUTH_ERROR, "Authentication failed. Check API key.", "AUTH_ERROR", False, started_at)
            elif response.status_code == 429:
                return self._create_error_result(image_path, ProcessingStatus.RATE_LIMITED, "Rate limit exceeded.", "RATE_LIMITED", True, started_at)
            elif response.status_code >= 500:
                return self._create_error_result(image_path, ProcessingStatus.FAILED, f"Server error: {response.text}", "SERVER_ERROR", True, started_at)
            else:
                return self._create_error_result(image_path, ProcessingStatus.INVALID_IMAGE, f"API error {response.status_code}: {response.text}", "API_ERROR", False, started_at)

        except requests.exceptions.Timeout:
            return self._create_error_result(image_path, ProcessingStatus.TIMEOUT, "Request to PhotoRoom API timed out.", "TIMEOUT", True, started_at)
        except requests.exceptions.RequestException as e:
            return self._create_error_result(image_path, ProcessingStatus.FAILED, f"Network error: {str(e)}", "NETWORK_ERROR", True, started_at)
        except Exception as e:
            return self._create_error_result(image_path, ProcessingStatus.FAILED, f"Unexpected error: {str(e)}", "UNKNOWN_ERROR", False, started_at)

    def _create_error_result(self, input_path: Path, status: ProcessingStatus, message: str, code: str, retryable: bool, started_at: datetime) -> PhotoRoomResult:
        logger.error(f"PhotoRoom API error ({code}): {message}")
        return PhotoRoomResult(
            status=status,
            success=False,
            input_path=input_path,
            error_message=message,
            error_code=code,
            is_retryable=retryable,
            started_at=started_at,
            completed_at=datetime.now(timezone.utc),
        )
