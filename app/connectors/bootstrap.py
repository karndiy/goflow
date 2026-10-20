from app.connectors.facebook.connector import FacebookConnector
from app.connectors.mock.connector import MockConnector
from app.connectors.registry import registry
from app.core.config import get_settings
from app.core.database import AsyncSessionLocal

settings = get_settings()


def register_default_connectors() -> None:
    if not registry.is_registered("mock"):
        registry.register(MockConnector())

    if settings.meta_app_id and settings.meta_app_secret and not registry.is_registered("facebook"):
        registry.register(
            FacebookConnector(AsyncSessionLocal, api_version=settings.meta_graph_api_version)
        )
