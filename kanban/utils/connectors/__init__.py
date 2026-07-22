"""
Live migration connectors.

Where ``kanban/utils/import_adapters`` handles *file* imports (a user exports a
file from their old tool and uploads it), this package handles *live* imports:
a connector authenticates to an external PM tool's API, fetches a project, and
shapes the raw data into exactly the form the matching import adapter already
consumes — so all translation logic is reused, not rewritten.

Pipeline:
    [Connector: live API fetch] -> [existing Adapter: translate]
        -> [migration_orchestrator: Strategy + Boards] -> [async AI audit]

Public API:
    ConnectorFactory.get_connector(provider, connection) -> BaseSourceConnector
    BaseSourceConnector.test_connection()
    BaseSourceConnector.list_projects()
    BaseSourceConnector.fetch_project(project_id)
"""

from .base_connector import BaseSourceConnector, ConnectorError
from .connector_factory import ConnectorFactory

__all__ = [
    "BaseSourceConnector",
    "ConnectorError",
    "ConnectorFactory",
]
