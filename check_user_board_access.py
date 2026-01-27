#!/usr/bin/env python
"""Check user's organization and board access"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'kanban_board.settings')
django.setup()

from django.contrib.auth.models import User
from kanban.models import Board, Organization
from django.db.models import Q

print("=" * 60)
print("USER BOARD ACCESS ANALYSIS")
print("=" * 60)

# Find the user
username = 'avishekpaul1310'
try:
    user = User.objects.get(username=username)
    print(f"\n👤 User Found: {user.username}")
    print(f"   - ID: {user.id}")
    print(f"   - Email: {user.email}")
    print(f"   - Is Authenticated: True")
    
    # Check if user has profile
    try:
        profile = user.profile
        print(f"\n📋 User Profile:")
        print(f"   - Has Profile: Yes")
        print(f"   - Organization: {profile.organization if hasattr(profile, 'organization') else 'None'}")
        if hasattr(profile, 'organization') and profile.organization:
            org = profile.organization
            print(f"   - Organization ID: {org.id}")
            print(f"   - Organization Name: {org.name}")
            
            # Check boards using the same query as conflict detection
            boards = Board.objects.filter(
                Q(organization=org) &
                (Q(created_by=user) | Q(members=user))
            ).distinct()
            
            print(f"\n📊 Boards Accessible (Using Conflict Detection Query):")
            print(f"   - Count: {boards.count()}")
            for board in boards:
                print(f"   - {board.name} (ID: {board.id})")
            
            # Check all boards in user's organization
            org_boards = Board.objects.filter(organization=org)
            print(f"\n📊 All Boards in User's Organization:")
            print(f"   - Count: {org_boards.count()}")
            for board in org_boards:
                is_creator = board.created_by == user
                is_member = user in board.members.all()
                print(f"   - {board.name} (Creator: {is_creator}, Member: {is_member})")
                
    except AttributeError as e:
        print(f"\n❌ User Profile Error: {e}")
        print("   - User may not have a profile set up")
        
except User.DoesNotExist:
    print(f"\n❌ User '{username}' not found")
    print("\nAll users in database:")
    for u in User.objects.all():
        print(f"   - {u.username}")

print("\n" + "=" * 60)
