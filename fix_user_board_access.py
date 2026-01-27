#!/usr/bin/env python
"""Fix: Add user to demo boards as a member"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'kanban_board.settings')
django.setup()

from django.contrib.auth.models import User
from kanban.models import Board, Organization

print("=" * 60)
print("FIXING USER BOARD ACCESS")
print("=" * 60)

username = 'avishekpaul1310'
user = User.objects.get(username=username)
print(f"\n👤 User: {user.username}")

# Get demo boards
demo_org = Organization.objects.get(name='Demo - Acme Corporation')
demo_boards = Board.objects.filter(organization=demo_org)

print(f"\n📋 Adding user to {demo_boards.count()} demo boards...")

for board in demo_boards:
    if user not in board.members.all():
        board.members.add(user)
        print(f"   ✅ Added to: {board.name}")
    else:
        print(f"   ℹ️  Already member of: {board.name}")

print("\n✨ Complete! User should now be able to scan boards.")
print("=" * 60)
