from app.connectors.mock.connector import MockConnector
from app.connectors.registry import registry


def register_default_connectors() -> None:
    if not registry.is_registered("mock"):
        registry.register(MockConnector())
