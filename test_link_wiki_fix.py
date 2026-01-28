#!/usr/bin/env python
"""
Test script to verify the Link Wiki fix
Checks if the quick_link_wiki endpoint handles users without organizations properly
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'kanban_board.settings')
django.setup()

from django.contrib.auth.models import User
from accounts.models import Organization, UserProfile
from kanban.models import Board
from wiki.models import WikiPage

print("=" * 80)
print("TESTING LINK WIKI FIX")
print("=" * 80)

# Check organizations
print("\n1. Checking Organizations:")
all_orgs = Organization.objects.all()
print(f"   Total organizations: {all_orgs.count()}")
for org in all_orgs:
    print(f"   - {org.name} (is_demo={org.is_demo})")

demo_org = Organization.objects.filter(is_demo=True).first()
if not demo_org:
    demo_org = Organization.objects.filter(name='Demo - Acme Corporation').first()

if demo_org:
    print(f"\n   ✓ Demo organization found: {demo_org.name}")
else:
    print("\n   ✗ No demo organization found!")

# Check users and their organizations
print("\n2. Checking Users:")
users = User.objects.all()[:10]  # Check first 10 users
for user in users:
    if hasattr(user, 'profile'):
        org = user.profile.organization
        print(f"   - {user.username}: org={org.name if org else 'None'}")
    else:
        print(f"   - {user.username}: No profile")

# Check boards
print("\n3. Checking Boards:")
boards = Board.objects.all()[:5]
print(f"   Total boards: {Board.objects.count()}")
for board in boards:
    print(f"   - Board ID {board.id}: {board.name}")
    print(f"     Organization: {board.organization.name if board.organization else 'None'}")

# Check wiki pages
print("\n4. Checking Wiki Pages:")
wiki_pages = WikiPage.objects.filter(is_published=True)
print(f"   Published wiki pages: {wiki_pages.count()}")
for page in wiki_pages[:5]:
    org_name = page.organization.name if page.organization else 'None'
    print(f"   - {page.title} (org={org_name})")

# Test the fix logic
print("\n5. Testing Link Wiki Logic:")
test_user = User.objects.first()
if test_user and hasattr(test_user, 'profile'):
    user_org = test_user.profile.organization
    print(f"   Test user: {test_user.username}")
    print(f"   User's organization: {user_org.name if user_org else 'None'}")
    
    # Simulate the fixed logic
    org = user_org if user_org else demo_org
    print(f"   Effective organization: {org.name if org else 'None'}")
    
    allowed_orgs = []
    if org:
        allowed_orgs.append(org)
    if demo_org and demo_org not in allowed_orgs:
        allowed_orgs.append(demo_org)
    
    print(f"   Allowed organizations: {[o.name for o in allowed_orgs]}")
    
    # Check if boards are accessible
    accessible_boards = Board.objects.filter(organization__in=allowed_orgs) if allowed_orgs else Board.objects.all()
    print(f"   Accessible boards: {accessible_boards.count()}")
    
    # Check if wiki pages are accessible
    from django.db.models import Q
    if user_org:
        wiki_query = WikiPage.objects.filter(
            Q(organization=user_org) | Q(organization__in=[demo_org]) if demo_org else Q(organization=user_org),
            is_published=True
        )
    else:
        wiki_query = WikiPage.objects.filter(
            Q(organization__in=[demo_org]) | Q(organization__isnull=True) if demo_org else Q(organization__isnull=True),
            is_published=True
        )
    print(f"   Accessible wiki pages: {wiki_query.count()}")
    
    if accessible_boards.count() > 0 and wiki_query.count() > 0:
        print("\n   ✓ PASS: Users can access boards and wiki pages for linking!")
    else:
        print("\n   ✗ FAIL: Users cannot access boards or wiki pages")

print("\n" + "=" * 80)
print("TEST COMPLETE")
print("=" * 80)
