"""
Script to recreate retrospective action items with meaningful titles
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'kanban_board.settings')
django.setup()

from django.utils import timezone
from datetime import timedelta
from kanban.models import Board
from kanban.retrospective_models import ProjectRetrospective, RetrospectiveActionItem
from django.contrib.auth import get_user_model

User = get_user_model()

def recreate_action_items():
    # Get users
    sam = User.objects.filter(username='sam_rivera_demo').first()
    jordan = User.objects.filter(username='jordan_taylor_demo').first()
    alex = User.objects.filter(username='alex_chen_demo').first()
    
    if not all([sam, jordan, alex]):
        print("Users not found")
        return
    
    # Action items by board type
    action_items_by_board = {
        'Software Development Sprint': [
            {
                'title': 'Implement automated code review checklist',
                'description': 'Create and integrate automated checklist for code reviews to ensure consistent quality standards',
                'action_type': 'process_change',
                'priority': 'high'
            },
            {
                'title': 'Reduce technical debt in authentication module',
                'description': 'Allocate 20% of sprint capacity to refactor and document authentication code',
                'action_type': 'technical_improvement',
                'priority': 'medium'
            }
        ],
        'Marketing Campaign Review': [
            {
                'title': 'Improve campaign performance tracking',
                'description': 'Set up automated dashboards for real-time campaign metrics and ROI tracking',
                'action_type': 'tool_adoption',
                'priority': 'high'
            },
            {
                'title': 'Enhance team collaboration on content creation',
                'description': 'Schedule weekly brainstorming sessions and implement shared content calendar',
                'action_type': 'team_building',
                'priority': 'medium'
            }
        ],
        'Bug Fix Retrospective': [
            {
                'title': 'Establish bug triage process',
                'description': 'Create priority matrix and daily triage meetings to handle critical bugs faster',
                'action_type': 'process_change',
                'priority': 'high'
            },
            {
                'title': 'Improve bug documentation standards',
                'description': 'Create bug report template with reproduction steps and impact assessment',
                'action_type': 'documentation',
                'priority': 'medium'
            }
        ]
    }
    
    # Find retrospectives without good action items
    retros = ProjectRetrospective.objects.all()
    
    for retro in retros:
        # Determine action items based on title
        action_items = None
        for board_type, items in action_items_by_board.items():
            if board_type in retro.title:
                action_items = items
                break
        
        if not action_items:
            action_items = [
                {
                    'title': 'Implement process improvements',
                    'description': 'Follow up on retrospective discussion and implement agreed changes',
                    'action_type': 'process_change',
                    'priority': 'high'
                }
            ]
        
        # Create the action items
        for idx, action_data in enumerate(action_items):
            days_offset = 14 if action_data['priority'] == 'high' else 30
            
            # Check if this action already exists
            existing = RetrospectiveActionItem.objects.filter(
                retrospective=retro,
                title=action_data['title']
            ).first()
            
            if not existing:
                RetrospectiveActionItem.objects.create(
                    retrospective=retro,
                    board=retro.board,
                    title=action_data['title'],
                    description=action_data['description'],
                    action_type=action_data['action_type'],
                    assigned_to=sam if idx == 0 else (jordan if idx == 1 else alex),
                    target_completion_date=(timezone.now() + timedelta(days=days_offset)).date(),
                    priority=action_data['priority'],
                    status='in_progress' if idx == 0 else 'pending',
                    expected_impact=f'Improve team efficiency and {retro.board.name.lower()} outcomes'
                )
                print(f"Created action item: {action_data['title']} for {retro.title}")
            else:
                print(f"Action item already exists: {action_data['title']}")

if __name__ == '__main__':
    recreate_action_items()
    print("\nDone! Action items recreated.")
