"""
Trello Import Adapter
Handles import of Trello JSON export format.

Trello Export Structure:
- Board info in root (name, desc, id)
- lists[] - columns/lists
- cards[] - tasks with idList reference
- labels[] - board labels
- members[] - board members
- checklists[] - card checklists
- actions[] - activity/comments
"""

import json
from typing import Dict, Any, Tuple, List, Optional
from datetime import datetime

from .base_adapter import BaseImportAdapter, ImportResult, ImportError


class TrelloAdapter(BaseImportAdapter):
    """
    Adapter for Trello JSON exports.
    
    Trello exports can be obtained from:
    - Board Menu > More > Print and Export > Export as JSON
    - Via Trello API
    """
    
    name = "Trello Adapter"
    supported_extensions = ['json']
    source_tool = "Trello"
    
    # Trello-specific field mappings
    TRELLO_PRIORITY_LABELS = {
        'critical': 'urgent',
        'urgent': 'urgent',
        'high': 'high',
        'high priority': 'high',
        'medium': 'medium',
        'medium priority': 'medium',
        'low': 'low',
        'low priority': 'low',
    }
    
    def can_handle(self, data: Any, filename: str = None) -> Tuple[bool, float]:
        """
        Detect Trello export format.
        
        Trello exports have distinctive markers:
        - 'cards' array at root
        - 'lists' array at root
        - 'idOrganization' field
        - Card objects have 'idList', 'idBoard', 'idShort'
        """
        confidence = 0.0
        
        # Try to parse if string
        if isinstance(data, str):
            try:
                data = json.loads(data)
            except json.JSONDecodeError:
                return (False, 0.0)
        
        if not isinstance(data, dict):
            return (False, 0.0)
        
        # Check for Trello-specific root keys
        trello_markers = ['cards', 'lists', 'idOrganization', 'idBoard', 'prefs']
        found_markers = sum(1 for marker in trello_markers if marker in data)
        
        if found_markers >= 2:
            confidence += 0.4
        
        # Check for Trello URL pattern
        if 'url' in data and 'trello.com' in str(data.get('url', '')).lower():
            confidence += 0.3
        
        # Check card structure
        cards = data.get('cards', [])
        if isinstance(cards, list) and len(cards) > 0:
            card = cards[0]
            if isinstance(card, dict):
                trello_card_fields = ['idList', 'idBoard', 'idShort', 'idMembers']
                card_matches = sum(1 for f in trello_card_fields if f in card)
                if card_matches >= 2:
                    confidence += 0.3
        
        return (confidence >= 0.5, min(confidence, 1.0))
    
    def parse(self, raw_data: Any) -> Dict[str, Any]:
        """Parse Trello JSON export"""
        if isinstance(raw_data, dict):
            return raw_data
        
        if isinstance(raw_data, (str, bytes)):
            try:
                return json.loads(raw_data)
            except json.JSONDecodeError as e:
                raise ImportError(f"Invalid JSON: {e}")
        
        raise ImportError("Unsupported data type for parsing")
    
    def validate(self, parsed_data: Dict[str, Any]) -> bool:
        """Validate Trello export structure"""
        # Must have lists
        if 'lists' not in parsed_data:
            raise ImportError("Missing 'lists' key - not a valid Trello export", field='lists')
        
        # Must have cards (can be empty)
        if 'cards' not in parsed_data:
            raise ImportError("Missing 'cards' key - not a valid Trello export", field='cards')
        
        # Validate lists structure
        lists = parsed_data['lists']
        if not isinstance(lists, list):
            raise ImportError("'lists' must be an array", field='lists')
        
        for i, lst in enumerate(lists):
            if not isinstance(lst, dict):
                raise ImportError(f"List at index {i} is not an object", field='lists', row=i)
            if 'name' not in lst and 'id' not in lst:
                raise ImportError(f"List at index {i} missing 'name' or 'id'", field='lists', row=i)
        
        return True
    
    def transform_to_prizmAI(self, parsed_data: Dict[str, Any]) -> ImportResult:
        """Transform Trello export to PrizmAI format"""
        result = ImportResult(
            source_format='json',
            source_tool='Trello'
        )
        
        # Build lookup maps
        list_map = {}  # Trello list ID -> temp column ID
        label_map = {}  # Trello label ID -> label data
        member_map = {}  # Trello member ID -> member data
        checklist_map = {}  # Trello checklist ID -> card ID
        
        # Transform board metadata
        result.board_data = {
            'name': parsed_data.get('name', 'Imported from Trello'),
            'description': parsed_data.get('desc', ''),
            'external_id': parsed_data.get('id'),
            'external_url': parsed_data.get('url'),
        }
        
        # Transform labels
        for label in parsed_data.get('labels', []):
            if not label.get('name'):  # Skip unnamed labels
                continue
            
            label_data = {
                'name': label.get('name'),
                'color': self._extract_color(label.get('color')),
                'external_id': label.get('id'),
            }
            label_map[label.get('id')] = label_data
            result.labels_data.append(label_data)
            result.update_stats('labels_imported')
        
        # Transform members
        for member in parsed_data.get('members', []):
            member_data = {
                'external_id': member.get('id'),
                'username': member.get('username'),
                'full_name': member.get('fullName'),
                'avatar_url': member.get('avatarUrl'),
            }
            member_map[member.get('id')] = member_data
            result.users_data.append(member_data)
        
        # Transform lists (columns)
        # Filter out archived lists
        active_lists = [lst for lst in parsed_data.get('lists', []) if not lst.get('closed', False)]
        
        for col_idx, lst in enumerate(active_lists):
            col_temp_id = f'col_{lst.get("id", col_idx)}'
            list_map[lst.get('id')] = col_temp_id
            
            col_data = {
                'name': lst.get('name', f'Column {col_idx + 1}'),
                'position': lst.get('pos', col_idx),
                'temp_id': col_temp_id,
                'external_id': lst.get('id'),
            }
            result.columns_data.append(col_data)
            result.update_stats('columns_imported')
        
        # Transform checklists (build map)
        for checklist in parsed_data.get('checklists', []):
            card_id = checklist.get('idCard')
            if card_id not in checklist_map:
                checklist_map[card_id] = []
            
            checklist_data = {
                'name': checklist.get('name', 'Checklist'),
                'items': [],
            }
            
            for item in checklist.get('checkItems', []):
                checklist_data['items'].append({
                    'name': item.get('name', ''),
                    'completed': item.get('state') == 'complete',
                    'position': item.get('pos', 0),
                })
            
            checklist_map[card_id].append(checklist_data)
        
        # Transform cards (tasks)
        # Filter out archived cards
        active_cards = [card for card in parsed_data.get('cards', []) if not card.get('closed', False)]
        
        # Sort cards by list and position
        active_cards.sort(key=lambda c: (c.get('idList', ''), c.get('pos', 0)))
        
        for task_idx, card in enumerate(active_cards):
            task_data = self._transform_card(
                card, 
                list_map, 
                label_map, 
                member_map, 
                checklist_map,
                task_idx
            )
            
            if task_data:
                result.tasks_data.append(task_data)
                result.update_stats('tasks_imported')
            else:
                result.add_warning(f"Skipped card '{card.get('name', 'Unknown')}' - no valid list")
        
        # Extract comments from actions
        result.comments_data = self._extract_comments(parsed_data.get('actions', []), member_map)
        result.update_stats('comments_imported', len(result.comments_data))
        
        return result
    
    def _transform_card(self, card: Dict, list_map: Dict, label_map: Dict,
                        member_map: Dict, checklist_map: Dict, position: int) -> Optional[Dict[str, Any]]:
        """Transform a Trello card to PrizmAI task"""
        
        # Get column reference
        list_id = card.get('idList')
        if list_id not in list_map:
            return None  # Card's list was archived
        
        # Determine priority from labels
        priority = 'medium'
        label_names = []
        
        for label_id in card.get('idLabels', []):
            if label_id in label_map:
                label_data = label_map[label_id]
                label_name = label_data.get('name', '')
                label_names.append(label_name)
                
                # Check if this is a priority label
                priority_match = self.TRELLO_PRIORITY_LABELS.get(label_name.lower())
                if priority_match:
                    priority = priority_match
        
        # Get assigned members
        assigned_usernames = []
        for member_id in card.get('idMembers', []):
            if member_id in member_map:
                username = member_map[member_id].get('username')
                if username:
                    assigned_usernames.append(username)
        
        # Calculate progress from checklists
        progress = 0
        checklists = checklist_map.get(card.get('id'), [])
        if checklists:
            total_items = 0
            completed_items = 0
            for cl in checklists:
                for item in cl.get('items', []):
                    total_items += 1
                    if item.get('completed'):
                        completed_items += 1
            if total_items > 0:
                progress = int((completed_items / total_items) * 100)
        
        # Build task data
        task_data = {
            'title': self._sanitize_string(card.get('name', 'Untitled'), max_length=200),
            'description': card.get('desc', ''),
            'column_temp_id': list_map[list_id],
            'position': card.get('pos', position),
            'priority': priority,
            'progress': progress,
            'due_date': self._parse_date(card.get('due')),
            'start_date': self._parse_date(card.get('start')),
            'label_names': label_names,
            'assigned_to_usernames': assigned_usernames,
            'assigned_to_username': assigned_usernames[0] if assigned_usernames else None,
            'checklists': checklists,
            'external_id': card.get('id'),
            'external_short_id': card.get('idShort'),
            'external_url': card.get('url'),
            
            # Additional Trello-specific data preserved
            'metadata': {
                'trello_badges': card.get('badges', {}),
                'is_template': card.get('isTemplate', False),
                'cover': card.get('cover', {}),
            }
        }
        
        # Extract attachments info (URLs only, not downloading)
        attachments = card.get('attachments', [])
        if attachments:
            task_data['attachments'] = [{
                'name': att.get('name', 'attachment'),
                'url': att.get('url'),
                'mime_type': att.get('mimeType'),
            } for att in attachments]
        
        return task_data
    
    def _extract_comments(self, actions: List[Dict], member_map: Dict) -> List[Dict[str, Any]]:
        """Extract comments from Trello actions"""
        comments = []
        
        for action in actions:
            if action.get('type') != 'commentCard':
                continue
            
            action_data = action.get('data', {})
            card_data = action_data.get('card', {})
            
            member_creator = action.get('memberCreator', {})
            username = member_creator.get('username', 'Unknown')
            
            comment = {
                'task_external_id': card_data.get('id'),
                'author_username': username,
                'author_full_name': member_creator.get('fullName'),
                'text': action_data.get('text', ''),
                'created_at': self._parse_date(action.get('date')),
                'external_id': action.get('id'),
            }
            comments.append(comment)
        
        return comments
    
    def _extract_color(self, trello_color: str) -> str:
        """Convert Trello color names to hex codes"""
        if not trello_color:
            return '#808080'
        
        # Trello's color palette
        trello_colors = {
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
            'green_dark': '#519839',
            'yellow_dark': '#d9b51c',
            'orange_dark': '#cd8313',
            'red_dark': '#b04632',
            'purple_dark': '#89609e',
            'blue_dark': '#055a8c',
            'sky_dark': '#096faf',
            'lime_dark': '#4bbf6b',
            'pink_dark': '#e568af',
            'black_dark': '#505f79',
            'green_light': '#b3f1bf',
            'yellow_light': '#fdfad1',
            'orange_light': '#ffefd5',
            'red_light': '#ffcccb',
            'purple_light': '#e8d5f0',
            'blue_light': '#bcdffb',
            'sky_light': '#bcf3ff',
            'lime_light': '#d0ffd0',
            'pink_light': '#ffd0e8',
            'black_light': '#dfe1e6',
        }
        
        return trello_colors.get(trello_color.lower(), '#808080')
