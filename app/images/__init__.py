"""Images package — image validation, processing, file management, and batching."""

from app.images.validator import (
    validate_image,
    validate_images,
    collect_images_from_folder,
    ValidationResult,
    ValidationStatus,
)
from app.images.file_manager import (
    build_original_copy_path,
    build_processed_path,
    ensure_output_dir,
    preserve_original,
    is_safe_output_path,
)
from app.images.processor import convert_image, get_image_info, ConversionResult
from app.images.batch import BatchQueue, BatchItem, BatchItemStatus

__all__ = [
    "validate_image",
    "validate_images",
    "collect_images_from_folder",
    "ValidationResult",
    "ValidationStatus",
    "build_original_copy_path",
    "build_processed_path",
    "ensure_output_dir",
    "preserve_original",
    "is_safe_output_path",
    "convert_image",
    "get_image_info",
    "ConversionResult",
    "BatchQueue",
    "BatchItem",
    "BatchItemStatus",
]
