"""
Vendoo Integration Package.
"""

from app.vendoo.connector import VendooConnector, VendooResult
from app.vendoo.mock_connector import MockVendooConnector
from app.config.settings import get_settings


def create_vendoo_connector(mode: str | None = None) -> VendooConnector:
    """
    Factory function to create the appropriate VendooConnector.
    
    Args:
        mode: "mock" or "production". Defaults to settings.APP_MODE.
    """
    if mode is None:
        mode = get_settings().app_mode

    if mode == "production":
        from app.vendoo.real_connector import RealVendooConnector
        settings = get_settings()
        return RealVendooConnector(output_dir=settings.output_dir)

    return MockVendooConnector()


__all__ = [
    "VendooConnector",
    "MockVendooConnector",
    "VendooResult",
    "create_vendoo_connector",
]
