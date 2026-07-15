"""
Base source connector — interface for all live-migration connectors.

A connector's single responsibility is to authenticate to an external PM tool
and return raw project data shaped *exactly* like the matching import adapter's
expected input. It performs NO translation itself — that stays in the adapters.

Subclasses implement:
    provider           - the SourceConnection.provider string this handles
    adapter_name       - the import-adapter name whose input shape fetch_project returns
    test_connection()  - verify credentials; raise ConnectorError on failure
    list_projects()    - [{"id": ..., "name": ...}, ...]
    fetch_project(id)  - raw data ready to hand to the matching adapter
"""

import logging
from abc import ABC, abstractmethod
from typing import Any, Dict, List

logger = logging.getLogger(__name__)


class ConnectorError(Exception):
    """
    Raised when a connector cannot authenticate or fetch data.

    ``status_code`` is the upstream HTTP status when relevant (e.g. 401/403 for
    bad credentials, 404 for a missing project). Never put a raw token in the
    message.
    """

    def __init__(self, message: str, status_code: int = None):
        self.message = message
        self.status_code = status_code
        super().__init__(message)


class BaseSourceConnector(ABC):
    """
    Abstract base class for live-migration connectors.

    Args:
        connection: an ``integrations.SourceConnection`` instance. The connector
            reads ``base_url``/``account_email`` from it and decrypts the token
            via ``connection.get_token()`` only in memory, only when needed.
    """

    provider: str = "base"
    adapter_name: str = ""
    # Default network timeout (seconds) for a single request.
    timeout: int = 30

    def __init__(self, connection):
        self.connection = connection

    # ---- Subclass interface -------------------------------------------------

    @abstractmethod
    def test_connection(self) -> Dict[str, Any]:
        """
        Verify the stored credentials work. Return a small dict of account info
        on success (e.g. ``{"account": "..."}``); raise ConnectorError on failure.
        """
        raise NotImplementedError

    @abstractmethod
    def list_projects(self) -> List[Dict[str, Any]]:
        """Return selectable projects as ``[{"id": ..., "name": ...}, ...]``."""
        raise NotImplementedError

    @abstractmethod
    def fetch_project(self, project_id: str) -> Any:
        """
        Fetch a whole project and return raw data shaped exactly like the
        matching import adapter's expected input (see ``adapter_name``).
        Handles pagination internally.
        """
        raise NotImplementedError
