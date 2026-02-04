"""
Remove redundant action items across different retrospectives
Keep only the most recent action item for each unique (board, title, assignee) combination
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'kanban_board.settings')
django.setup()

from kanban.retrospective_models import RetrospectiveActionItem
from django.db.models import Max

print("Finding redundant action items...\n")

# Group by board, title, and assigned_to
# For each group, keep only the most recent one (latest created_at)
all_actions = RetrospectiveActionItem.objects.all()

# Group actions by (board_id, title, assigned_to_id)
action_groups = {}
for action in all_actions:
    key = (action.board_id, action.title, action.assigned_to_id)
    if key not in action_groups:
        action_groups[key] = []
    action_groups[key].append(action)

deleted_count = 0
kept_count = 0

for key, actions in action_groups.items():
    if len(actions) > 1:
        # Sort by created_at descending (newest first)
        actions.sort(key=lambda x: x.created_at, reverse=True)
        
        # Keep the first (newest) one
        keep_action = actions[0]
        kept_count += 1
        
        print(f"\nKeeping: {keep_action.title} (ID: {keep_action.id})")
        print(f"  Board: {keep_action.board.name}")
        print(f"  Retrospective: {keep_action.retrospective.title}")
        print(f"  Created: {keep_action.created_at}")
        
        # Delete the rest
        for action in actions[1:]:
            print(f"  Deleting duplicate: ID {action.id} from {action.retrospective.title}")
            action.delete()
            deleted_count += 1
    else:
        kept_count += 1

print(f"\n\n✓ Summary:")
print(f"  Kept: {kept_count} action items")
print(f"  Deleted: {deleted_count} redundant action items")
