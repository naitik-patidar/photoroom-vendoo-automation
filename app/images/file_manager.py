"""
Image file manager — safe naming, original preservation, output path resolution.

Rules enforced here:
- Original images are NEVER overwritten
- Output files are always distinct from inputs
- Naming convention: {stem}_original.{ext} and {stem}_processed.png
- Output directories are created as needed
"""

import shutil
from pathlib import Path

from app.config.constants import ORIGINAL_SUFFIX, PROCESSED_SUFFIX, DEFAULT_OUTPUT_FORMAT
from app.logging import get_logger

logger = get_logger("images.file_manager")


def build_original_copy_path(image_path: Path, output_dir: Path) -> Path:
    """
    Build a path for preserving a copy of the original image.

    Example:
        input:  /some/dir/shirt.jpg
        output: /output_dir/shirt_original.jpg
    """
    stem = image_path.stem
    suffix = image_path.suffix
    return output_dir / f"{stem}{ORIGINAL_SUFFIX}{suffix}"


def build_processed_path(image_path: Path, output_dir: Path) -> Path:
    """
    Build a path for the processed (background-removed) image.

    Always outputs as PNG (to support transparency).

    Example:
        input:  /some/dir/shirt.jpg
        output: /output_dir/shirt_processed.png
    """
    stem = image_path.stem
    return output_dir / f"{stem}{PROCESSED_SUFFIX}{DEFAULT_OUTPUT_FORMAT}"


def ensure_output_dir(output_dir: Path) -> Path:
    """Create the output directory (and parents) if it doesn't exist."""
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    return output_dir


def preserve_original(image_path: Path, output_dir: Path) -> Path:
    """
    Copy the original image to the output directory.

    The original is NEVER modified. This copy is for archival.

    Returns:
        Path to the preserved copy.
    """
    image_path = Path(image_path)
    output_dir = ensure_output_dir(output_dir)

    dest = build_original_copy_path(image_path, output_dir)
    shutil.copy2(image_path, dest)
    logger.debug(f"Original preserved: {image_path.name} → {dest.name}")
    return dest


def is_safe_output_path(input_path: Path, output_path: Path) -> bool:
    """
    Verify that the output path is not the same file as the input.

    Returns True if it's safe to write to output_path.
    """
    try:
        return input_path.resolve() != output_path.resolve()
    except Exception:
        return input_path != output_path


def safe_delete(path: Path) -> bool:
    """
    Delete a file safely (non-fatal if it doesn't exist).

    Returns True if deleted, False if not found.
    """
    try:
        path.unlink()
        logger.debug(f"Deleted: {path}")
        return True
    except FileNotFoundError:
        return False
    except Exception as e:
        logger.warning(f"Could not delete {path}: {e}")
        return False
