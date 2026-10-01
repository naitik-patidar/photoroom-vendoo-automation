"""
Tests for app.ai — AI Command Engine schemas and interpreters.
"""

import pytest
from pydantic import ValidationError

from app.ai.schemas import (
    CommandType,
    ProcessImageCommand,
    BatchProcessCommand,
    CreateListingCommand,
    CheckStatusCommand,
    HelpCommand,
    UnknownCommand,
)
from app.ai.mock_interpreter import MockCommandInterpreter
from app.ai import create_interpreter


# ======================================================================
# Schema Validation Tests
# ======================================================================

class TestSchemas:
    
    def test_process_image_command_valid(self):
        cmd = ProcessImageCommand(
            image_path="/data/shirt.jpg",
            title="Cool Shirt",
            price=25.0
        )
        assert cmd.command_type == CommandType.PROCESS_IMAGE
        assert cmd.image_path == "/data/shirt.jpg"
        assert cmd.price == 25.0

    def test_process_image_requires_path(self):
        with pytest.raises(ValidationError):
            ProcessImageCommand(price=25.0)

    def test_process_image_empty_path_invalid(self):
        with pytest.raises(ValidationError):
            ProcessImageCommand(image_path="   ")

    def test_process_image_negative_price_invalid(self):
        with pytest.raises(ValidationError):
            ProcessImageCommand(image_path="test.jpg", price=-5.0)

    def test_batch_process_command_valid(self):
        cmd = BatchProcessCommand(folder_path="/data/images", recursive=True)
        assert cmd.command_type == CommandType.BATCH_PROCESS
        assert cmd.folder_path == "/data/images"
        assert cmd.recursive is True

    def test_batch_process_empty_folder_invalid(self):
        with pytest.raises(ValidationError):
            BatchProcessCommand(folder_path="")


# ======================================================================
# MockCommandInterpreter Tests
# ======================================================================

class TestMockCommandInterpreter:
    
    @pytest.fixture
    def interpreter(self):
        return MockCommandInterpreter()

    def test_empty_input(self, interpreter):
        res = interpreter.interpret("")
        assert res.command_type == CommandType.UNKNOWN
        assert res.confidence == 0.0

    # -- Help --
    
    def test_help_command(self, interpreter):
        res = interpreter.interpret("How do I use this?")
        assert res.command_type == CommandType.HELP
        assert isinstance(res.command, HelpCommand)
        assert res.command.topic == "general"

    def test_help_topic_batch(self, interpreter):
        res = interpreter.interpret("help with batch processing")
        assert res.command_type == CommandType.HELP
        assert res.command.topic == "batch"

    # -- Status --
    
    def test_status_check(self, interpreter):
        res = interpreter.interpret("check status")
        assert res.command_type == CommandType.CHECK_STATUS
        assert isinstance(res.command, CheckStatusCommand)
        assert res.command.job_id is None
        assert res.command.status_filter is None

    def test_status_check_with_filter(self, interpreter):
        res = interpreter.interpret("show me failed jobs")
        assert res.command_type == CommandType.CHECK_STATUS
        assert res.command.status_filter == "FAILED"

    def test_status_check_with_job_id(self, interpreter):
        job_id = "123e4567-e89b-12d3-a456-426614174000"
        res = interpreter.interpret(f"status for {job_id}")
        assert res.command_type == CommandType.CHECK_STATUS
        assert res.command.job_id == job_id

    # -- Batch Processing --
    
    def test_batch_process(self, interpreter):
        res = interpreter.interpret("batch process /images/shirts")
        assert res.command_type == CommandType.BATCH_PROCESS
        assert isinstance(res.command, BatchProcessCommand)
        assert res.command.folder_path == "/images/shirts"
        assert res.command.recursive is False

    def test_batch_process_recursive(self, interpreter):
        res = interpreter.interpret("process all images in /my/folder recursive")
        assert res.command_type == CommandType.BATCH_PROCESS
        assert res.command.folder_path == "/my/folder"
        assert res.command.recursive is True

    # -- Process Image (Extraction) --
    
    def test_process_image_basic(self, interpreter):
        res = interpreter.interpret("process /images/cool_shirt.jpg")
        assert res.command_type == CommandType.PROCESS_IMAGE
        assert isinstance(res.command, ProcessImageCommand)
        assert res.command.image_path == "/images/cool_shirt.jpg"

    def test_process_image_quotes(self, interpreter):
        res = interpreter.interpret('edit "/path/with spaces/img.png"')
        assert res.command_type == CommandType.PROCESS_IMAGE
        assert res.command.image_path == "/path/with spaces/img.png"

    def test_process_image_price(self, interpreter):
        res = interpreter.interpret("process /img.jpg for $25.99")
        assert res.command_type == CommandType.PROCESS_IMAGE
        assert res.command.price == 25.99

    def test_process_image_condition_color_brand(self, interpreter):
        text = "process ./nike_shoe.png condition excellent color red brand Nike"
        res = interpreter.interpret(text)
        assert res.command_type == CommandType.PROCESS_IMAGE
        assert res.command.condition == "EXCELLENT"
        assert res.command.color == "Red"
        assert res.command.brand.lower() == "nike"
        assert "nike" in res.command.tags
        assert "red" in res.command.tags
        assert "excellent" in res.command.tags

    def test_process_image_size(self, interpreter):
        res = interpreter.interpret("process /img.jpg size XL")
        assert res.command_type == CommandType.PROCESS_IMAGE
        assert res.command.size == "XL"

    def test_process_image_category(self, interpreter):
        res = interpreter.interpret("process /img.jpg it's a shirt")
        assert res.command_type == CommandType.PROCESS_IMAGE
        assert res.command.category == "Clothing"
        assert "clothing" in res.command.tags

    def test_process_image_bg_color(self, interpreter):
        res = interpreter.interpret("process /img.jpg with white background")
        assert res.command_type == CommandType.PROCESS_IMAGE
        assert res.command.bg_color == "#FFFFFF"

        res = interpreter.interpret("process /img.jpg with #FF0000 background")
        assert res.command_type == CommandType.PROCESS_IMAGE
        assert res.command.bg_color == "#FF0000"

    def test_process_image_generates_fallback_title(self, interpreter):
        res = interpreter.interpret("process /data/red_nike_shirt.jpg color red brand Nike")
        assert res.command_type == CommandType.PROCESS_IMAGE
        title = res.command.title
        assert title is not None
        assert "Nike" in title
        assert "Red" in title
        assert "Red Nike Shirt" in title

    # -- Fallbacks --
    
    def test_unknown_command(self, interpreter):
        res = interpreter.interpret("do something completely different")
        assert res.command_type == CommandType.UNKNOWN
        assert isinstance(res.command, UnknownCommand)
        assert res.command.raw_input == "do something completely different"

    def test_process_without_path_is_unknown(self, interpreter):
        res = interpreter.interpret("process this image but I won't tell you the path")
        assert res.command_type == CommandType.UNKNOWN
        assert "Could not find an image path" in res.command.error_message


# ======================================================================
# Factory Tests
# ======================================================================

class TestFactory:
    
    def test_create_mock_interpreter(self):
        interpreter = create_interpreter(mode="mock")
        assert isinstance(interpreter, MockCommandInterpreter)
        
    def test_create_production_interpreter_fallback(self):
        # Even in production mode, we return mock for now because real LLM isn't built yet
        interpreter = create_interpreter(mode="production")
        assert isinstance(interpreter, MockCommandInterpreter)
