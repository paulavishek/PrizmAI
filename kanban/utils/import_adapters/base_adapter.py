"""
Base Import Adapter
Abstract base class that defines the interface for all import adapters.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class ImportError(Exception):
    """Custom exception for import-related errors"""
    def __init__(self, message: str, field: str = None, row: int = None):
        self.message = message
        self.field = field
        self.row = row
        super().__init__(self.message)
    
    def __str__(self):
        parts = [self.message]
        if self.field:
            parts.append(f"Field: {self.field}")
        if self.row:
            parts.append(f"Row: {self.row}")
        return " | ".join(parts)


@dataclass
class ImportResult:
    """
    Standardized result object for import operations.
    Contains the transformed data ready for PrizmAI model creation.
    """
    success: bool = True
    source_format: str = ""
    source_tool: str = ""
    
    # Transformed data in PrizmAI native format
    board_data: Dict[str, Any] = field(default_factory=dict)
    columns_data: List[Dict[str, Any]] = field(default_factory=list)
    tasks_data: List[Dict[str, Any]] = field(default_factory=list)
    labels_data: List[Dict[str, Any]] = field(default_factory=list)
    users_data: List[Dict[str, Any]] = field(default_factory=list)
    comments_data: List[Dict[str, Any]] = field(default_factory=list)
    checklists_data: List[Dict[str, Any]] = field(default_factory=list)
    
    # Import statistics
    stats: Dict[str, int] = field(default_factory=dict)
    
    # Warnings and errors (non-fatal issues)
    warnings: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    
    # Field mapping info (for user review)
    field_mappings: Dict[str, str] = field(default_factory=dict)
    unmapped_fields: List[str] = field(default_factory=list)
    
    def add_warning(self, message: str):
        """Add a warning message"""
        self.warnings.append(message)
        logger.warning(f"Import warning: {message}")
    
    def add_error(self, message: str):
        """Add an error message (non-fatal)"""
        self.errors.append(message)
        logger.error(f"Import error: {message}")
    
    def update_stats(self, key: str, count: int = 1):
        """Update import statistics"""
        if key not in self.stats:
            self.stats[key] = 0
        self.stats[key] += count
    
    def get_summary(self) -> Dict[str, Any]:
        """Get a summary of the import result"""
        return {
            'success': self.success,
            'source_format': self.source_format,
            'source_tool': self.source_tool,
            'statistics': self.stats,
            'warnings_count': len(self.warnings),
            'errors_count': len(self.errors),
            'unmapped_fields': self.unmapped_fields,
        }


class BaseImportAdapter(ABC):
    """
    Abstract base class for all import adapters.
    
    Each adapter is responsible for:
    1. Detecting if it can handle a given file/data format
    2. Parsing the raw data
    3. Validating the data structure
    4. Transforming to PrizmAI's native format
    """
    
    # Adapter metadata
    name: str = "Base Adapter"
    supported_extensions: List[str] = []
    source_tool: str = "Unknown"
    
    def __init__(self, field_mapper=None, user_matcher=None):
        """
        Initialize the adapter with optional field mapper and user matcher.
        
        Args:
            field_mapper: Optional FieldMapper instance for custom field mappings
            user_matcher: Optional UserMatcher instance for resolving user assignments
        """
        self.field_mapper = field_mapper
        self.user_matcher = user_matcher
        self.result = ImportResult()
    
    @abstractmethod
    def can_handle(self, data: Any, filename: str = None) -> Tuple[bool, float]:
        """
        Check if this adapter can handle the given data.
        
        Args:
            data: The raw data (could be dict, string, bytes depending on format)
            filename: Optional filename for extension-based detection
        
        Returns:
            Tuple of (can_handle: bool, confidence: float 0.0-1.0)
        """
        pass
    
    @abstractmethod
    def parse(self, raw_data: Any) -> Dict[str, Any]:
        """
        Parse the raw input data into a structured dictionary.
        
        Args:
            raw_data: The raw data from the file (string, bytes, etc.)
        
        Returns:
            Parsed data as a dictionary
        
        Raises:
            ImportError: If parsing fails
        """
        pass
    
    @abstractmethod
    def validate(self, parsed_data: Dict[str, Any]) -> bool:
        """
        Validate the parsed data structure.
        
        Args:
            parsed_data: The parsed data dictionary
        
        Returns:
            True if valid, False otherwise
        
        Raises:
            ImportError: If validation fails with details
        """
        pass
    
    @abstractmethod
    def transform_to_prizmAI(self, parsed_data: Dict[str, Any]) -> ImportResult:
        """
        Transform the parsed data into PrizmAI's native format.
        
        Args:
            parsed_data: The parsed and validated data
        
        Returns:
            ImportResult with transformed data
        """
        pass
    
    def import_data(self, raw_data: Any, filename: str = None) -> ImportResult:
        """
        Main entry point for importing data.
        Orchestrates the parse -> validate -> transform pipeline.
        
        Args:
            raw_data: The raw data to import
            filename: Optional filename for context
        
        Returns:
            ImportResult with the transformed data and any warnings/errors
        """
        self.result = ImportResult(
            source_format=self._detect_format(raw_data, filename),
            source_tool=self.source_tool
        )
        
        try:
            # Step 1: Parse raw data
            logger.info(f"{self.name}: Parsing data...")
            parsed_data = self.parse(raw_data)
            
            # Step 2: Validate structure
            logger.info(f"{self.name}: Validating data...")
            self.validate(parsed_data)
            
            # Step 3: Transform to PrizmAI format
            logger.info(f"{self.name}: Transforming to PrizmAI format...")
            self.result = self.transform_to_prizmAI(parsed_data)
            self.result.success = True
            
        except ImportError as e:
            self.result.success = False
            self.result.add_error(str(e))
        except Exception as e:
            self.result.success = False
            self.result.add_error(f"Unexpected error: {str(e)}")
            logger.exception(f"Import failed: {e}")
        
        return self.result
    
    def _detect_format(self, data: Any, filename: str = None) -> str:
        """Detect the data format based on content and filename"""
        if filename:
            ext = filename.lower().split('.')[-1] if '.' in filename else ''
            return ext
        return "unknown"
    
    # Utility methods for subclasses
    
    def _normalize_priority(self, value: str) -> str:
        """
        Normalize priority values to PrizmAI's format.
        Maps various priority representations to: low, medium, high, urgent
        """
        if not value:
            return 'medium'
        
        value = str(value).lower().strip()
        
        # Common mappings
        priority_map = {
            # Low variants
            'low': 'low',
            'lowest': 'low',
            'minor': 'low',
            'trivial': 'low',
            '1': 'low',
            'p4': 'low',
            'p5': 'low',
            
            # Medium variants
            'medium': 'medium',
            'normal': 'medium',
            'moderate': 'medium',
            '2': 'medium',
            '3': 'medium',
            'p3': 'medium',
            
            # High variants
            'high': 'high',
            'major': 'high',
            'important': 'high',
            '4': 'high',
            'p2': 'high',
            
            # Urgent variants
            'urgent': 'urgent',
            'critical': 'urgent',
            'blocker': 'urgent',
            'highest': 'urgent',
            '5': 'urgent',
            'p1': 'urgent',
        }
        
        return priority_map.get(value, 'medium')
    
    def _normalize_progress(self, value: Any) -> int:
        """
        Normalize progress values to 0-100 integer.
        """
        if value is None:
            return 0
        
        try:
            # Handle percentage strings like "50%"
            if isinstance(value, str):
                value = value.replace('%', '').strip()
            
            progress = int(float(value))
            return max(0, min(100, progress))
        except (ValueError, TypeError):
            return 0
    
    def _parse_date(self, value: Any) -> Optional[datetime]:
        """
        Parse various date formats to datetime object.
        """
        if not value:
            return None
        
        if isinstance(value, datetime):
            return value
        
        # Common date formats to try
        date_formats = [
            '%Y-%m-%dT%H:%M:%S.%fZ',  # ISO format with milliseconds
            '%Y-%m-%dT%H:%M:%SZ',      # ISO format
            '%Y-%m-%dT%H:%M:%S',       # ISO format without Z
            '%Y-%m-%d %H:%M:%S',       # Standard datetime
            '%Y-%m-%d',                 # Date only
            '%m/%d/%Y',                 # US date
            '%d/%m/%Y',                 # European date
            '%d-%m-%Y',                 # European date with dashes
            '%B %d, %Y',                # "January 31, 2026"
        ]
        
        value_str = str(value).strip()
        
        for fmt in date_formats:
            try:
                return datetime.strptime(value_str, fmt)
            except ValueError:
                continue
        
        # Try Unix timestamp
        try:
            timestamp = float(value_str)
            # Handle milliseconds
            if timestamp > 10000000000:
                timestamp = timestamp / 1000
            return datetime.fromtimestamp(timestamp)
        except (ValueError, TypeError, OSError):
            pass
        
        return None
    
    def _generate_position(self, index: int, existing_positions: List[int] = None) -> int:
        """
        Generate a position value for ordering.
        """
        if existing_positions:
            return max(existing_positions) + 1 + index
        return index
    
    def _sanitize_string(self, value: Any, max_length: int = None) -> str:
        """
        Sanitize and truncate string values.
        """
        if value is None:
            return ''
        
        result = str(value).strip()
        
        if max_length and len(result) > max_length:
            result = result[:max_length - 3] + '...'
        
        return result
    
    def _extract_color(self, value: str) -> str:
        """
        Extract or generate a color code from a value.
        Returns a valid hex color code.
        """
        if not value:
            return '#808080'  # Default gray
        
        value = str(value).lower().strip()
        
        # If already a hex color
        if value.startswith('#') and len(value) in [4, 7]:
            return value
        
        # Common color name mappings (Trello, etc.)
        color_map = {
            'green': '#61bd4f',
            'yellow': '#f2d600',
            'orange': '#ff9f1a',
            'red': '#eb5a46',
            'purple': '#c377e0',
            'blue': '#0079bf',
            'sky': '#00c2e0',
            'lime': '#51e898',
            'pink': '#ff78cb',
            'black': '#344563',
            'grey': '#808080',
            'gray': '#808080',
        }
        
        return color_map.get(value, '#808080')
