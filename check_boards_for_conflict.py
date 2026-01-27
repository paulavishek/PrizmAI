#!/usr/bin/env python
"""Check boards available for conflict detection"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'kanban_board.settings')
django.setup()

from kanban.models import Board, Organization

print("=" * 60)
print("BOARD ANALYSIS FOR CONFLICT DETECTION")
print("=" * 60)

# Check total boards
total_boards = Board.objects.count()
print(f"\n📊 Total Boards in Database: {total_boards}")

# Check Demo organization
demo_org_names = ['Demo - Acme Corporation']
demo_orgs = Organization.objects.filter(name__in=demo_org_names)
print(f"\n🏢 Demo Organizations Found: {demo_orgs.count()}")
for org in demo_orgs:
    print(f"   - {org.name} (ID: {org.id})")

# Check demo boards
demo_boards = Board.objects.filter(organization__in=demo_orgs)
print(f"\n📋 Demo Organization Boards: {demo_boards.count()}")
for board in demo_boards:
    print(f"   - {board.name} (ID: {board.id}, Org: {board.organization.name})")

# Check all organizations
all_orgs = Organization.objects.all()
print(f"\n🏢 All Organizations ({all_orgs.count()}):")
for org in all_orgs:
    board_count = Board.objects.filter(organization=org).count()
    print(f"   - {org.name} (ID: {org.id}) - {board_count} boards")

print("\n" + "=" * 60)
print("ANALYSIS COMPLETE")
print("=" * 60)
