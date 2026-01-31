"""
Import Adapters for PrizmAI
Provides adapters to transform data from various PM tools into PrizmAI's native format.

Supported formats:
- PrizmAI Native JSON
- Trello JSON export
- Jira CSV/JSON export
- Asana CSV/JSON export
- Monday.com CSV export
- Generic CSV with field mapping
"""

from .base_adapter import BaseImportAdapter, ImportResult, ImportError
from .adapter_factory import AdapterFactory, detect_format
from .trello_adapter import TrelloAdapter
from .jira_adapter import JiraAdapter
from .asana_adapter import AsanaAdapter
from .csv_adapter import CSVAdapter
from .prizmAI_adapter import PrizmAIAdapter
from .field_mapper import FieldMapper, UserMatcher

__all__ = [
    'BaseImportAdapter',
    'ImportResult',
    'ImportError',
    'AdapterFactory',
    'detect_format',
    'TrelloAdapter',
    'JiraAdapter',
    'AsanaAdapter',
    'CSVAdapter',
    'PrizmAIAdapter',
    'FieldMapper',
    'UserMatcher',
]
