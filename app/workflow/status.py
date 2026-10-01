"""
Workflow status tracker — in-memory summary of a running workflow.

Separate from DB status so the UI can observe progress
without polling the database on every update.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum


class WorkflowState(Enum):
    IDLE = "idle"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class WorkflowStatus:
    """
    Real-time status snapshot of a workflow run.

    Used by the UI to display progress.
    """
    job_id: str
    state: WorkflowState = WorkflowState.IDLE
    current_step: str = ""
    steps_completed: list[str] = field(default_factory=list)
    steps_failed: list[str] = field(default_factory=list)
    started_at: datetime | None = None
    completed_at: datetime | None = None
    error_message: str = ""

    # File paths
    original_file: str = ""
    processed_file: str = ""

    def start(self, step_name: str) -> None:
        if self.state == WorkflowState.IDLE:
            self.state = WorkflowState.RUNNING
            self.started_at = datetime.now(timezone.utc)
        self.current_step = step_name

    def complete_step(self, step_name: str) -> None:
        self.steps_completed.append(step_name)
        self.current_step = ""

    def fail_step(self, step_name: str, error: str) -> None:
        self.steps_failed.append(step_name)
        self.error_message = error
        self.current_step = ""

    def finish(self) -> None:
        self.state = WorkflowState.COMPLETED
        self.completed_at = datetime.now(timezone.utc)

    def fail(self, error: str) -> None:
        self.state = WorkflowState.FAILED
        self.error_message = error
        self.completed_at = datetime.now(timezone.utc)

    @property
    def elapsed_seconds(self) -> float | None:
        if not self.started_at:
            return None
        end = self.completed_at or datetime.now(timezone.utc)
        return (end - self.started_at).total_seconds()

    def summary(self) -> str:
        elapsed = f"{self.elapsed_seconds:.1f}s" if self.elapsed_seconds else "?"
        return (
            f"Job {self.job_id[:8]} | {self.state.value} | "
            f"step={self.current_step!r} | "
            f"done={self.steps_completed} | "
            f"elapsed={elapsed}"
        )
