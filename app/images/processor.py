"""
Image format conversion and preprocessing.

Handles:
- Format conversion (JPEG ↔ PNG ↔ WebP)
- EXIF-aware rotation (auto-orient)
- RGB normalization (strip alpha when saving JPEG)
- Basic quality/optimization settings
"""

from pathlib import Path
from dataclasses import dataclass

from PIL import Image, ImageOps

from app.logging import get_logger

logger = get_logger("images.processor")


@dataclass
class ConversionResult:
    success: bool
    input_path: Path
    output_path: Path | None = None
    input_format: str = ""
    output_format: str = ""
    input_size: tuple[int, int] = (0, 0)
    output_size: tuple[int, int] = (0, 0)
    error_message: str = ""


def convert_image(
    input_path: Path,
    output_path: Path,
    *,
    quality: int = 95,
    max_dimension: int | None = None,
) -> ConversionResult:
    """
    Convert an image to the format implied by output_path extension.

    Features:
    - EXIF auto-orient (fixes rotated phone photos)
    - Alpha stripping when converting to JPEG
    - Optional max_dimension resize (preserves aspect ratio)
    - Lossless WebP when quality=100

    Args:
        input_path: Source image file.
        output_path: Destination path. Extension determines format.
        quality: JPEG/WebP quality (1-100). Default 95.
        max_dimension: If set, resize so neither dimension exceeds this value.

    Returns:
        ConversionResult with outcome details.
    """
    input_path = Path(input_path)
    output_path = Path(output_path)

    try:
        with Image.open(input_path) as img:
            input_format = img.format or ""
            input_size = img.size

            # Auto-orient based on EXIF
            img = ImageOps.exif_transpose(img)

            # Resize if max_dimension specified
            if max_dimension:
                img.thumbnail(
                    (max_dimension, max_dimension),
                    Image.Resampling.LANCZOS,
                )

            # Determine target format from extension
            target_suffix = output_path.suffix.lower()
            target_format = _suffix_to_pillow_format(target_suffix)

            # Strip alpha for JPEG (not supported)
            if target_format == "JPEG" and img.mode in ("RGBA", "LA", "P"):
                bg = Image.new("RGB", img.size, (255, 255, 255))
                if img.mode == "P":
                    img = img.convert("RGBA")
                bg.paste(img, mask=img.split()[-1] if img.mode in ("RGBA", "LA") else None)
                img = bg
            elif target_format != "JPEG" and img.mode not in ("RGB", "RGBA", "L"):
                img = img.convert("RGBA")

            # Ensure output directory exists
            output_path.parent.mkdir(parents=True, exist_ok=True)

            # Save with format-specific options
            save_kwargs = {"format": target_format}
            if target_format == "JPEG":
                save_kwargs["quality"] = quality
                save_kwargs["optimize"] = True
            elif target_format == "WEBP":
                save_kwargs["quality"] = quality
                save_kwargs["lossless"] = quality == 100
            elif target_format == "PNG":
                save_kwargs["optimize"] = True

            img.save(output_path, **save_kwargs)
            output_size = img.size

        logger.debug(
            f"Converted: {input_path.name} ({input_format}) → "
            f"{output_path.name} ({target_format}) {output_size}"
        )

        return ConversionResult(
            success=True,
            input_path=input_path,
            output_path=output_path,
            input_format=input_format,
            output_format=target_format,
            input_size=input_size,
            output_size=output_size,
        )

    except Exception as e:
        logger.error(f"Conversion failed for {input_path.name}: {e}")
        return ConversionResult(
            success=False,
            input_path=input_path,
            output_path=output_path,
            error_message=str(e),
        )


def get_image_info(image_path: Path) -> dict:
    """
    Return metadata about an image without processing it.

    Returns dict with: format, mode, width, height, file_size_bytes,
    has_transparency, has_exif.
    """
    image_path = Path(image_path)
    with Image.open(image_path) as img:
        exif_data = None
        try:
            exif_data = img._getexif()
        except (AttributeError, Exception):
            pass

        return {
            "format": img.format or "",
            "mode": img.mode,
            "width": img.width,
            "height": img.height,
            "file_size_bytes": image_path.stat().st_size,
            "has_transparency": img.mode in ("RGBA", "LA", "P"),
            "has_exif": exif_data is not None,
        }


def _suffix_to_pillow_format(suffix: str) -> str:
    """Map a file extension to a Pillow format string."""
    mapping = {
        ".jpg": "JPEG",
        ".jpeg": "JPEG",
        ".png": "PNG",
        ".webp": "WEBP",
        ".heic": "HEIF",
    }
    return mapping.get(suffix.lower(), "PNG")
