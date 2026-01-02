import os
import sys
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'taskflow.settings')
django.setup()

from kanban.models import Board
from accounts.models import Organization

print("=== Organizations ===")
for o in Organization.objects.all():
    print(f"  {o.id}: {o.name}")

print("\n=== All Boards ===")
for b in Board.objects.all():
    print(f"  {b.id}: '{b.name}' (org: '{b.organization.name}')")

# Check expected demo values
print("\n=== Demo Check ===")
DEMO_ORG_NAMES = ['Demo - Acme Corporation']
DEMO_BOARD_NAMES = ['Software Development', 'Bug Tracking', 'Marketing Campaign']

demo_orgs = Organization.objects.filter(name__in=DEMO_ORG_NAMES)
print(f"Demo orgs found: {demo_orgs.count()}")
for o in demo_orgs:
    print(f"  Found: {o.name}")

demo_boards = Board.objects.filter(
    organization__in=demo_orgs,
    name__in=DEMO_BOARD_NAMES
)
print(f"\nDemo boards found: {demo_boards.count()}")
for b in demo_boards:
    print(f"  Found: {b.name}")

# Check what boards exist in demo org
print("\n=== Boards in Demo Org ===")
demo_org_boards = Board.objects.filter(organization__in=demo_orgs)
print(f"Boards in demo org: {demo_org_boards.count()}")
for b in demo_org_boards:
    print(f"  {b.id}: '{b.name}'")
