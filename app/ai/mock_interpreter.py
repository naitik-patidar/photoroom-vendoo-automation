"""
MockCommandInterpreter — Pattern-matching command parser.

Parses user instructions using regex and keyword matching.
No API calls, no LLM — deterministic and fast.

Supports:
- "process [image_path]" → ProcessImageCommand
- "process all in [folder]" / "batch [folder]" → BatchProcessCommand
- "status" / "check status" → CheckStatusCommand
- "help" → HelpCommand
- Extracts price ($25, $19.99), condition, color, brand from text
- Falls back to UnknownCommand if nothing matches
"""

import re
from pathlib import Path

from app.ai.command_interpreter import CommandInterpreter
from app.ai.schemas import (
    CommandType,
    CommandResult,
    ProcessImageCommand,
    BatchProcessCommand,
    CreateListingCommand,
    CheckStatusCommand,
    RetryCommand,
    HelpCommand,
    UnknownCommand,
)
from app.logging import get_logger

logger = get_logger("ai.mock_interpreter")

# ---------------------------------------------------------------------------
# Regex patterns
# ---------------------------------------------------------------------------

# Matches file paths: /path/to/file.jpg, ./file.png, C:\path\file.jpg, "/path with space.jpg"
PATH_PATTERN = re.compile(
    r"""(['"])(.+?\.(?:jpg|jpeg|png|webp|heic))\1"""  # Group 2: quoted path (allows spaces)
    r"""|"""
    r"""((?:[A-Za-z]:[/\\])?[./\\~]?[\w/\\.-]+\.(?:jpg|jpeg|png|webp|heic))""",  # Group 3: unquoted path (no spaces)
    re.IGNORECASE | re.VERBOSE,
)

# Matches folder paths (no extension)
FOLDER_PATTERN = re.compile(
    r"""(?:['"]?)
        (
            (?:[A-Za-z]:[/\\])?
            (?:[./\\~])?
            [^\s'",:]+[/\\][^\s'",.]+
        )
        (?:['"]?)
    """,
    re.IGNORECASE | re.VERBOSE,
)

# Matches price: $25, $19.99, 25.00
PRICE_PATTERN = re.compile(r"\$\s*(\d+(?:\.\d{1,2})?)")

# Matches condition keywords
CONDITION_PATTERN = re.compile(
    r"\b(new|like new|excellent|good|fair|poor|nwt|nwot|euc|guc|used)\b",
    re.IGNORECASE,
)

# Matches common color names
COLOR_PATTERN = re.compile(
    r"\b(red|blue|green|black|white|gray|grey|navy|pink|purple|"
    r"yellow|orange|brown|beige|cream|teal|maroon|olive|gold|silver)\b",
    re.IGNORECASE,
)

# Matches common brand names (expandable)
BRAND_PATTERN = re.compile(
    r"\b(nike|adidas|puma|gucci|prada|zara|h&m|levi'?s|gap|coach|"
    r"louis vuitton|ralph lauren|tommy hilfiger|calvin klein|"
    r"under armour|new balance|converse|vans|reebok|supreme)\b",
    re.IGNORECASE,
)

# Matches size
SIZE_PATTERN = re.compile(
    r"\bsize\s+(xs|s|m|l|xl|xxl|2xl|3xl|\d{1,2})\b",
    re.IGNORECASE,
)

# Common category keywords
CATEGORY_MAP = {
    "shirt": "Clothing",
    "tshirt": "Clothing",
    "t-shirt": "Clothing",
    "pants": "Clothing",
    "jeans": "Clothing",
    "jacket": "Clothing",
    "dress": "Clothing",
    "skirt": "Clothing",
    "shoes": "Shoes",
    "sneakers": "Shoes",
    "boots": "Shoes",
    "bag": "Bags & Accessories",
    "purse": "Bags & Accessories",
    "handbag": "Bags & Accessories",
    "wallet": "Bags & Accessories",
    "watch": "Accessories",
    "jewelry": "Accessories",
    "hat": "Accessories",
    "sunglasses": "Accessories",
    "electronics": "Electronics",
    "phone": "Electronics",
    "laptop": "Electronics",
    "toy": "Toys & Games",
    "book": "Books",
    "home": "Home & Garden",
    "decor": "Home & Garden",
}


class MockCommandInterpreter(CommandInterpreter):
    """
    Pattern-matching command interpreter — no LLM required.

    Deterministic parsing using regex and keyword extraction.
    Designed to be good enough for development and testing,
    while the real LLM interpreter is built in a future task.
    """

    def __init__(self):
        logger.info("MockCommandInterpreter initialized")

    def interpret(self, user_input: str) -> CommandResult:
        """Parse a natural language instruction into a structured command."""
        if not user_input or not user_input.strip():
            return self._unknown("", "Empty input")

        text = user_input.strip()
        lower = text.lower()

        # Help
        if self._is_help(lower):
            return self._make_result(
                CommandType.HELP,
                HelpCommand(topic=self._extract_help_topic(lower)),
                text, 0.95, "Interpreted as help request",
            )

        # Status check
        if self._is_status_check(lower):
            return self._make_result(
                CommandType.CHECK_STATUS,
                CheckStatusCommand(
                    job_id=self._extract_job_id(text),
                    status_filter=self._extract_status_filter(lower),
                ),
                text, 0.90, "Interpreted as status check",
            )

        # Batch process
        if self._is_batch(lower):
            folder = self._extract_folder(text)
            if folder:
                return self._make_result(
                    CommandType.BATCH_PROCESS,
                    BatchProcessCommand(
                        folder_path=folder,
                        recursive="recursive" in lower or "all subfolders" in lower,
                        category=self._extract_category(lower),
                        brand=self._extract_brand(text),
                        condition=self._extract_condition(lower),
                    ),
                    text, 0.85, f"Batch process folder: {folder}",
                )

        # Retry
        if lower.startswith("retry"):
            return self._make_result(
                CommandType.RETRY,
                RetryCommand(job_id=self._extract_job_id(text)),
                text, 0.95, "Interpreted as retry command",
            )

        # Single image process
        image_path = self._extract_image_path(text)
        if image_path:
            return self._make_result(
                CommandType.PROCESS_IMAGE,
                ProcessImageCommand(
                    image_path=image_path,
                    title=self._extract_title(text, image_path),
                    price=self._extract_price(text),
                    condition=self._extract_condition(lower),
                    color=self._extract_color(lower),
                    brand=self._extract_brand(text),
                    size=self._extract_size(lower),
                    category=self._extract_category(lower),
                    tags=self._extract_tags(lower),
                    bg_color=self._extract_bg_color(lower),
                ),
                text, 0.80, f"Process image: {image_path}",
            )

        # Fallback: if text mentions "process" but no path found
        if any(kw in lower for kw in ("process", "remove background", "edit", "list")):
            return self._unknown(text, "Could not find an image path in the instruction")

        return self._unknown(text)

    def get_interpreter_info(self) -> dict:
        return {
            "type": "mock",
            "version": "1.0.0",
            "is_mock": True,
            "capabilities": [
                "process_image", "batch_process",
                "check_status", "help",
            ],
        }

    # ------------------------------------------------------------------
    # Intent detection
    # ------------------------------------------------------------------

    def _is_help(self, lower: str) -> bool:
        return any(kw in lower for kw in (
            "help", "how to", "how do i", "what can", "commands", "usage", "guide",
        ))

    def _is_status_check(self, lower: str) -> bool:
        return any(kw in lower for kw in (
            "status", "check", "progress", "how is", "what happened",
            "show jobs", "list jobs", "failed jobs", "show me",
        ))

    def _is_batch(self, lower: str) -> bool:
        return any(kw in lower for kw in (
            "batch", "all images", "process all", "process folder",
            "all in", "entire folder", "whole folder",
        ))

    # ------------------------------------------------------------------
    # Extraction helpers
    # ------------------------------------------------------------------

    def _extract_image_path(self, text: str) -> str | None:
        match = PATH_PATTERN.search(text)
        if match:
            return match.group(2) or match.group(3)
        return None

    def _extract_folder(self, text: str) -> str | None:
        match = FOLDER_PATTERN.search(text)
        if match:
            return match.group(1)
        # Fallback: look for path after "in" or "from"
        m = re.search(r"(?:in|from)\s+['\"]?([^\s'\"]+)['\"]?", text, re.IGNORECASE)
        return m.group(1) if m else None

    def _extract_price(self, text: str) -> float | None:
        match = PRICE_PATTERN.search(text)
        return float(match.group(1)) if match else None

    def _extract_condition(self, lower: str) -> str | None:
        match = CONDITION_PATTERN.search(lower)
        return match.group(1).upper() if match else None

    def _extract_color(self, lower: str) -> str | None:
        match = COLOR_PATTERN.search(lower)
        return match.group(1).capitalize() if match else None

    def _extract_brand(self, text: str) -> str | None:
        match = BRAND_PATTERN.search(text)
        return match.group(1) if match else None

    def _extract_size(self, lower: str) -> str | None:
        match = SIZE_PATTERN.search(lower)
        return match.group(1).upper() if match else None

    def _extract_category(self, lower: str) -> str | None:
        for keyword, category in CATEGORY_MAP.items():
            if keyword in lower:
                return category
        return None

    def _extract_title(self, text: str, image_path: str) -> str | None:
        """Try to build a title from extracted fields."""
        parts = []
        brand = self._extract_brand(text)
        color = self._extract_color(text.lower())
        # Don't use the path as the title
        if brand:
            parts.append(brand)
        if color:
            parts.append(color)
        # Use stem of filename as fallback
        stem = Path(image_path).stem.replace("_", " ").replace("-", " ").title()
        if parts:
            parts.append(stem)
            return " ".join(parts)
        return None  # Let AI generate title in later task

    def _extract_tags(self, lower: str) -> list[str]:
        tags = []
        brand = self._extract_brand(lower)
        color = self._extract_color(lower)
        condition = self._extract_condition(lower)
        category = self._extract_category(lower)
        if brand:
            tags.append(brand.lower())
        if color:
            tags.append(color.lower())
        if condition:
            tags.append(condition.lower())
        if category:
            tags.append(category.lower())
        return tags

    def _extract_bg_color(self, lower: str) -> str | None:
        if "white background" in lower:
            return "#FFFFFF"
        if "black background" in lower:
            return "#000000"
        hex_match = re.search(r"#[0-9a-fA-F]{6}", lower)
        return hex_match.group(0).upper() if hex_match else None

    def _extract_help_topic(self, lower: str) -> str:
        if "batch" in lower:
            return "batch"
        if "process" in lower:
            return "processing"
        if "status" in lower:
            return "status"
        if "listing" in lower:
            return "listing"
        return "general"

    def _extract_job_id(self, text: str) -> str | None:
        # Look for UUID-like patterns
        m = re.search(
            r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}",
            text, re.IGNORECASE,
        )
        return m.group(0) if m else None

    def _extract_status_filter(self, lower: str) -> str | None:
        for status in ("queued", "processing", "completed", "failed"):
            if status in lower:
                return status.upper()
        return None

    # ------------------------------------------------------------------
    # Result builders
    # ------------------------------------------------------------------

    def _make_result(
        self,
        cmd_type: CommandType,
        command,
        raw_input: str,
        confidence: float,
        note: str,
    ) -> CommandResult:
        return CommandResult(
            command_type=cmd_type,
            command=command,
            confidence=confidence,
            interpretation_note=note,
            raw_input=raw_input,
        )

    def _unknown(self, raw_input: str, extra: str = "") -> CommandResult:
        msg = (
            "Could not understand the instruction. Try something like: "
            "'Process the image at /path/to/photo.jpg' or "
            "'Process all images in /path/to/folder'"
        )
        if extra:
            msg = f"{extra}. {msg}"
        return CommandResult(
            command_type=CommandType.UNKNOWN,
            command=UnknownCommand(raw_input=raw_input, error_message=msg),
            confidence=0.0,
            interpretation_note="No matching pattern found",
            raw_input=raw_input,
        )
