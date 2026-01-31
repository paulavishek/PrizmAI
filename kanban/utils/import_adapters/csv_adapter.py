"""
CSV Import Adapter
Handles import of generic CSV files with field mapping support.

This is the most flexible adapter as it supports:
- Auto-detection of common PM tool CSV exports
- Manual field mapping via UI
- Universal fallback for any CSV
"""

import csv
import io
from typing import Dict, Any, Tuple, List, Optional
from collections import defaultdict

from .base_adapter import BaseImportAdapter, ImportResult, ImportError


class CSVAdapter(BaseImportAdapter):
    """
    Adapter for generic CSV imports.
    
    Supports two modes:
    1. Auto-mapping: Detects common field names and maps automatically
    2. Manual mapping: User provides explicit field mappings
    """
    
    name = "CSV Adapter"
    supported_extensions = ['csv', 'tsv']
    source_tool = "CSV"
    
    # Common field name patterns for auto-mapping
    # Each key is a PrizmAI field, values are possible source field names (lowercase)
    FIELD_PATTERNS = {
        'title': ['title', 'name', 'task', 'task name', 'summary', 'subject', 
                  'issue', 'card', 'card name', 'item', 'ticket', 'story'],
        'description': ['description', 'desc', 'details', 'body', 'content', 
                       'notes', 'note', 'comment', 'text'],
        'column': ['column', 'status', 'state', 'list', 'stage', 'phase',
                  'workflow', 'board column', 'group'],
        'priority': ['priority', 'urgency', 'importance', 'severity', 'p'],
        'progress': ['progress', 'percent', 'percentage', 'completion', 
                    'percent complete', '% complete', 'done'],
        'due_date': ['due date', 'due', 'deadline', 'due_date', 'target date',
                    'end date', 'finish date', 'complete by'],
        'start_date': ['start date', 'start', 'begin date', 'start_date',
                      'begin', 'created', 'created date'],
        'assigned_to': ['assigned to', 'assignee', 'owner', 'assigned', 
                       'responsible', 'user', 'member', 'team member'],
        'labels': ['labels', 'tags', 'label', 'tag', 'category', 'categories',
                  'type', 'issue type'],
        'complexity': ['complexity', 'story points', 'points', 'estimate',
                      'effort', 'size', 't-shirt size'],
        'external_id': ['id', 'key', 'issue key', 'ticket id', 'card id',
                       'task id', 'item id', 'external id'],
    }
    
    def __init__(self, field_mapper=None, user_matcher=None, custom_mappings: Dict[str, str] = None):
        """
        Initialize CSV adapter.
        
        Args:
            custom_mappings: Optional dict mapping source columns to PrizmAI fields
                            e.g., {'Issue Key': 'external_id', 'Summary': 'title'}
        """
        super().__init__(field_mapper, user_matcher)
        self.custom_mappings = custom_mappings or {}
        self.detected_mappings = {}
        self.unmapped_columns = []
    
    def can_handle(self, data: Any, filename: str = None) -> Tuple[bool, float]:
        """
        Check if this is a CSV file.
        CSV detection is based on:
        - File extension
        - Content structure (comma/tab separated values)
        """
        confidence = 0.0
        
        # Check filename extension
        if filename:
            ext = filename.lower().split('.')[-1] if '.' in filename else ''
            if ext in ['csv', 'tsv']:
                confidence += 0.5
        
        # Try to detect CSV structure
        if isinstance(data, (str, bytes)):
            sample = data[:2000] if isinstance(data, str) else data[:2000].decode('utf-8', errors='ignore')
            
            # Count potential delimiters
            comma_count = sample.count(',')
            tab_count = sample.count('\t')
            newline_count = sample.count('\n')
            
            # CSV typically has consistent delimiter counts per line
            if newline_count > 0:
                lines = sample.split('\n')[:5]
                if len(lines) >= 2:
                    # Check if delimiter count is consistent
                    if comma_count > tab_count:
                        counts = [line.count(',') for line in lines if line.strip()]
                    else:
                        counts = [line.count('\t') for line in lines if line.strip()]
                    
                    if counts and len(set(counts)) <= 2:  # Allow small variation
                        confidence += 0.4
        
        # Don't identify as CSV if it looks like JSON
        if isinstance(data, (str, bytes)):
            sample = data[:100] if isinstance(data, str) else data[:100].decode('utf-8', errors='ignore')
            if sample.strip().startswith(('{', '[')):
                confidence = 0.0
        
        return (confidence >= 0.5, min(confidence, 1.0))
    
    def parse(self, raw_data: Any) -> Dict[str, Any]:
        """Parse CSV data into a list of row dictionaries"""
        if isinstance(raw_data, bytes):
            # Try to detect encoding
            for encoding in ['utf-8', 'utf-8-sig', 'latin-1', 'cp1252']:
                try:
                    raw_data = raw_data.decode(encoding)
                    break
                except UnicodeDecodeError:
                    continue
            else:
                raise ImportError("Unable to decode CSV file - unknown encoding")
        
        if not isinstance(raw_data, str):
            raise ImportError("Invalid data type for CSV parsing")
        
        # Detect delimiter
        sample = raw_data[:1000]
        delimiter = '\t' if sample.count('\t') > sample.count(',') else ','
        
        try:
            reader = csv.DictReader(io.StringIO(raw_data), delimiter=delimiter)
            rows = list(reader)
            
            if not rows:
                raise ImportError("CSV file is empty or has no data rows")
            
            # Get headers
            headers = reader.fieldnames or []
            
            return {
                'headers': headers,
                'rows': rows,
                'delimiter': delimiter,
                'row_count': len(rows),
            }
            
        except csv.Error as e:
            raise ImportError(f"CSV parsing error: {e}")
    
    def validate(self, parsed_data: Dict[str, Any]) -> bool:
        """Validate CSV data structure"""
        if 'headers' not in parsed_data or 'rows' not in parsed_data:
            raise ImportError("Invalid parsed CSV data structure")
        
        headers = parsed_data['headers']
        if not headers:
            raise ImportError("CSV has no headers")
        
        # Auto-detect field mappings
        self.detected_mappings = self._auto_detect_mappings(headers)
        
        # Check if we can map at least a title field
        if 'title' not in self.detected_mappings and 'title' not in self.custom_mappings.values():
            # Try to find any reasonable title column
            for header in headers:
                if header:  # Use first non-empty column as title
                    self.detected_mappings['title'] = header
                    self.result.add_warning(f"Using '{header}' as task title (no title column detected)")
                    break
        
        if 'title' not in self.detected_mappings and 'title' not in self.custom_mappings.values():
            raise ImportError("Could not detect a title/name column in CSV")
        
        # Track unmapped columns
        mapped_sources = set(self.detected_mappings.values()) | set(self.custom_mappings.keys())
        self.unmapped_columns = [h for h in headers if h not in mapped_sources]
        
        return True
    
    def transform_to_prizmAI(self, parsed_data: Dict[str, Any]) -> ImportResult:
        """Transform CSV data to PrizmAI format"""
        result = ImportResult(
            source_format='csv',
            source_tool=self.source_tool
        )
        
        # Merge custom mappings with detected mappings (custom takes precedence)
        effective_mappings = dict(self.detected_mappings)
        for source_col, target_field in self.custom_mappings.items():
            effective_mappings[target_field] = source_col
        
        result.field_mappings = effective_mappings
        result.unmapped_fields = self.unmapped_columns
        
        # Collect unique columns and labels
        columns_seen = {}
        labels_seen = {}
        tasks = []
        
        for row_idx, row in enumerate(parsed_data['rows']):
            task_data = self._transform_row(row, effective_mappings, row_idx, columns_seen, labels_seen)
            if task_data:
                tasks.append(task_data)
                result.update_stats('tasks_imported')
        
        # Build column data
        # Sort columns by first appearance order
        for col_name, col_info in sorted(columns_seen.items(), key=lambda x: x[1]['order']):
            result.columns_data.append({
                'name': col_name,
                'position': col_info['order'],
                'temp_id': col_info['temp_id'],
            })
            result.update_stats('columns_imported')
        
        # Build label data
        for label_name, label_color in labels_seen.items():
            result.labels_data.append({
                'name': label_name,
                'color': label_color,
            })
            result.update_stats('labels_imported')
        
        result.tasks_data = tasks
        
        # Board data
        result.board_data = {
            'name': 'Imported from CSV',
            'description': f'Imported {len(tasks)} tasks from CSV file',
        }
        
        return result
    
    def _auto_detect_mappings(self, headers: List[str]) -> Dict[str, str]:
        """
        Auto-detect field mappings based on header names.
        Returns dict of PrizmAI field -> source column name
        """
        mappings = {}
        headers_lower = {h.lower().strip(): h for h in headers if h}
        
        for prizmAI_field, patterns in self.FIELD_PATTERNS.items():
            for pattern in patterns:
                if pattern in headers_lower:
                    mappings[prizmAI_field] = headers_lower[pattern]
                    break
        
        return mappings
    
    def _transform_row(self, row: Dict, mappings: Dict, row_idx: int,
                       columns_seen: Dict, labels_seen: Dict) -> Optional[Dict[str, Any]]:
        """Transform a single CSV row to task data"""
        
        def get_value(field: str) -> Any:
            """Get value for a PrizmAI field from the row"""
            source_col = mappings.get(field)
            if source_col and source_col in row:
                return row[source_col]
            return None
        
        # Get required title
        title = get_value('title')
        if not title or not str(title).strip():
            self.result.add_warning(f"Row {row_idx + 2}: Skipped - no title")
            return None
        
        # Get or create column
        column_name = get_value('column') or 'To Do'
        column_name = str(column_name).strip() or 'To Do'
        
        if column_name not in columns_seen:
            columns_seen[column_name] = {
                'order': len(columns_seen),
                'temp_id': f'col_{len(columns_seen)}',
            }
        
        # Process labels
        label_names = []
        labels_value = get_value('labels')
        if labels_value:
            # Labels might be comma-separated
            for label in str(labels_value).split(','):
                label = label.strip()
                if label:
                    label_names.append(label)
                    if label not in labels_seen:
                        labels_seen[label] = self._generate_label_color(len(labels_seen))
        
        # Build task data
        task_data = {
            'title': self._sanitize_string(title, max_length=200),
            'description': get_value('description') or '',
            'column_temp_id': columns_seen[column_name]['temp_id'],
            'position': row_idx,
            'priority': self._normalize_priority(get_value('priority')),
            'progress': self._normalize_progress(get_value('progress')),
            'due_date': self._parse_date(get_value('due_date')),
            'start_date': self._parse_date(get_value('start_date')),
            'assigned_to_username': get_value('assigned_to'),
            'label_names': label_names,
            'external_id': get_value('external_id'),
            'complexity_score': self._normalize_complexity(get_value('complexity')),
        }
        
        return task_data
    
    def _normalize_complexity(self, value: Any) -> int:
        """Normalize complexity/story points to 1-10 scale"""
        if value is None:
            return 5
        
        try:
            # Handle T-shirt sizes
            if isinstance(value, str):
                size_map = {
                    'xs': 1, 'extra small': 1,
                    's': 2, 'small': 2,
                    'm': 5, 'medium': 5,
                    'l': 7, 'large': 7,
                    'xl': 9, 'extra large': 9,
                    'xxl': 10,
                }
                if value.lower().strip() in size_map:
                    return size_map[value.lower().strip()]
            
            # Handle numeric values
            num = float(value)
            
            # If using Fibonacci story points, map to 1-10
            fib_map = {1: 1, 2: 2, 3: 3, 5: 5, 8: 7, 13: 9, 21: 10}
            if num in fib_map:
                return fib_map[num]
            
            # Clamp to 1-10
            return max(1, min(10, int(num)))
            
        except (ValueError, TypeError):
            return 5
    
    def _generate_label_color(self, index: int) -> str:
        """Generate a color for a label based on index"""
        colors = [
            '#61bd4f',  # Green
            '#f2d600',  # Yellow
            '#ff9f1a',  # Orange
            '#eb5a46',  # Red
            '#c377e0',  # Purple
            '#0079bf',  # Blue
            '#00c2e0',  # Sky
            '#51e898',  # Lime
            '#ff78cb',  # Pink
            '#344563',  # Black
        ]
        return colors[index % len(colors)]
    
    def get_available_columns(self, raw_data: Any) -> List[str]:
        """
        Get list of column headers from CSV without full parsing.
        Useful for building field mapping UI.
        """
        parsed = self.parse(raw_data)
        return parsed.get('headers', [])
    
    def get_suggested_mappings(self, raw_data: Any) -> Dict[str, str]:
        """
        Get auto-detected field mappings for UI preview.
        Returns dict of PrizmAI field -> suggested source column
        """
        parsed = self.parse(raw_data)
        return self._auto_detect_mappings(parsed.get('headers', []))
