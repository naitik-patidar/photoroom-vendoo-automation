"""
PhotoRoom API client package.

Provides:
- PhotoRoomClient: abstract interface
- MockPhotoRoomClient: simulated processing for development
- RealPhotoRoomClient: real API client (stub until Task 14)
- create_photoroom_client(): factory function
"""

from app.photoroom.client import PhotoRoomClient, PhotoRoomResult, ProcessingStatus
from app.photoroom.mock_client import MockPhotoRoomClient
from app.photoroom.real_client import RealPhotoRoomClient


def create_photoroom_client(
    mode: str = "mock",
    api_key: str = "",
    sandbox: bool = True,
) -> PhotoRoomClient:
    """
    Factory function to create the appropriate PhotoRoom client.

    Args:
        mode: "mock" or "production"
        api_key: PhotoRoom API key (only needed for production)
        sandbox: Whether to use sandbox mode

    Returns:
        A PhotoRoomClient implementation.
    """
    if mode == "production":
        from app.photoroom.real_client import RealPhotoRoomClient
        from app.config.settings import get_settings
        settings = get_settings()
        return RealPhotoRoomClient(api_key=api_key or settings.photoroom_api_key, sandbox=sandbox)
    return MockPhotoRoomClient(sandbox=sandbox)


__all__ = [
    "PhotoRoomClient",
    "PhotoRoomResult",
    "ProcessingStatus",
    "MockPhotoRoomClient",
    "RealPhotoRoomClient",
    "create_photoroom_client",
]
