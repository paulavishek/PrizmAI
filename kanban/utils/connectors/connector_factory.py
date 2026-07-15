"""
Connector factory — maps a provider string to its connector class.

Parallels ``import_adapters.AdapterFactory``. Register a new tool by adding it
to ``_REGISTRY``; no other call-site changes.
"""

from typing import Dict, List, Type

from .base_connector import BaseSourceConnector, ConnectorError
from .jira_connector import JiraConnector
from .asana_connector import AsanaConnector
from .monday_connector import MondayConnector


class ConnectorFactory:
    # provider (matches SourceConnection.provider) -> connector class
    _REGISTRY: Dict[str, Type[BaseSourceConnector]] = {
        "jira": JiraConnector,
        "asana": AsanaConnector,
        "monday": MondayConnector,
        # Trello / ClickUp / Notion land here as they ship.
    }

    @classmethod
    def supported_providers(cls) -> List[str]:
        return list(cls._REGISTRY.keys())

    @classmethod
    def is_supported(cls, provider: str) -> bool:
        return provider in cls._REGISTRY

    @classmethod
    def get_connector(cls, provider: str, connection) -> BaseSourceConnector:
        connector_cls = cls._REGISTRY.get(provider)
        if connector_cls is None:
            raise ConnectorError(
                f"No live connector is available yet for provider '{provider}'."
            )
        return connector_cls(connection)
