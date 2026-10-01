"""
Image validation module.

Validates images before processing:
- File existence and permissions
- Format support
- File size limits
- Image integrity (not corrupted)
- Minimum dimensions
"""

from dataclasses import dataclass, field
from pathlib import Path
from enum import Enum

from PIL import Image, UnidentifiedImageError

from app.config.constants import (
    SUPPORTED_INPUT_FORMATS,
    MAX_IMAGE_FILE_SIZE_BYTES,
)
from app.logging import get_logger

logger = get_logger("images.validator")

# Minimum acceptable dimensions
MIN_WIDTH = 50
MIN_HEIGHT = 50


class ValidationStatus(Enum):
    VALID = "valid"
    FILE_NOT_FOUND = "file_not_found"
    NOT_A_FILE = "not_a_file"
    PERMISSION_DENIED = "permission_denied"
    UNSUPPORTED_FORMAT = "unsupported_format"
    FILE_TOO_LARGE = "file_too_large"
    CORRUPTED = "corrupted"
    TOO_SMALL = "too_small"


@dataclass
class ValidationResult:
    """Result of validating a single image file."""

    path: Path
    status: ValidationStatus
    is_valid: bool

    # Populated when valid
    format: str = ""
    width: int = 0
    height: int = 0
    mode: str = ""
    file_size_bytes: int = 0

    # Populated when invalid
    error_message: str = ""

    @property
    def summary(self) -> str:
        if self.is_valid:
            return (
                f"VALID: {self.path.name} "
                f"({self.format}, {self.width}x{self.height}, "
                f"{self.file_size_bytes:,} bytes)"
            )
        return f"INVALID: {self.path.name} — {self.error_message}"


def validate_image(image_path: Path) -> ValidationResult:
    """
    Validate a single image file.

    Checks (in order):
    1. File exists
    2. Is a regular file
    3. Read permission
    4. Extension is supported
    5. File size within limits
    6. Image is not corrupted
    7. Dimensions meet minimums

    Returns:
        ValidationResult describing the outcome.
    """
    image_path = Path(image_path)

    # 1. Exists
    if not image_path.exists():
        return ValidationResult(
            path=image_path,
            status=ValidationStatus.FILE_NOT_FOUND,
            is_valid=False,
            error_message=f"File not found: {image_path}",
        )

    # 2. Is a file
    if not image_path.is_file():
        return ValidationResult(
            path=image_path,
            status=ValidationStatus.NOT_A_FILE,
            is_valid=False,
            error_message=f"Path is not a file: {image_path}",
        )

    # 3. Readable
    try:
        image_path.stat()
    except PermissionError:
        return ValidationResult(
            path=image_path,
            status=ValidationStatus.PERMISSION_DENIED,
            is_valid=False,
            error_message=f"Permission denied: {image_path}",
        )

    # 4. Supported format
    suffix = image_path.suffix.lower()
    if suffix not in SUPPORTED_INPUT_FORMATS:
        return ValidationResult(
            path=image_path,
            status=ValidationStatus.UNSUPPORTED_FORMAT,
            is_valid=False,
            error_message=(
                f"Unsupported format '{suffix}'. "
                f"Supported: {', '.join(sorted(SUPPORTED_INPUT_FORMATS))}"
            ),
        )

    # 5. File size
    file_size = image_path.stat().st_size
    if file_size > MAX_IMAGE_FILE_SIZE_BYTES:
        return ValidationResult(
            path=image_path,
            status=ValidationStatus.FILE_TOO_LARGE,
            is_valid=False,
            file_size_bytes=file_size,
            error_message=(
                f"File too large: {file_size:,} bytes "
                f"(max {MAX_IMAGE_FILE_SIZE_BYTES:,} bytes)"
            ),
        )

    # 6 & 7. Open and inspect the image
    try:
        with Image.open(image_path) as img:
            img.verify()

        # Re-open after verify (verify closes the image)
        with Image.open(image_path) as img:
            img_format = img.format or suffix.lstrip(".")
            width, height = img.size
            mode = img.mode

    except UnidentifiedImageError:
        return ValidationResult(
            path=image_path,
            status=ValidationStatus.CORRUPTED,
            is_valid=False,
            file_size_bytes=file_size,
            error_message="File is not a recognizable image format (possibly corrupted).",
        )
    except Exception as e:
        return ValidationResult(
            path=image_path,
            status=ValidationStatus.CORRUPTED,
            is_valid=False,
            file_size_bytes=file_size,
            error_message=f"Image could not be opened: {e}",
        )

    # 7. Minimum dimensions
    if width < MIN_WIDTH or height < MIN_HEIGHT:
        return ValidationResult(
            path=image_path,
            status=ValidationStatus.TOO_SMALL,
            is_valid=False,
            width=width,
            height=height,
            file_size_bytes=file_size,
            error_message=(
                f"Image too small: {width}x{height} "
                f"(minimum {MIN_WIDTH}x{MIN_HEIGHT})"
            ),
        )

    result = ValidationResult(
        path=image_path,
        status=ValidationStatus.VALID,
        is_valid=True,
        format=img_format.upper(),
        width=width,
        height=height,
        mode=mode,
        file_size_bytes=file_size,
    )
    logger.debug(result.summary)
    return result


def validate_images(image_paths: list[Path]) -> list[ValidationResult]:
    """Validate multiple images. Returns one result per path."""
    results = []
    for path in image_paths:
        results.append(validate_image(path))
    return results


def collect_images_from_folder(
    folder: Path,
    recursive: bool = False,
) -> list[Path]:
    """
    Collect all supported image files from a folder.

    Args:
        folder: Directory to scan.
        recursive: If True, scan subdirectories too.

    Returns:
        Sorted list of image file paths with supported extensions.
    """
    folder = Path(folder)
    if not folder.is_dir():
        raise ValueError(f"Not a directory: {folder}")

    pattern = "**/*" if recursive else "*"
    paths = []
    for suffix in SUPPORTED_INPUT_FORMATS:
        paths.extend(folder.glob(f"{pattern}{suffix}"))
        paths.extend(folder.glob(f"{pattern}{suffix.upper()}"))

    return sorted(set(paths))
