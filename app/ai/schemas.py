"""
AI Command Schemas — Pydantic models for structured commands.

The AI interprets natural language instructions and produces one of these
structured command objects. The workflow engine then executes the command.

Example flow:
    User: "Process the blue shirt photo and list it for $25"
    AI → ProcessImageCommand(image_path="blue_shirt.jpg", price=25.0, ...)
    Orchestrator → run(job_id)

Rules:
- AI must NEVER invent price, condition, SKU, or brand (user-supplied only)
- AI CAN generate title, description, tags, category from image context
- All commands are validated by Pydantic before execution
"""

from enum import Enum
from pathlib import Path
from pydantic import BaseModel, Field, field_validator
from typing import Optional


class CommandType(str, Enum):
    """Types of commands the AI can produce."""
    PROCESS_IMAGE = "process_image"
    BATCH_PROCESS = "batch_process"
    CREATE_LISTING = "create_listing"
    UPDATE_LISTING = "update_listing"
    CHECK_STATUS = "check_status"
    RETRY = "retry"
    HELP = "help"
    UNKNOWN = "unknown"


class ProcessImageCommand(BaseModel):
    """Command to process a single product image."""
    command_type: CommandType = CommandType.PROCESS_IMAGE
    image_path: str = Field(..., description="Path to the image file")

    # Optional listing data (user-supplied or AI-generated)
    title: Optional[str] = Field(None, description="Product title")
    description: Optional[str] = Field(None, description="Product description")
    category: Optional[str] = Field(None, description="Product category")
    subcategory: Optional[str] = Field(None, description="Subcategory")
    brand: Optional[str] = Field(None, description="Brand (user-supplied only)")
    size: Optional[str] = Field(None, description="Size")
    color: Optional[str] = Field(None, description="Color")
    material: Optional[str] = Field(None, description="Material")
    condition: Optional[str] = Field(None, description="Condition (user-supplied only)")
    price: Optional[float] = Field(None, ge=0, description="Price (user-supplied only)")
    tags: list[str] = Field(default_factory=list, description="Search tags")

    # Processing options
    bg_color: Optional[str] = Field(None, description="Background color hex, e.g. #FFFFFF")
    sandbox: bool = Field(False, description="Use PhotoRoom sandbox mode")

    @field_validator("image_path")
    @classmethod
    def validate_image_path(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("image_path cannot be empty")
        return v.strip()


class BatchProcessCommand(BaseModel):
    """Command to process all images in a folder."""
    command_type: CommandType = CommandType.BATCH_PROCESS
    folder_path: str = Field(..., description="Path to folder containing images")
    recursive: bool = Field(False, description="Include subdirectories")

    # Shared listing data (applies to all items if provided)
    category: Optional[str] = None
    brand: Optional[str] = None
    condition: Optional[str] = None

    @field_validator("folder_path")
    @classmethod
    def validate_folder_path(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("folder_path cannot be empty")
        return v.strip()


class CreateListingCommand(BaseModel):
    """Command to create a listing for an already-processed image."""
    command_type: CommandType = CommandType.CREATE_LISTING
    job_id: Optional[str] = Field(None, description="Job ID to create listing for")
    image_path: Optional[str] = Field(None, description="Path to processed image")

    title: Optional[str] = None
    description: Optional[str] = None
    category: Optional[str] = None
    brand: Optional[str] = None
    condition: Optional[str] = None
    price: Optional[float] = Field(None, ge=0)
    tags: list[str] = Field(default_factory=list)


class CheckStatusCommand(BaseModel):
    """Command to check the status of jobs."""
    command_type: CommandType = CommandType.CHECK_STATUS
    job_id: Optional[str] = Field(None, description="Specific job ID, or None for all")
    status_filter: Optional[str] = Field(None, description="Filter by status")


class RetryCommand(BaseModel):
    """Command to retry failed jobs."""
    command_type: CommandType = CommandType.RETRY
    job_id: Optional[str] = Field(None, description="Specific job ID to retry, or None for all retryable")


class HelpCommand(BaseModel):
    """Command requesting help or information."""
    command_type: CommandType = CommandType.HELP
    topic: str = Field("general", description="Help topic")


class UnknownCommand(BaseModel):
    """Fallback when the AI cannot interpret the instruction."""
    command_type: CommandType = CommandType.UNKNOWN
    raw_input: str = Field("", description="The original user input")
    error_message: str = Field(
        "Could not understand the instruction. Try something like: "
        "'Process the image at /path/to/photo.jpg' or "
        "'Process all images in /path/to/folder'"
    )


class CommandResult(BaseModel):
    """
    Wrapper returned by the CommandInterpreter.

    Contains the parsed command, confidence score, and any interpretation notes.
    """
    command_type: CommandType
    command: ProcessImageCommand | BatchProcessCommand | CreateListingCommand | CheckStatusCommand | RetryCommand | HelpCommand | UnknownCommand
    confidence: float = Field(1.0, ge=0.0, le=1.0, description="Interpretation confidence")
    interpretation_note: str = Field("", description="How the AI interpreted the input")
    raw_input: str = Field("", description="The original user text")
