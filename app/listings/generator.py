"""
Listing Generator Interface & Mock Implementation.

Takes a processed image and a structured command, and generates
the final ProductListing data.
"""

from abc import ABC, abstractmethod
from pathlib import Path
from dataclasses import dataclass

from app.ai.schemas import ProcessImageCommand
from app.listings.schemas import ProductListing
from app.logging import get_logger

logger = get_logger("listings.generator")


@dataclass
class GenerationResult:
    """Outcome of listing generation."""
    success: bool
    listing: ProductListing | None = None
    error_message: str = ""
    is_retryable: bool = False


class ListingGenerator(ABC):
    """Abstract interface for listing generation."""

    @abstractmethod
    def generate(
        self, 
        image_path: Path, 
        command: ProcessImageCommand | None = None
    ) -> GenerationResult:
        """
        Generate listing data from an image and user constraints.
        
        Args:
            image_path: Path to the processed image.
            command: The parsed command with user-supplied facts (price, brand, etc.)
            
        Returns:
            GenerationResult containing the ProductListing.
        """
        ...


class MockListingGenerator(ListingGenerator):
    """
    Mock generator for testing without LLM API calls.
    
    Uses provided command data, or generates deterministic boilerplate
    if data is missing.
    """

    def __init__(self):
        logger.info("MockListingGenerator initialized")

    def generate(
        self, 
        image_path: Path, 
        command: ProcessImageCommand | None = None
    ) -> GenerationResult:
        """Generate a mock listing."""
        if not image_path.exists():
            return GenerationResult(
                success=False,
                error_message=f"Image not found: {image_path}",
                is_retryable=False
            )

        # Base defaults
        stem = image_path.stem.replace("_", " ").replace("-", " ").title()
        title = f"{stem} Item"
        price = 19.99
        desc_lines = ["High-quality product.", "Great condition."]
        tags = ["mock", "item"]
        
        # Apply command constraints
        if command:
            if command.title:
                title = command.title
            elif command.brand or command.color or command.category:
                parts = []
                if command.brand:
                    parts.append(command.brand)
                if command.color:
                    parts.append(command.color)
                if command.category:
                    parts.append(command.category)
                else:
                    parts.append(stem)
                title = " ".join(parts)
            
            if command.price is not None:
                price = command.price
            
            if command.description:
                desc_lines = [command.description]
            
            if command.tags:
                tags = command.tags
            else:
                if command.brand: tags.append(command.brand.lower())
                if command.color: tags.append(command.color.lower())
                if command.condition: tags.append(command.condition.lower())
        
        # Construct final description
        description = "\n".join(desc_lines)
        if command:
            if command.brand: description += f"\nBrand: {command.brand}"
            if command.size: description += f"\nSize: {command.size}"
            if command.condition: description += f"\nCondition: {command.condition}"

        try:
            listing = ProductListing(
                title=title[:120],  # Max length enforcement
                description=description,
                price=price,
                category=command.category if command else "General",
                brand=command.brand if command else None,
                condition=command.condition if command else None,
                color=command.color if command else None,
                size=command.size if command else None,
                tags=tags[:30]  # Max tags enforcement
            )
            
            logger.info(f"Mock generated listing for {image_path.name}")
            return GenerationResult(success=True, listing=listing)
            
        except Exception as e:
            msg = f"Failed to build mock listing: {e}"
            logger.error(msg)
            return GenerationResult(success=False, error_message=msg, is_retryable=False)
