#!/usr/bin/env python
"""Verify the fix for conflict detection board query"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'kanban_board.settings')
django.setup()

from django.contrib.auth.models import User
from kanban.models import Board, Organization
from django.db.models import Q

print("=" * 60)
print("VERIFYING CONFLICT DETECTION FIX")
print("=" * 60)

username = 'avishekpaul1310'
user = User.objects.get(username=username)
profile = user.profile
organization = profile.organization

print(f"\n👤 User: {user.username}")
print(f"   Organization: {organization.name} (ID: {organization.id})")

# Simulate the OLD query (without demo boards)
print("\n❌ OLD QUERY (Only user's organization):")
old_boards = Board.objects.filter(
    Q(organization=organization) &
    (Q(created_by=user) | Q(members=user))
).distinct()
print(f"   Boards found: {old_boards.count()}")
for board in old_boards:
    print(f"   - {board.name}")

# Simulate the NEW query (with demo boards included)
print("\n✅ NEW QUERY (Including demo organization):")
demo_org = Organization.objects.filter(name='Demo - Acme Corporation').first()
org_filter = Q(organization=organization)
if demo_org:
    org_filter |= Q(organization=demo_org)

new_boards = Board.objects.filter(
    org_filter &
    (Q(created_by=user) | Q(members=user))
).distinct()
print(f"   Boards found: {new_boards.count()}")
for board in new_boards:
    print(f"   - {board.name} (Org: {board.organization.name})")

print("\n" + "=" * 60)
print(f"✨ FIX RESULT: {new_boards.count()} boards will now be scanned!")
print("=" * 60)
