"""
Tests for app.images — validator, file_manager, processor, batch.
"""

import shutil
from pathlib import Path

import pytest
from PIL import Image

from app.images.validator import (
    validate_image,
    validate_images,
    collect_images_from_folder,
    ValidationResult,
    ValidationStatus,
    MIN_WIDTH,
    MIN_HEIGHT,
)
from app.images.file_manager import (
    build_original_copy_path,
    build_processed_path,
    preserve_original,
    ensure_output_dir,
    is_safe_output_path,
    safe_delete,
)
from app.images.processor import convert_image, get_image_info, ConversionResult
from app.images.batch import BatchQueue, BatchItem, BatchItemStatus


# ======================================================================
# Helpers
# ======================================================================

def make_image(path: Path, size=(100, 100), color=(255, 0, 0), mode="RGB") -> Path:
    img = Image.new(mode, size, color=color)
    img.save(path)
    return path


# ======================================================================
# Validator tests
# ======================================================================

class TestValidateImage:

    def test_valid_png(self, tmp_path):
        path = make_image(tmp_path / "img.png")
        result = validate_image(path)
        assert result.is_valid is True
        assert result.status == ValidationStatus.VALID
        assert result.width == 100
        assert result.height == 100
        assert result.file_size_bytes > 0
        assert result.format == "PNG"

    def test_valid_jpg(self, tmp_path):
        path = make_image(tmp_path / "img.jpg")
        result = validate_image(path)
        assert result.is_valid is True
        assert result.format == "JPEG"

    def test_valid_webp(self, tmp_path):
        img = Image.new("RGB", (100, 100), color=(10, 20, 30))
        path = tmp_path / "img.webp"
        img.save(path, "WEBP")
        result = validate_image(path)
        assert result.is_valid is True

    def test_file_not_found(self, tmp_path):
        result = validate_image(tmp_path / "missing.png")
        assert result.is_valid is False
        assert result.status == ValidationStatus.FILE_NOT_FOUND
        assert "not found" in result.error_message.lower()

    def test_not_a_file(self, tmp_path):
        folder = tmp_path / "a_folder"
        folder.mkdir()
        result = validate_image(folder)
        assert result.is_valid is False
        assert result.status == ValidationStatus.NOT_A_FILE

    def test_unsupported_format(self, tmp_path):
        bad = tmp_path / "doc.pdf"
        bad.write_bytes(b"fake pdf")
        result = validate_image(bad)
        assert result.is_valid is False
        assert result.status == ValidationStatus.UNSUPPORTED_FORMAT
        assert ".pdf" in result.error_message

    def test_corrupted_image(self, tmp_path):
        corrupt = tmp_path / "bad.png"
        corrupt.write_bytes(b"this is not an image")
        result = validate_image(corrupt)
        assert result.is_valid is False
        assert result.status == ValidationStatus.CORRUPTED

    def test_too_small(self, tmp_path):
        path = make_image(tmp_path / "tiny.png", size=(10, 10))
        result = validate_image(path)
        assert result.is_valid is False
        assert result.status == ValidationStatus.TOO_SMALL
        assert "10x10" in result.error_message

    def test_file_too_large(self, tmp_path):
        import app.images.validator as v_module
        original = v_module.MAX_IMAGE_FILE_SIZE_BYTES
        v_module.MAX_IMAGE_FILE_SIZE_BYTES = 5
        try:
            path = make_image(tmp_path / "large.png")
            result = validate_image(path)
            assert result.is_valid is False
            assert result.status == ValidationStatus.FILE_TOO_LARGE
        finally:
            v_module.MAX_IMAGE_FILE_SIZE_BYTES = original

    def test_summary_valid(self, tmp_path):
        path = make_image(tmp_path / "img.png")
        result = validate_image(path)
        assert "VALID" in result.summary
        assert "img.png" in result.summary

    def test_summary_invalid(self, tmp_path):
        result = validate_image(tmp_path / "missing.png")
        assert "INVALID" in result.summary

    def test_validate_images_multiple(self, tmp_path):
        paths = [
            make_image(tmp_path / "a.png"),
            make_image(tmp_path / "b.png"),
            tmp_path / "missing.png",
        ]
        results = validate_images(paths)
        assert len(results) == 3
        assert results[0].is_valid is True
        assert results[1].is_valid is True
        assert results[2].is_valid is False


class TestCollectImagesFromFolder:

    def test_collects_supported_formats(self, tmp_path):
        make_image(tmp_path / "a.png")
        make_image(tmp_path / "b.jpg")
        (tmp_path / "c.txt").write_text("not an image")

        paths = collect_images_from_folder(tmp_path)
        names = {p.name for p in paths}
        assert "a.png" in names
        assert "b.jpg" in names
        assert "c.txt" not in names

    def test_non_recursive_skips_subdirs(self, tmp_path):
        sub = tmp_path / "sub"
        sub.mkdir()
        make_image(sub / "inner.png")
        make_image(tmp_path / "outer.png")

        paths = collect_images_from_folder(tmp_path, recursive=False)
        names = {p.name for p in paths}
        assert "outer.png" in names
        assert "inner.png" not in names

    def test_recursive_includes_subdirs(self, tmp_path):
        sub = tmp_path / "sub"
        sub.mkdir()
        make_image(sub / "inner.png")
        make_image(tmp_path / "outer.png")

        paths = collect_images_from_folder(tmp_path, recursive=True)
        names = {p.name for p in paths}
        assert "outer.png" in names
        assert "inner.png" in names

    def test_raises_on_non_directory(self, tmp_path):
        file = tmp_path / "notadir.txt"
        file.write_text("x")
        with pytest.raises(ValueError, match="Not a directory"):
            collect_images_from_folder(file)

    def test_empty_folder(self, tmp_path):
        paths = collect_images_from_folder(tmp_path)
        assert paths == []


# ======================================================================
# File manager tests
# ======================================================================

class TestFileManager:

    def test_build_original_copy_path(self, tmp_path):
        src = tmp_path / "shirt.jpg"
        out_dir = tmp_path / "out"
        result = build_original_copy_path(src, out_dir)
        assert result == out_dir / "shirt_original.jpg"

    def test_build_processed_path(self, tmp_path):
        src = tmp_path / "shirt.jpg"
        out_dir = tmp_path / "out"
        result = build_processed_path(src, out_dir)
        assert result == out_dir / "shirt_processed.png"
        assert result.suffix == ".png"

    def test_preserve_original_copies_file(self, tmp_path):
        src = make_image(tmp_path / "shirt.png")
        out_dir = tmp_path / "output"

        dest = preserve_original(src, out_dir)

        assert dest.exists()
        assert dest.read_bytes() == src.read_bytes()
        assert dest.name == "shirt_original.png"

    def test_preserve_original_does_not_delete_source(self, tmp_path):
        src = make_image(tmp_path / "shirt.png")
        preserve_original(src, tmp_path / "output")
        assert src.exists()

    def test_ensure_output_dir_creates(self, tmp_path):
        new_dir = tmp_path / "deep" / "nested"
        ensure_output_dir(new_dir)
        assert new_dir.is_dir()

    def test_is_safe_output_path_different(self, tmp_path):
        src = tmp_path / "input.png"
        dst = tmp_path / "output.png"
        assert is_safe_output_path(src, dst) is True

    def test_is_safe_output_path_same(self, tmp_path):
        src = tmp_path / "input.png"
        assert is_safe_output_path(src, src) is False

    def test_safe_delete_existing(self, tmp_path):
        f = tmp_path / "to_delete.txt"
        f.write_text("x")
        result = safe_delete(f)
        assert result is True
        assert not f.exists()

    def test_safe_delete_missing(self, tmp_path):
        result = safe_delete(tmp_path / "nonexistent.txt")
        assert result is False


# ======================================================================
# Processor tests
# ======================================================================

class TestConvertImage:

    def test_png_to_jpg(self, tmp_path):
        src = make_image(tmp_path / "in.png", mode="RGB")
        dst = tmp_path / "out.jpg"
        result = convert_image(src, dst)
        assert result.success is True
        assert dst.exists()
        with Image.open(dst) as img:
            assert img.format == "JPEG"

    def test_jpg_to_png(self, tmp_path):
        src = make_image(tmp_path / "in.jpg")
        dst = tmp_path / "out.png"
        result = convert_image(src, dst)
        assert result.success is True
        with Image.open(dst) as img:
            assert img.format == "PNG"

    def test_png_to_webp(self, tmp_path):
        src = make_image(tmp_path / "in.png")
        dst = tmp_path / "out.webp"
        result = convert_image(src, dst)
        assert result.success is True

    def test_rgba_to_jpg_strips_alpha(self, tmp_path):
        src = tmp_path / "in.png"
        img = Image.new("RGBA", (100, 100), (255, 0, 0, 128))
        img.save(src)
        dst = tmp_path / "out.jpg"
        result = convert_image(src, dst)
        assert result.success is True
        with Image.open(dst) as out:
            assert out.mode == "RGB"

    def test_max_dimension_resize(self, tmp_path):
        src = make_image(tmp_path / "in.png", size=(400, 300))
        dst = tmp_path / "out.png"
        result = convert_image(src, dst, max_dimension=200)
        assert result.success is True
        assert result.output_size[0] <= 200
        assert result.output_size[1] <= 200

    def test_output_dir_created(self, tmp_path):
        src = make_image(tmp_path / "in.png")
        dst = tmp_path / "new" / "sub" / "out.png"
        result = convert_image(src, dst)
        assert result.success is True
        assert dst.exists()

    def test_metadata_populated(self, tmp_path):
        src = make_image(tmp_path / "in.jpg", size=(80, 60))
        dst = tmp_path / "out.png"
        result = convert_image(src, dst)
        assert result.input_path == src
        assert result.output_path == dst
        assert result.input_size == (80, 60)
        assert result.input_format == "JPEG"
        assert result.output_format == "PNG"


class TestGetImageInfo:

    def test_returns_metadata(self, tmp_path):
        path = make_image(tmp_path / "img.png", size=(120, 90))
        info = get_image_info(path)
        assert info["format"] == "PNG"
        assert info["width"] == 120
        assert info["height"] == 90
        assert info["file_size_bytes"] > 0
        assert info["has_transparency"] is False

    def test_detects_transparency(self, tmp_path):
        img = Image.new("RGBA", (100, 100), (255, 0, 0, 128))
        path = tmp_path / "img.png"
        img.save(path)
        info = get_image_info(path)
        assert info["has_transparency"] is True


# ======================================================================
# Batch queue tests
# ======================================================================

class TestBatchQueue:

    def test_from_paths(self, tmp_path):
        paths = [make_image(tmp_path / f"img{i}.png") for i in range(3)]
        queue = BatchQueue.from_paths(paths)
        assert queue.total_count == 3

    def test_from_folder(self, sample_images_dir):
        queue = BatchQueue.from_folder(sample_images_dir)
        assert queue.total_count == 3
        assert queue.source_folder == sample_images_dir

    def test_from_empty_folder(self, tmp_path):
        queue = BatchQueue.from_folder(tmp_path)
        assert queue.is_empty is True
        assert queue.total_count == 0

    def test_validate_all_marks_valid(self, sample_images_dir):
        queue = BatchQueue.from_folder(sample_images_dir)
        queue.validate_all()
        assert queue.valid_count == 3
        assert queue.invalid_count == 0

    def test_validate_marks_invalid(self, tmp_path):
        good = make_image(tmp_path / "good.png")
        bad = tmp_path / "bad.png"
        bad.write_bytes(b"not an image")

        queue = BatchQueue.from_paths([good, bad])
        queue.validate_all()
        assert queue.valid_count == 1
        assert queue.invalid_count == 1

    def test_invalid_does_not_abort_batch(self, tmp_path):
        """A single invalid item should not affect others."""
        paths = [make_image(tmp_path / f"img{i}.png") for i in range(3)]
        bad = tmp_path / "corrupt.png"
        bad.write_bytes(b"nope")
        all_paths = paths + [bad]

        queue = BatchQueue.from_paths(all_paths)
        queue.validate_all()

        assert queue.valid_count == 3
        assert queue.invalid_count == 1

    def test_mark_complete(self, sample_images_dir, tmp_path):
        queue = BatchQueue.from_folder(sample_images_dir)
        queue.validate_all()
        item = queue.valid_items[0]

        output = tmp_path / "done.png"
        queue.mark_complete(item.index, output)

        assert queue.complete_count == 1
        assert queue.complete_items[0].output_path == output

    def test_mark_failed(self, sample_images_dir):
        queue = BatchQueue.from_folder(sample_images_dir)
        queue.validate_all()
        item = queue.valid_items[0]

        queue.mark_failed(item.index, "some error")

        assert queue.failed_count == 1
        assert queue.failed_items[0].error_message == "some error"

    def test_mark_skipped(self, sample_images_dir):
        queue = BatchQueue.from_folder(sample_images_dir)
        queue.validate_all()
        item = queue.valid_items[0]

        queue.mark_skipped(item.index, "duplicate")

        skipped = [i for i in queue.items if i.status == BatchItemStatus.SKIPPED]
        assert len(skipped) == 1

    def test_summary_string(self, sample_images_dir):
        queue = BatchQueue.from_folder(sample_images_dir)
        queue.validate_all()
        summary = queue.summary()
        assert "3 total" in summary
        assert "3 valid" in summary

    def test_from_recursive_folder(self, tmp_path):
        sub = tmp_path / "sub"
        sub.mkdir()
        make_image(tmp_path / "a.png")
        make_image(sub / "b.png")

        queue = BatchQueue.from_folder(tmp_path, recursive=True)
        assert queue.total_count == 2
