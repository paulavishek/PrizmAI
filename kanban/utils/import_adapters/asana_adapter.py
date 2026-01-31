"""
Asana Import Adapter
Handles import of Asana CSV and JSON export formats.

Asana Export Formats:
- CSV: Project > Export > CSV
- JSON: Via Asana API

Asana-specific fields:
- Task ID (gid)
- Name
- Section/Column
- Assignee
- Due Date
- Tags
- Projects
- Subtasks
- Custom Fields
"""

import json
import csv
import io
from typing import Dict, Any, Tuple, List, Optional

from .base_adapter import BaseImportAdapter, ImportResult, ImportError


class AsanaAdapter(BaseImportAdapter):
    """
    Adapter for Asana exports (CSV and JSON).
    
    Supports:
    - Asana CSV export
    - Asana JSON (from API)
    """
    
    name = "Asana Adapter"
    supported_extensions = ['csv', 'json']
    source_tool = "Asana"
    
    # Asana CSV column patterns
    ASANA_CSV_PATTERNS = [
        'task id', 'name', 'section/column', 'assignee', 'due date',
        'tags', 'notes', 'projects', 'created at', 'completed at',
        'parent task', 'blocked by', 'blocking'
    ]
    
    # Asana section to column mapping
    SECTION_TO_COLUMN = {
        'to do': 'To Do',
        'to-do': 'To Do',
        'in progress': 'In Progress',
        'doing': 'In Progress',
        'done': 'Done',
        'complete': 'Done',
        'completed': 'Done',
    }
    
    def can_handle(self, data: Any, filename: str = None) -> Tuple[bool, float]:
        """Detect Asana export format"""
        confidence = 0.0
        
        # Check if it's JSON
        if isinstance(data, str):
            data_stripped = data.strip()
            if data_stripped.startswith('{') or data_stripped.startswith('['):
                try:
                    json_data = json.loads(data)
                    return self._check_asana_json(json_data)
                except json.JSONDecodeError:
                    pass
            else:
                # Check CSV
                return self._check_asana_csv(data)
        
        if isinstance(data, dict):
            return self._check_asana_json(data)
        
        if isinstance(data, bytes):
            try:
                decoded = data.decode('utf-8')
                return self.can_handle(decoded, filename)
            except UnicodeDecodeError:
                return (False, 0.0)
        
        return (False, 0.0)
    
    def _check_asana_json(self, data: Dict) -> Tuple[bool, float]:
        """Check if JSON data is from Asana"""
        confidence = 0.0
        
        # Asana API response structure
        if 'data' in data:
            confidence += 0.3
            items = data.get('data', [])
            if isinstance(items, list) and len(items) > 0:
                item = items[0]
                if 'gid' in item:  # Asana's global ID
                    confidence += 0.4
                if 'resource_type' in item:
                    confidence += 0.2
        
        # Direct task list
        if isinstance(data, list) and len(data) > 0:
            item = data[0]
            if isinstance(item, dict):
                if 'gid' in item and ('name' in item or 'resource_type' in item):
                    confidence += 0.6
        
        return (confidence >= 0.5, min(confidence, 1.0))
    
    def _check_asana_csv(self, data: str) -> Tuple[bool, float]:
        """Check if CSV data is from Asana"""
        confidence = 0.0
        
        first_line = data.split('\n')[0].lower() if '\n' in data else data.lower()
        
        # Count Asana-specific patterns
        matches = sum(1 for pattern in self.ASANA_CSV_PATTERNS if pattern in first_line)
        
        if matches >= 4:
            confidence = 0.8
        elif matches >= 2:
            confidence = 0.5
        
        # Strong indicators
        if 'section/column' in first_line or 'task id' in first_line:
            confidence += 0.2
        
        return (confidence >= 0.5, min(confidence, 1.0))
    
    def parse(self, raw_data: Any) -> Dict[str, Any]:
        """Parse Asana export data"""
        if isinstance(raw_data, bytes):
            raw_data = raw_data.decode('utf-8')
        
        if isinstance(raw_data, str):
            data_stripped = raw_data.strip()
            if data_stripped.startswith('{') or data_stripped.startswith('['):
                return self._parse_json(raw_data)
            else:
                return self._parse_csv(raw_data)
        
        if isinstance(raw_data, dict):
            return {'format': 'json', 'data': raw_data}
        
        raise ImportError("Unsupported data type for Asana import")
    
    def _parse_json(self, data: str) -> Dict[str, Any]:
        """Parse Asana JSON"""
        try:
            json_data = json.loads(data)
            
            # Normalize to tasks array
            if 'data' in json_data:
                tasks = json_data['data']
            elif isinstance(json_data, list):
                tasks = json_data
            else:
                tasks = [json_data]
            
            return {'format': 'json', 'tasks': tasks}
            
        except json.JSONDecodeError as e:
            raise ImportError(f"Invalid JSON: {e}")
    
    def _parse_csv(self, data: str) -> Dict[str, Any]:
        """Parse Asana CSV"""
        try:
            reader = csv.DictReader(io.StringIO(data))
            rows = list(reader)
            headers = reader.fieldnames or []
            
            return {
                'format': 'csv',
                'headers': headers,
                'rows': rows,
            }
        except csv.Error as e:
            raise ImportError(f"CSV parsing error: {e}")
    
    def validate(self, parsed_data: Dict[str, Any]) -> bool:
        """Validate Asana export structure"""
        fmt = parsed_data.get('format')
        
        if fmt == 'json':
            tasks = parsed_data.get('tasks', [])
            if not tasks:
                raise ImportError("No tasks found in Asana JSON")
        
        elif fmt == 'csv':
            rows = parsed_data.get('rows', [])
            if not rows:
                raise ImportError("No data rows in Asana CSV")
        
        else:
            raise ImportError(f"Unknown format: {fmt}")
        
        return True
    
    def transform_to_prizmAI(self, parsed_data: Dict[str, Any]) -> ImportResult:
        """Transform Asana export to PrizmAI format"""
        result = ImportResult(
            source_format=parsed_data.get('format', 'unknown'),
            source_tool='Asana'
        )
        
        fmt = parsed_data.get('format')
        
        if fmt == 'json':
            self._transform_json(parsed_data['tasks'], result)
        elif fmt == 'csv':
            self._transform_csv(parsed_data['rows'], result)
        
        # Set board metadata
        result.board_data = {
            'name': 'Imported from Asana',
            'description': f'Imported {len(result.tasks_data)} tasks from Asana',
        }
        
        return result
    
    def _transform_json(self, tasks: List[Dict], result: ImportResult):
        """Transform Asana JSON tasks"""
        columns_seen = {}
        labels_seen = {}
        
        for idx, task in enumerate(tasks):
            # Skip subtasks at top level (they'll be linked to parents)
            if task.get('parent'):
                continue
            
            # Get section/column
            section = self._extract_section(task)
            column_name = self.SECTION_TO_COLUMN.get(section.lower(), section) if section else 'To Do'
            
            if column_name not in columns_seen:
                columns_seen[column_name] = {
                    'order': len(columns_seen),
                    'temp_id': f'col_{len(columns_seen)}',
                }
            
            # Get tags as labels
            label_names = []
            for tag in task.get('tags', []):
                tag_name = tag.get('name') if isinstance(tag, dict) else str(tag)
                if tag_name:
                    label_names.append(tag_name)
                    if tag_name not in labels_seen:
                        labels_seen[tag_name] = self._extract_tag_color(tag)
            
            # Get assignee
            assignee_obj = task.get('assignee', {})
            assignee = None
            if isinstance(assignee_obj, dict):
                assignee = assignee_obj.get('email') or assignee_obj.get('name')
            
            # Calculate progress
            progress = 100 if task.get('completed') else 0
            
            # Build task data
            task_data = {
                'title': self._sanitize_string(task.get('name', 'Untitled'), max_length=200),
                'description': task.get('notes', '') or '',
                'column_temp_id': columns_seen[column_name]['temp_id'],
                'position': idx,
                'priority': self._determine_priority(task),
                'progress': progress,
                'due_date': self._parse_date(task.get('due_on') or task.get('due_at')),
                'start_date': self._parse_date(task.get('start_on') or task.get('created_at')),
                'assigned_to_username': assignee,
                'label_names': label_names,
                'external_id': task.get('gid') or task.get('id'),
                'complexity_score': self._estimate_complexity(task),
            }
            
            result.tasks_data.append(task_data)
            result.update_stats('tasks_imported')
        
        # Build columns and labels
        for col_name, col_info in sorted(columns_seen.items(), key=lambda x: x[1]['order']):
            result.columns_data.append({
                'name': col_name,
                'position': col_info['order'],
                'temp_id': col_info['temp_id'],
            })
            result.update_stats('columns_imported')
        
        for label_name, color in labels_seen.items():
            result.labels_data.append({
                'name': label_name,
                'color': color,
            })
            result.update_stats('labels_imported')
    
    def _transform_csv(self, rows: List[Dict], result: ImportResult):
        """Transform Asana CSV rows"""
        columns_seen = {}
        labels_seen = {}
        
        for idx, row in enumerate(rows):
            # Normalize keys
            row_lower = {k.lower(): v for k, v in row.items()}
            
            # Get title
            title = row_lower.get('name') or row_lower.get('task name') or f'Task {idx + 1}'
            
            # Get section/column
            section = row_lower.get('section/column', '') or row_lower.get('section', '') or 'To Do'
            # Clean section name (Asana adds ":" suffix)
            section = section.rstrip(':').strip()
            column_name = self.SECTION_TO_COLUMN.get(section.lower(), section) if section else 'To Do'
            
            if column_name not in columns_seen:
                columns_seen[column_name] = {
                    'order': len(columns_seen),
                    'temp_id': f'col_{len(columns_seen)}',
                }
            
            # Get tags as labels
            label_names = []
            tags_raw = row_lower.get('tags', '')
            if tags_raw:
                for tag in str(tags_raw).split(','):
                    tag = tag.strip()
                    if tag:
                        label_names.append(tag)
                        if tag not in labels_seen:
                            labels_seen[tag] = self._generate_label_color(len(labels_seen))
            
            # Determine completion status
            completed = row_lower.get('completed at', '').strip() != ''
            progress = 100 if completed else 0
            
            # Build task data
            task_data = {
                'title': self._sanitize_string(title, max_length=200),
                'description': row_lower.get('notes', '') or row_lower.get('description', ''),
                'column_temp_id': columns_seen[column_name]['temp_id'],
                'position': idx,
                'priority': 'medium',  # Asana CSV doesn't typically include priority
                'progress': progress,
                'due_date': self._parse_date(row_lower.get('due date')),
                'start_date': self._parse_date(row_lower.get('start date') or row_lower.get('created at')),
                'assigned_to_username': row_lower.get('assignee'),
                'label_names': label_names,
                'external_id': row_lower.get('task id'),
            }
            
            result.tasks_data.append(task_data)
            result.update_stats('tasks_imported')
        
        # Build columns and labels
        for col_name, col_info in sorted(columns_seen.items(), key=lambda x: x[1]['order']):
            result.columns_data.append({
                'name': col_name,
                'position': col_info['order'],
                'temp_id': col_info['temp_id'],
            })
            result.update_stats('columns_imported')
        
        for label_name, color in labels_seen.items():
            result.labels_data.append({
                'name': label_name,
                'color': color,
            })
            result.update_stats('labels_imported')
    
    def _extract_section(self, task: Dict) -> str:
        """Extract section name from Asana task"""
        # Check memberships for section
        for membership in task.get('memberships', []):
            section = membership.get('section', {})
            if isinstance(section, dict) and section.get('name'):
                return section['name']
        
        return 'To Do'
    
    def _extract_tag_color(self, tag: Any) -> str:
        """Extract or generate color for Asana tag"""
        if isinstance(tag, dict):
            color = tag.get('color')
            if color:
                # Asana color names
                color_map = {
                    'dark-pink': '#ea4e9d',
                    'dark-green': '#62d26f',
                    'dark-blue': '#4186e0',
                    'dark-red': '#e8384f',
                    'dark-teal': '#4ecbc4',
                    'dark-brown': '#a6754e',
                    'dark-orange': '#fd612c',
                    'dark-purple': '#7a6ff0',
                    'dark-warm-gray': '#8da3a6',
                    'light-pink': '#f9aaef',
                    'light-green': '#b4f0a7',
                    'light-blue': '#9ee7e3',
                    'light-red': '#f1b5b5',
                    'light-teal': '#c7f5f5',
                    'light-yellow': '#fce28a',
                    'light-orange': '#fdc87c',
                    'light-purple': '#d4c3fb',
                    'light-warm-gray': '#d0d8db',
                }
                return color_map.get(color, '#808080')
        
        return '#808080'
    
    def _determine_priority(self, task: Dict) -> str:
        """Determine priority from Asana task fields"""
        # Check custom fields for priority
        for field in task.get('custom_fields', []):
            if isinstance(field, dict):
                field_name = field.get('name', '').lower()
                if 'priority' in field_name:
                    value = field.get('display_value') or field.get('text_value', '')
                    return self._normalize_priority(value)
        
        # Check if task has due date (might indicate higher priority)
        if task.get('due_on') or task.get('due_at'):
            return 'medium'
        
        return 'medium'
    
    def _estimate_complexity(self, task: Dict) -> int:
        """Estimate complexity from Asana task"""
        complexity = 5
        
        # Check custom fields for story points or effort
        for field in task.get('custom_fields', []):
            if isinstance(field, dict):
                field_name = field.get('name', '').lower()
                if 'point' in field_name or 'effort' in field_name or 'complexity' in field_name:
                    value = field.get('number_value')
                    if value is not None:
                        return max(1, min(10, int(value)))
        
        # Estimate based on subtasks
        subtasks = task.get('subtasks', [])
        if isinstance(subtasks, list):
            if len(subtasks) > 10:
                complexity = 9
            elif len(subtasks) > 5:
                complexity = 7
            elif len(subtasks) > 2:
                complexity = 6
        
        return complexity
    
    def _generate_label_color(self, index: int) -> str:
        """Generate color for a label"""
        colors = [
            '#ea4e9d', '#62d26f', '#4186e0', '#e8384f', '#4ecbc4',
            '#a6754e', '#fd612c', '#7a6ff0', '#8da3a6', '#f2d600',
        ]
        return colors[index % len(colors)]
