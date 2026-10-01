"""
Background threads for running workflow tasks without blocking the PySide6 UI.
"""

from typing import List
from PySide6.QtCore import QThread, Signal
from app.workflow.orchestrator import WorkflowOrchestrator
from app.workflow.status import WorkflowStatus
from app.ai.schemas import CommandType, ProcessImageCommand, BatchProcessCommand


class WorkflowWorkerThread(QThread):
    """
    QThread for running orchestrator tasks.
    """
    
    # Signals
    log_message = Signal(str)
    job_completed = Signal(WorkflowStatus)
    job_failed = Signal(str, str) # job_id, error_message
    batch_completed = Signal(list) # list of WorkflowStatus
    
    def __init__(self, orchestrator: WorkflowOrchestrator, intent_type: CommandType, command, job_ids: List[str] = None):
        super().__init__()
        self.orchestrator = orchestrator
        self.intent_type = intent_type
        self.command = command
        self.job_ids = job_ids or []

    def run(self):
        """Execute the workflow in the background thread."""
        try:
            if self.intent_type == CommandType.PROCESS_IMAGE:
                self.log_message.emit(f"Starting job {self.job_ids[0]}...")
                status = self.orchestrator.run(self.job_ids[0], self.command)
                
                if status.state.value == "completed":
                    self.log_message.emit(f"Job {self.job_ids[0]} completed successfully.")
                    self.job_completed.emit(status)
                else:
                    err = status.error_message or "Unknown error"
                    self.log_message.emit(f"Job {self.job_ids[0]} failed: {err}")
                    self.job_failed.emit(self.job_ids[0], err)
                    
            elif self.intent_type == CommandType.BATCH_PROCESS:
                self.log_message.emit(f"Starting batch of {len(self.job_ids)} jobs...")
                # We can construct a shared ProcessImageCommand for the batch
                shared_cmd = ProcessImageCommand(
                    image_path="dummy",
                    brand=self.command.brand,
                    condition=self.command.condition
                )
                results = self.orchestrator.run_batch(self.job_ids, shared_cmd)
                
                success_count = sum(1 for r in results if r.state.value == "completed")
                self.log_message.emit(f"Batch completed: {success_count}/{len(self.job_ids)} successful.")
                self.batch_completed.emit(results)
                
        except Exception as e:
            self.log_message.emit(f"Exception in workflow thread: {e}")
