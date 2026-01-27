import sys
import os
sys.path.insert(0, os.path.dirname(__file__))
os.environ['DJANGO_SETTINGS_MODULE'] = 'PrizmAI.settings'

import django
django.setup()

from django.contrib.auth.models import User
from accounts.models import Organization
from kanban.models import Board

demo_org = Organization.objects.filter(is_demo=True).first()
print(f"Demo org: {demo_org.name if demo_org else 'None'}")
if demo_org:
    print(f"  Boards in demo org: {demo_org.boards.count()}")
    print(f"  Official demo boards: {demo_org.boards.filter(is_official_demo_board=True).count()}")
    print(f"  User-created boards in demo org: {demo_org.boards.filter(is_official_demo_board=False).count()}")

print("\nAll users and their organizations:")
for user in User.objects.all()[:5]:
    if hasattr(user, 'profile'):
        print(f"  {user.username}: org={user.profile.organization.name}, is_demo={user.profile.organization.is_demo}")

print("\nTest board details:")
test_board = Board.objects.filter(name__icontains='test').first()
if test_board:
    print(f"  Name: {test_board.name}")
    print(f"  Organization: {test_board.organization.name}")
    print(f"  Org is_demo: {test_board.organization.is_demo}")
    print(f"  Created by: {test_board.created_by.username}")
    if hasattr(test_board.created_by, 'profile'):
        print(f"  Creator's org: {test_board.created_by.profile.organization.name}")
