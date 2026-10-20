from app.connectors.base import SocialConnector


class ConnectorRegistrationError(Exception):
    pass


class UnsupportedPlatformError(Exception):
    pass


class ConnectorRegistry:
    def __init__(self) -> None:
        self._connectors: dict[str, SocialConnector] = {}

    def register(self, connector: SocialConnector) -> None:
        if connector.platform in self._connectors:
            raise ConnectorRegistrationError(
                f"Connector already registered for platform '{connector.platform}'"
            )
        self._connectors[connector.platform] = connector

    def get(self, platform: str) -> SocialConnector:
        connector = self._connectors.get(platform)
        if connector is None:
            raise UnsupportedPlatformError(f"No connector registered for platform '{platform}'")
        return connector

    def is_registered(self, platform: str) -> bool:
        return platform in self._connectors


registry = ConnectorRegistry()
