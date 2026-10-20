from app.connectors.facebook.connector import FacebookConnector
from app.connectors.mock.connector import MockConnector
from app.connectors.registry import registry
from app.core.config import get_settings
from app.core.database import AsyncSessionLocal

settings = get_settings()


def register_default_connectors() -> None:
    """Registers connectors that only need per-account credentials resolved at publish time.

    Platform app credentials (e.g. Meta App ID/Secret) are workspace-scoped and resolved
    per-request by the OAuth connect/callback endpoints, not needed to construct the connector.
    """
    if not registry.is_registered("mock"):
        registry.register(MockConnector())

    if not registry.is_registered("facebook"):
        registry.register(
            FacebookConnector(AsyncSessionLocal, api_version=settings.meta_graph_api_version)
        )
