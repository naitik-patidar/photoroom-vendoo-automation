"""
Workflow step definitions.

Each step is a pure function that:
- Takes the current job + dependencies
- Does ONE unit of work
- Returns a StepResult
- NEVER updates the database itself (the orchestrator does that)

This keeps steps testable in isolation.
"""

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path


class StepStatus(Enum):
    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class StepResult:
    """Outcome of a single workflow step."""
    step_name: str
    status: StepStatus
    success: bool

    # Outputs to carry forward
    output_path: Path | None = None
    product_id: str | None = None

    # Error info
    error_message: str = ""
    is_retryable: bool = False

    @property
    def failed(self) -> bool:
        return self.status == StepStatus.FAILED
