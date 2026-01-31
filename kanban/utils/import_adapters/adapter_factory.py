"""
Adapter Factory
Auto-detects file format and routes to the appropriate import adapter.
"""

import json
from typing import Any, Optional, List, Tuple, Type
import logging

from .base_adapter import BaseImportAdapter, ImportResult, ImportError
from .prizmAI_adapter import PrizmAIAdapter
from .trello_adapter import TrelloAdapter
from .jira_adapter import JiraAdapter
from .asana_adapter import AsanaAdapter
from .csv_adapter import CSVAdapter

logger = logging.getLogger(__name__)


# Adapter priority order (higher priority adapters are checked first)
ADAPTER_PRIORITY: List[Type[BaseImportAdapter]] = [
    PrizmAIAdapter,  # Check native format first
    TrelloAdapter,   # Trello has distinctive markers
    JiraAdapter,     # Jira has distinctive markers
    AsanaAdapter,    # Asana has distinctive markers
    CSVAdapter,      # Generic CSV as fallback
]


def detect_format(data: Any, filename: str = None) -> Tuple[Optional[str], Optional[Type[BaseImportAdapter]], float]:
    """
    Detect the format of the import data and return the best matching adapter.
    
    Args:
        data: The raw import data (string, bytes, or dict)
        filename: Optional filename for extension-based hints
    
    Returns:
        Tuple of (format_name, adapter_class, confidence)
    """
    best_adapter = None
    best_confidence = 0.0
    best_format = None
    
    for adapter_class in ADAPTER_PRIORITY:
        try:
            adapter = adapter_class()
            can_handle, confidence = adapter.can_handle(data, filename)
            
            logger.debug(f"{adapter_class.name}: can_handle={can_handle}, confidence={confidence}")
            
            if can_handle and confidence > best_confidence:
                best_adapter = adapter_class
                best_confidence = confidence
                best_format = adapter.source_tool
                
                # If we have very high confidence, stop checking
                if confidence >= 0.95:
                    break
                    
        except Exception as e:
            logger.warning(f"Error checking adapter {adapter_class.name}: {e}")
            continue
    
    return (best_format, best_adapter, best_confidence)


class AdapterFactory:
    """
    Factory for creating and using import adapters.
    
    Usage:
        factory = AdapterFactory()
        result = factory.import_from_file(file_data, filename='export.json')
        
        # Or with explicit adapter:
        result = factory.import_with_adapter('trello', file_data)
    """
    
    # Map of adapter names to classes
    ADAPTER_REGISTRY = {
        'prizmAI': PrizmAIAdapter,
        'prizmAI_native': PrizmAIAdapter,
        'trello': TrelloAdapter,
        'jira': JiraAdapter,
        'asana': AsanaAdapter,
        'csv': CSVAdapter,
        'generic': CSVAdapter,
    }
    
    def __init__(self, field_mapper=None, user_matcher=None):
        """
        Initialize the factory with optional utilities.
        
        Args:
            field_mapper: FieldMapper instance for custom field mappings
            user_matcher: UserMatcher instance for user resolution
        """
        self.field_mapper = field_mapper
        self.user_matcher = user_matcher
    
    def detect_and_import(self, data: Any, filename: str = None) -> ImportResult:
        """
        Auto-detect the format and import the data.
        
        Args:
            data: The raw import data
            filename: Optional filename for hints
        
        Returns:
            ImportResult with transformed data
        """
        # Detect the best adapter
        format_name, adapter_class, confidence = detect_format(data, filename)
        
        if not adapter_class:
            result = ImportResult(success=False)
            result.add_error("Could not detect import format. Supported formats: Trello JSON, Jira CSV/JSON, Asana CSV/JSON, generic CSV")
            return result
        
        logger.info(f"Detected format: {format_name} (confidence: {confidence:.2f}), using {adapter_class.name}")
        
        # Create adapter and import
        adapter = adapter_class(
            field_mapper=self.field_mapper,
            user_matcher=self.user_matcher
        )
        
        result = adapter.import_data(data, filename)
        
        # Add detection info to result
        result.field_mappings['_detected_format'] = format_name
        result.field_mappings['_detection_confidence'] = str(confidence)
        
        return result
    
    def import_with_adapter(self, adapter_name: str, data: Any, 
                            filename: str = None, **kwargs) -> ImportResult:
        """
        Import using a specific adapter.
        
        Args:
            adapter_name: Name of the adapter to use (e.g., 'trello', 'jira', 'csv')
            data: The raw import data
            filename: Optional filename
            **kwargs: Additional arguments passed to the adapter
        
        Returns:
            ImportResult with transformed data
        """
        adapter_name_lower = adapter_name.lower()
        
        if adapter_name_lower not in self.ADAPTER_REGISTRY:
            result = ImportResult(success=False)
            result.add_error(f"Unknown adapter: {adapter_name}. Available: {', '.join(self.ADAPTER_REGISTRY.keys())}")
            return result
        
        adapter_class = self.ADAPTER_REGISTRY[adapter_name_lower]
        
        # Create adapter with any additional kwargs
        adapter = adapter_class(
            field_mapper=self.field_mapper,
            user_matcher=self.user_matcher,
            **kwargs
        )
        
        return adapter.import_data(data, filename)
    
    def get_available_adapters(self) -> List[dict]:
        """
        Get list of available adapters with their info.
        
        Returns:
            List of adapter info dictionaries
        """
        adapters = []
        seen = set()
        
        for name, adapter_class in self.ADAPTER_REGISTRY.items():
            if adapter_class not in seen:
                seen.add(adapter_class)
                adapters.append({
                    'name': name,
                    'display_name': adapter_class.name,
                    'source_tool': adapter_class.source_tool,
                    'extensions': adapter_class.supported_extensions,
                })
        
        return adapters
    
    def preview_import(self, data: Any, filename: str = None) -> dict:
        """
        Preview an import without actually transforming the data.
        Useful for showing users what will be imported.
        
        Args:
            data: The raw import data
            filename: Optional filename
        
        Returns:
            Preview information dictionary
        """
        format_name, adapter_class, confidence = detect_format(data, filename)
        
        if not adapter_class:
            return {
                'success': False,
                'error': 'Could not detect format',
                'supported_formats': [a['display_name'] for a in self.get_available_adapters()],
            }
        
        # Create adapter and parse (but don't fully transform)
        adapter = adapter_class(
            field_mapper=self.field_mapper,
            user_matcher=self.user_matcher
        )
        
        try:
            parsed = adapter.parse(data)
            adapter.validate(parsed)
            
            # Build preview based on adapter type
            preview = {
                'success': True,
                'detected_format': format_name,
                'adapter': adapter.name,
                'confidence': confidence,
            }
            
            # Try to get counts
            if isinstance(adapter, CSVAdapter):
                preview['row_count'] = parsed.get('row_count', 0)
                preview['columns'] = parsed.get('headers', [])
                preview['suggested_mappings'] = adapter.get_suggested_mappings(data)
            elif isinstance(adapter, TrelloAdapter):
                preview['list_count'] = len(parsed.get('lists', []))
                preview['card_count'] = len(parsed.get('cards', []))
                preview['board_name'] = parsed.get('name', 'Unknown')
            elif isinstance(adapter, JiraAdapter):
                if parsed.get('format') == 'json':
                    preview['issue_count'] = len(parsed.get('issues', []))
                else:
                    preview['issue_count'] = len(parsed.get('rows', []))
            elif isinstance(adapter, AsanaAdapter):
                if parsed.get('format') == 'json':
                    preview['task_count'] = len(parsed.get('tasks', []))
                else:
                    preview['task_count'] = len(parsed.get('rows', []))
            
            return preview
            
        except ImportError as e:
            return {
                'success': False,
                'error': str(e),
                'detected_format': format_name,
            }
        except Exception as e:
            return {
                'success': False,
                'error': f'Unexpected error: {str(e)}',
            }


# Convenience function for direct use
def import_board_data(data: Any, filename: str = None, 
                      adapter_name: str = None, **kwargs) -> ImportResult:
    """
    Convenience function to import board data.
    
    Args:
        data: The raw import data
        filename: Optional filename for format hints
        adapter_name: Optional explicit adapter name
        **kwargs: Additional arguments for the adapter
    
    Returns:
        ImportResult with transformed data
    """
    factory = AdapterFactory()
    
    if adapter_name:
        return factory.import_with_adapter(adapter_name, data, filename, **kwargs)
    else:
        return factory.detect_and_import(data, filename)
