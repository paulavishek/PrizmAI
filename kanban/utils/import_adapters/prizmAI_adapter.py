"""
PrizmAI Native Adapter
Handles import of PrizmAI's own JSON export format.
"""

import json
from typing import Dict, Any, Tuple, List

from .base_adapter import BaseImportAdapter, ImportResult, ImportError


class PrizmAIAdapter(BaseImportAdapter):
    """
    Adapter for PrizmAI's native JSON export format.
    This is the simplest adapter as no transformation is needed.
    """
    
    name = "PrizmAI Native Adapter"
    supported_extensions = ['json']
    source_tool = "PrizmAI"
    
    def can_handle(self, data: Any, filename: str = None) -> Tuple[bool, float]:
        """
        Check if this is a PrizmAI native export.
        
        PrizmAI exports have a specific structure:
        - 'board' key with board metadata
        - 'columns' key with column data
        - Optional: 'tasks' at root level or nested in columns
        """
        confidence = 0.0
        
        # Check filename extension
        if filename and filename.lower().endswith('.json'):
            confidence += 0.1
        
        # Try to parse if string
        if isinstance(data, str):
            try:
                data = json.loads(data)
            except json.JSONDecodeError:
                return (False, 0.0)
        
        if not isinstance(data, dict):
            return (False, 0.0)
        
        # Check for PrizmAI-specific structure
        if 'board' in data and 'columns' in data:
            confidence += 0.5
            
            # Check for PrizmAI-specific fields in board
            board = data.get('board', {})
            if isinstance(board, dict):
                prizmAI_fields = ['name', 'description', 'organization']
                for field in prizmAI_fields:
                    if field in board:
                        confidence += 0.1
                
                # Definite PrizmAI marker
                if 'is_official_demo_board' in board or 'num_phases' in board:
                    confidence = 1.0
        
        return (confidence >= 0.5, min(confidence, 1.0))
    
    def parse(self, raw_data: Any) -> Dict[str, Any]:
        """Parse JSON data"""
        if isinstance(raw_data, dict):
            return raw_data
        
        if isinstance(raw_data, (str, bytes)):
            try:
                return json.loads(raw_data)
            except json.JSONDecodeError as e:
                raise ImportError(f"Invalid JSON: {e}")
        
        raise ImportError("Unsupported data type for parsing")
    
    def validate(self, parsed_data: Dict[str, Any]) -> bool:
        """Validate PrizmAI export structure"""
        if 'board' not in parsed_data:
            raise ImportError("Missing 'board' key in import data", field='board')
        
        if 'columns' not in parsed_data:
            raise ImportError("Missing 'columns' key in import data", field='columns')
        
        board = parsed_data['board']
        if not isinstance(board, dict):
            raise ImportError("'board' must be an object", field='board')
        
        if 'name' not in board:
            raise ImportError("Board must have a 'name'", field='board.name')
        
        columns = parsed_data['columns']
        if not isinstance(columns, list):
            raise ImportError("'columns' must be an array", field='columns')
        
        return True
    
    def transform_to_prizmAI(self, parsed_data: Dict[str, Any]) -> ImportResult:
        """
        Transform PrizmAI export to import format.
        Mostly passthrough with normalization.
        """
        result = ImportResult(
            source_format='json',
            source_tool='PrizmAI'
        )
        
        # Board data
        board = parsed_data['board']
        result.board_data = {
            'name': board.get('name', 'Imported Board'),
            'description': board.get('description', ''),
            'num_phases': board.get('num_phases', 0),
        }
        
        # Columns and tasks
        all_tasks = []
        all_labels = {}
        
        for col_idx, column in enumerate(parsed_data['columns']):
            col_data = {
                'name': column.get('name', f'Column {col_idx + 1}'),
                'position': column.get('position', col_idx),
                'wip_limit': column.get('wip_limit'),
                'temp_id': f'col_{col_idx}',
            }
            result.columns_data.append(col_data)
            result.update_stats('columns_imported')
            
            # Process tasks in this column
            for task_idx, task in enumerate(column.get('tasks', [])):
                task_data = self._transform_task(task, col_data['temp_id'], task_idx, all_labels)
                all_tasks.append(task_data)
                result.update_stats('tasks_imported')
        
        result.tasks_data = all_tasks
        result.labels_data = list(all_labels.values())
        result.update_stats('labels_imported', len(all_labels))
        
        return result
    
    def _transform_task(self, task: Dict, column_temp_id: str, position: int, 
                        labels_registry: Dict) -> Dict[str, Any]:
        """Transform a single task"""
        task_data = {
            'title': task.get('title', 'Untitled Task'),
            'description': task.get('description', ''),
            'column_temp_id': column_temp_id,
            'position': task.get('position', position),
            'priority': self._normalize_priority(task.get('priority')),
            'progress': self._normalize_progress(task.get('progress')),
            'start_date': self._parse_date(task.get('start_date')),
            'due_date': self._parse_date(task.get('due_date')),
            'assigned_to_username': task.get('assigned_to'),
            'complexity_score': task.get('complexity_score', 5),
            'phase': task.get('phase'),
            'label_names': [],
        }
        
        # Process labels
        for label in task.get('labels', []):
            if isinstance(label, str):
                label_name = label
                label_color = '#FF5733'
            elif isinstance(label, dict):
                label_name = label.get('name', 'Unknown')
                label_color = self._extract_color(label.get('color'))
            else:
                continue
            
            task_data['label_names'].append(label_name)
            
            if label_name not in labels_registry:
                labels_registry[label_name] = {
                    'name': label_name,
                    'color': label_color,
                }
        
        return task_data
