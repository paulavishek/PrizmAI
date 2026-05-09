"""Debug script: check decision item statuses for all users."""
import os
import sys
import django

os.chdir(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Django setup is handled by manage.py when called via runscript,
# but we'll import directly using the manage.py env var trick
from decision_center.models import DecisionItem
from django.contrib.auth.models import User

for u in User.objects.all():
    items = DecisionItem.objects.filter(created_for=u).order_by('status', 'priority_level', 'id')
    if not items.exists():
        continue
    print(f'\n=== {u.username} (id={u.id}) ===')
    for i in items:
        flags = []
        if i.archived_at:
            flags.append('ARCHIVED')
        if i.snoozed_until:
            flags.append(f'SNOOZE_UNTIL={str(i.snoozed_until)[:16]}')
        flag_str = ' '.join(flags)
        print(f'  id={i.id:4} [{i.status:10}] [{i.priority_level:16}] {i.title[:60]}  {flag_str}')

print('\n--- Summary ---')
for status in ['pending', 'snoozed', 'resolved', 'dismissed']:
    print(f'  {status}: {DecisionItem.objects.filter(status=status).count()}')
