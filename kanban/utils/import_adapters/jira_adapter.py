"""
Jira Import Adapter
Handles import of Jira CSV and JSON export formats.

Jira Export Formats:
- CSV: Exported via Issues > Export > CSV (all fields)
- JSON: Via Jira REST API or third-party tools
- XML: Jira's native export format (less common)

Jira-specific fields:
- Issue Key (e.g., PROJ-123)
- Issue Type (Story, Bug, Task, Epic, etc.)
- Status (maps to columns)
- Priority (Highest, High, Medium, Low, Lowest)
- Resolution
- Sprint
- Story Points
- Components
- Fix Versions
"""

import json
import csv
import io
from typing import Dict, Any, Tuple, List, Optional

from .base_adapter import BaseImportAdapter, ImportResult, ImportError


class JiraAdapter(BaseImportAdapter):
    """
    Adapter for Jira exports (CSV and JSON).
    
    Supports:
    - Jira CSV export (most common)
    - Jira JSON (from API)
    - Confluence/Jira Cloud exports
    """
    
    name = "Jira Adapter"
    supported_extensions = ['csv', 'json']
    source_tool = "Jira"
    
    # Jira status to column mapping
    STATUS_TO_COLUMN = {
        'open': 'To Do',
        'to do': 'To Do',
        'backlog': 'Backlog',
        'selected for development': 'To Do',
        'in progress': 'In Progress',
        'in development': 'In Progress',
        'in review': 'In Review',
        'code review': 'In Review',
        'testing': 'Testing',
        'in qa': 'Testing',
        'qa': 'Testing',
        'done': 'Done',
        'closed': 'Done',
        'resolved': 'Done',
        'complete': 'Done',
        'released': 'Done',
    }
    
    # Jira priority mapping
    PRIORITY_MAP = {
        'highest': 'urgent',
        'blocker': 'urgent',
        'critical': 'urgent',
        'high': 'high',
        'major': 'high',
        'medium': 'medium',
        'normal': 'medium',
        'low': 'low',
        'minor': 'low',
        'lowest': 'low',
        'trivial': 'low',
    }
    
    # Jira CSV column name patterns
    JIRA_CSV_PATTERNS = [
        'issue key', 'issue id', 'summary', 'issue type', 'status',
        'priority', 'assignee', 'reporter', 'created', 'updated',
        'resolved', 'sprint', 'story points', 'epic link', 'epic name',
        'fix version', 'component', 'labels', 'parent'
    ]
    
    def can_handle(self, data: Any, filename: str = None) -> Tuple[bool, float]:
        """
        Detect Jira export format.
        
        Jira JSON has:
        - 'issues' array with 'key', 'fields' structure
        - Issue fields have 'issuetype', 'status', 'priority' objects
        
        Jira CSV has:
        - 'Issue Key', 'Summary', 'Status', 'Issue Type' columns
        """
        confidence = 0.0
        
        # Check if it's JSON
        if isinstance(data, str):
            data_stripped = data.strip()
            if data_stripped.startswith('{') or data_stripped.startswith('['):
                try:
                    json_data = json.loads(data)
                    return self._check_jira_json(json_data)
                except json.JSONDecodeError:
                    pass
            else:
                # Check CSV
                return self._check_jira_csv(data)
        
        if isinstance(data, dict):
            return self._check_jira_json(data)
        
        if isinstance(data, bytes):
            try:
                decoded = data.decode('utf-8')
                return self.can_handle(decoded, filename)
            except UnicodeDecodeError:
                return (False, 0.0)
        
        return (False, 0.0)
    
    def _check_jira_json(self, data: Dict) -> Tuple[bool, float]:
        """Check if JSON data is from Jira"""
        confidence = 0.0
        
        # Check for Jira API response structure
        if 'issues' in data:
            confidence += 0.4
            issues = data.get('issues', [])
            if issues and len(issues) > 0:
                issue = issues[0]
                if 'key' in issue and 'fields' in issue:
                    confidence += 0.3
                    fields = issue.get('fields', {})
                    if 'issuetype' in fields or 'status' in fields:
                        confidence += 0.2
        
        # Check for single issue structure
        if 'key' in data and 'fields' in data:
            confidence += 0.5
            fields = data.get('fields', {})
            if 'issuetype' in fields:
                confidence += 0.3
        
        return (confidence >= 0.5, min(confidence, 1.0))
    
    def _check_jira_csv(self, data: str) -> Tuple[bool, float]:
        """Check if CSV data is from Jira"""
        confidence = 0.0
        
        # Get first line (headers)
        first_line = data.split('\n')[0].lower() if '\n' in data else data.lower()
        
        # Count Jira-specific column patterns
        matches = sum(1 for pattern in self.JIRA_CSV_PATTERNS if pattern in first_line)
        
        if matches >= 4:
            confidence = 0.8
        elif matches >= 2:
            confidence = 0.5
        
        # Strong indicators
        if 'issue key' in first_line or 'issue id' in first_line:
            confidence += 0.2
        
        return (confidence >= 0.5, min(confidence, 1.0))
    
    def parse(self, raw_data: Any) -> Dict[str, Any]:
        """Parse Jira export data"""
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
        
        raise ImportError("Unsupported data type for Jira import")
    
    def _parse_json(self, data: str) -> Dict[str, Any]:
        """Parse Jira JSON"""
        try:
            json_data = json.loads(data)
            
            # Normalize to issues array
            if 'issues' in json_data:
                issues = json_data['issues']
            elif isinstance(json_data, list):
                issues = json_data
            elif 'key' in json_data and 'fields' in json_data:
                issues = [json_data]  # Single issue
            else:
                raise ImportError("Could not find issues in Jira JSON")
            
            return {'format': 'json', 'issues': issues}
            
        except json.JSONDecodeError as e:
            raise ImportError(f"Invalid JSON: {e}")
    
    def _parse_csv(self, data: str) -> Dict[str, Any]:
        """Parse Jira CSV"""
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
        """Validate Jira export structure"""
        fmt = parsed_data.get('format')
        
        if fmt == 'json':
            issues = parsed_data.get('issues', [])
            if not issues:
                raise ImportError("No issues found in Jira JSON")
            
            # Validate first issue structure
            issue = issues[0]
            if 'key' not in issue and 'id' not in issue:
                raise ImportError("Jira issues must have 'key' or 'id'")
        
        elif fmt == 'csv':
            rows = parsed_data.get('rows', [])
            if not rows:
                raise ImportError("No data rows in Jira CSV")
            
            headers = [h.lower() for h in parsed_data.get('headers', [])]
            if 'summary' not in headers and 'issue key' not in headers:
                raise ImportError("Jira CSV must have 'Summary' or 'Issue Key' column")
        
        else:
            raise ImportError(f"Unknown format: {fmt}")
        
        return True
    
    def transform_to_prizmAI(self, parsed_data: Dict[str, Any]) -> ImportResult:
        """Transform Jira export to PrizmAI format"""
        result = ImportResult(
            source_format=parsed_data.get('format', 'unknown'),
            source_tool='Jira'
        )
        
        fmt = parsed_data.get('format')
        
        if fmt == 'json':
            self._transform_json(parsed_data['issues'], result)
        elif fmt == 'csv':
            self._transform_csv(parsed_data['rows'], result)
        
        # Set board metadata
        result.board_data = {
            'name': 'Imported from Jira',
            'description': f'Imported {len(result.tasks_data)} issues from Jira',
        }
        
        return result
    
    def _transform_json(self, issues: List[Dict], result: ImportResult):
        """Transform Jira JSON issues"""
        columns_seen = {}
        labels_seen = {}
        
        for idx, issue in enumerate(issues):
            fields = issue.get('fields', {})
            
            # Get status/column
            status_obj = fields.get('status', {})
            status_name = status_obj.get('name', 'To Do') if isinstance(status_obj, dict) else str(status_obj)
            column_name = self.STATUS_TO_COLUMN.get(status_name.lower(), status_name)
            
            if column_name not in columns_seen:
                columns_seen[column_name] = {
                    'order': len(columns_seen),
                    'temp_id': f'col_{len(columns_seen)}',
                }
            
            # Get priority
            priority_obj = fields.get('priority', {})
            priority_name = priority_obj.get('name', 'Medium') if isinstance(priority_obj, dict) else 'Medium'
            priority = self.PRIORITY_MAP.get(priority_name.lower(), 'medium')
            
            # Get labels
            label_names = []
            for label in fields.get('labels', []):
                label_name = label if isinstance(label, str) else str(label)
                label_names.append(label_name)
                if label_name not in labels_seen:
                    labels_seen[label_name] = self._extract_color(None)
            
            # Get issue type as label
            issue_type = fields.get('issuetype', {})
            type_name = issue_type.get('name') if isinstance(issue_type, dict) else None
            if type_name and type_name not in label_names:
                label_names.append(type_name)
                if type_name not in labels_seen:
                    labels_seen[type_name] = self._get_issue_type_color(type_name)
            
            # Get assignee
            assignee_obj = fields.get('assignee', {})
            assignee = None
            if isinstance(assignee_obj, dict):
                assignee = assignee_obj.get('emailAddress') or assignee_obj.get('displayName')
            
            # Build task
            task_data = {
                'title': self._sanitize_string(fields.get('summary', 'Untitled'), max_length=200),
                'description': fields.get('description', '') or '',
                'column_temp_id': columns_seen[column_name]['temp_id'],
                'position': idx,
                'priority': priority,
                'progress': self._calculate_progress(status_name),
                'due_date': self._parse_date(fields.get('duedate')),
                'start_date': self._parse_date(fields.get('created')),
                'assigned_to_username': assignee,
                'label_names': label_names,
                'external_id': issue.get('key') or issue.get('id'),
                'complexity_score': self._normalize_story_points(fields.get('customfield_10016')),  # Story Points
                'metadata': {
                    'jira_key': issue.get('key'),
                    'issue_type': type_name,
                    'sprint': self._extract_sprint(fields),
                    'epic_link': fields.get('epic', {}).get('key') if isinstance(fields.get('epic'), dict) else None,
                }
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
        """Transform Jira CSV rows"""
        columns_seen = {}
        labels_seen = {}
        
        for idx, row in enumerate(rows):
            # Normalize keys to lowercase for easier access
            row_lower = {k.lower(): v for k, v in row.items()}
            
            # Get title
            title = (row_lower.get('summary') or 
                    row_lower.get('issue key') or 
                    f'Issue {idx + 1}')
            
            # Get status/column
            status = row_lower.get('status', 'To Do')
            column_name = self.STATUS_TO_COLUMN.get(status.lower(), status)
            
            if column_name not in columns_seen:
                columns_seen[column_name] = {
                    'order': len(columns_seen),
                    'temp_id': f'col_{len(columns_seen)}',
                }
            
            # Get priority
            priority_raw = row_lower.get('priority', 'Medium')
            priority = self.PRIORITY_MAP.get(priority_raw.lower(), 'medium')
            
            # Get labels
            label_names = []
            labels_raw = row_lower.get('labels', '')
            if labels_raw:
                for label in str(labels_raw).split(','):
                    label = label.strip()
                    if label:
                        label_names.append(label)
                        if label not in labels_seen:
                            labels_seen[label] = self._extract_color(None)
            
            # Add issue type as label
            issue_type = row_lower.get('issue type', '')
            if issue_type and issue_type not in label_names:
                label_names.append(issue_type)
                if issue_type not in labels_seen:
                    labels_seen[issue_type] = self._get_issue_type_color(issue_type)
            
            # Build task
            task_data = {
                'title': self._sanitize_string(title, max_length=200),
                'description': row_lower.get('description', ''),
                'column_temp_id': columns_seen[column_name]['temp_id'],
                'position': idx,
                'priority': priority,
                'progress': self._calculate_progress(status),
                'due_date': self._parse_date(row_lower.get('due date') or row_lower.get('due')),
                'start_date': self._parse_date(row_lower.get('created')),
                'assigned_to_username': row_lower.get('assignee'),
                'label_names': label_names,
                'external_id': row_lower.get('issue key') or row_lower.get('issue id'),
                'complexity_score': self._normalize_story_points(row_lower.get('story points')),
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
    
    def _calculate_progress(self, status: str) -> int:
        """Estimate progress based on status"""
        status_lower = status.lower()
        
        if status_lower in ['done', 'closed', 'resolved', 'complete', 'released']:
            return 100
        elif status_lower in ['in review', 'code review', 'testing', 'qa', 'in qa']:
            return 75
        elif status_lower in ['in progress', 'in development']:
            return 50
        elif status_lower in ['selected for development']:
            return 10
        else:
            return 0
    
    def _normalize_story_points(self, value: Any) -> int:
        """Normalize story points to complexity score (1-10)"""
        if not value:
            return 5
        
        try:
            points = float(value)
            # Fibonacci to 1-10 mapping
            if points <= 1:
                return 1
            elif points <= 2:
                return 2
            elif points <= 3:
                return 3
            elif points <= 5:
                return 5
            elif points <= 8:
                return 7
            elif points <= 13:
                return 9
            else:
                return 10
        except (ValueError, TypeError):
            return 5
    
    def _extract_sprint(self, fields: Dict) -> Optional[str]:
        """Extract sprint name from Jira fields"""
        sprint_field = fields.get('sprint', [])
        if not sprint_field:
            # Try common custom field for sprints
            sprint_field = fields.get('customfield_10020', [])
        
        if isinstance(sprint_field, list) and sprint_field:
            sprint = sprint_field[0]
            if isinstance(sprint, dict):
                return sprint.get('name')
            elif isinstance(sprint, str):
                # Parse sprint string format: "com.atlassian.greenhopper.service.sprint.Sprint@xyz[id=123,name=Sprint 1,...]"
                if 'name=' in sprint:
                    start = sprint.find('name=') + 5
                    end = sprint.find(',', start)
                    if end == -1:
                        end = sprint.find(']', start)
                    if end > start:
                        return sprint[start:end]
                return sprint
        
        return None
    
    def _get_issue_type_color(self, issue_type: str) -> str:
        """Get color for Jira issue type"""
        type_colors = {
            'bug': '#eb5a46',      # Red
            'story': '#61bd4f',    # Green
            'task': '#0079bf',     # Blue
            'epic': '#c377e0',     # Purple
            'subtask': '#00c2e0',  # Sky
            'improvement': '#f2d600',  # Yellow
            'feature': '#51e898',  # Lime
        }
        return type_colors.get(issue_type.lower(), '#808080')
