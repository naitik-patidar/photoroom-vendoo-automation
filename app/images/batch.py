"""
Batch image processing foundation.

Handles:
- Discovering images in a folder
- Building a processing queue
- Tracking per-item success/failure independently
- One failed item does NOT abort the batch
"""

from dataclasses import dataclass, field
from pathlib import Path
from enum import Enum

from app.images.validator import validate_image, ValidationResult, ValidationStatus
from app.images.validator import collect_images_from_folder
from app.logging import get_logger

logger = get_logger("images.batch")


class BatchItemStatus(Enum):
    PENDING = "pending"
    VALID = "valid"
    INVALID = "invalid"
    PROCESSING = "processing"
    COMPLETE = "complete"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class BatchItem:
    """A single image in a batch queue."""
    index: int
    path: Path
    status: BatchItemStatus = BatchItemStatus.PENDING
    validation: ValidationResult | None = None
    output_path: Path | None = None
    error_message: str = ""

    @property
    def name(self) -> str:
        return self.path.name

    @property
    def is_ready(self) -> bool:
        return self.status == BatchItemStatus.VALID


@dataclass
class BatchQueue:
    """
    A queue of images to be processed.

    Usage:
        queue = BatchQueue.from_folder(Path("/my/images"))
        queue.validate_all()
        for item in queue.valid_items:
            # process item.path → item.output_path
            queue.mark_complete(item.index, output_path)
    """

    items: list[BatchItem] = field(default_factory=list)
    source_folder: Path | None = None

    @classmethod
    def from_paths(cls, paths: list[Path]) -> "BatchQueue":
        """Create a queue from an explicit list of paths."""
        items = [
            BatchItem(index=i, path=Path(p))
            for i, p in enumerate(paths)
        ]
        return cls(items=items)

    @classmethod
    def from_folder(
        cls,
        folder: Path,
        recursive: bool = False,
    ) -> "BatchQueue":
        """Create a queue by scanning a folder for images."""
        folder = Path(folder)
        paths = collect_images_from_folder(folder, recursive=recursive)
        queue = cls.from_paths(paths)
        queue.source_folder = folder
        logger.info(f"Batch queue created from '{folder}': {len(paths)} images")
        return queue

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------

    def validate_all(self) -> None:
        """Validate every item. Updates each item's status in place."""
        for item in self.items:
            result = validate_image(item.path)
            item.validation = result
            if result.is_valid:
                item.status = BatchItemStatus.VALID
            else:
                item.status = BatchItemStatus.INVALID
                item.error_message = result.error_message

        valid = self.valid_count
        invalid = self.invalid_count
        logger.info(
            f"Validation complete: {valid} valid, {invalid} invalid "
            f"(total: {len(self.items)})"
        )

    # ------------------------------------------------------------------
    # Status updates
    # ------------------------------------------------------------------

    def mark_processing(self, index: int) -> None:
        self._get(index).status = BatchItemStatus.PROCESSING

    def mark_complete(self, index: int, output_path: Path) -> None:
        item = self._get(index)
        item.status = BatchItemStatus.COMPLETE
        item.output_path = output_path

    def mark_failed(self, index: int, error_message: str) -> None:
        item = self._get(index)
        item.status = BatchItemStatus.FAILED
        item.error_message = error_message

    def mark_skipped(self, index: int, reason: str = "") -> None:
        item = self._get(index)
        item.status = BatchItemStatus.SKIPPED
        item.error_message = reason

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    @property
    def valid_items(self) -> list[BatchItem]:
        return [i for i in self.items if i.status == BatchItemStatus.VALID]

    @property
    def failed_items(self) -> list[BatchItem]:
        return [i for i in self.items if i.status == BatchItemStatus.FAILED]

    @property
    def complete_items(self) -> list[BatchItem]:
        return [i for i in self.items if i.status == BatchItemStatus.COMPLETE]

    @property
    def invalid_items(self) -> list[BatchItem]:
        return [i for i in self.items if i.status == BatchItemStatus.INVALID]

    @property
    def valid_count(self) -> int:
        return len(self.valid_items)

    @property
    def invalid_count(self) -> int:
        return len(self.invalid_items)

    @property
    def complete_count(self) -> int:
        return len(self.complete_items)

    @property
    def failed_count(self) -> int:
        return len(self.failed_items)

    @property
    def total_count(self) -> int:
        return len(self.items)

    @property
    def is_empty(self) -> bool:
        return len(self.items) == 0

    def summary(self) -> str:
        return (
            f"Batch({self.total_count} total | "
            f"{self.valid_count} valid | "
            f"{self.complete_count} done | "
            f"{self.failed_count} failed | "
            f"{self.invalid_count} invalid)"
        )

    def _get(self, index: int) -> BatchItem:
        for item in self.items:
            if item.index == index:
                return item
        raise KeyError(f"No batch item with index {index}")
