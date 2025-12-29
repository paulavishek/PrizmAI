"""
Verify Current Demo State - Step 1
Checks that NO demo data exists (clean slate) and verifies existing models
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'kanban_board.settings')
django.setup()

from django.contrib.auth.models import User
from accounts.models import Organization, UserProfile
from kanban.models import Board, Task
from analytics.models import UserSession

def check_demo_organizations():
    """Check for demo organizations"""
    print("\n" + "="*80)
    print("CHECKING DEMO ORGANIZATIONS")
    print("="*80)
    
    # Check for organizations with "Demo" in name
    demo_org_patterns = ['Demo', 'Dev Team', 'Marketing Team']
    
    for pattern in demo_org_patterns:
        orgs = Organization.objects.filter(name__icontains=pattern)
        if orgs.exists():
            print(f"\n⚠️  Found {orgs.count()} organization(s) matching '{pattern}':")
            for org in orgs:
                print(f"   - {org.name} (ID: {org.id}, Created: {org.created_at})")
                # Check if has is_demo field
                if hasattr(org, 'is_demo'):
                    print(f"     is_demo: {org.is_demo}")
                else:
                    print(f"     ❌ is_demo field NOT FOUND (need to add)")
        else:
            print(f"\n✅ No organizations found matching '{pattern}'")
    
    # Check total organizations
    total_orgs = Organization.objects.all().count()
    print(f"\n📊 Total organizations in database: {total_orgs}")
    
    # Check for is_demo field
    if hasattr(Organization, 'is_demo'):
        print("✅ Organization.is_demo field EXISTS")
    else:
        print("❌ Organization.is_demo field MISSING (need to add via migration)")

def check_demo_boards():
    """Check for demo boards"""
    print("\n" + "="*80)
    print("CHECKING DEMO BOARDS")
    print("="*80)
    
    # Check for boards with demo-related names
    demo_board_names = ['Software Project', 'Bug Tracking', 'Marketing Campaign', 'Software Development']
    
    for board_name in demo_board_names:
        boards = Board.objects.filter(name__icontains=board_name)
        if boards.exists():
            print(f"\n⚠️  Found {boards.count()} board(s) matching '{board_name}':")
            for board in boards:
                print(f"   - {board.name} (ID: {board.id})")
                print(f"     Organization: {board.organization.name}")
                print(f"     Created: {board.created_at}")
                print(f"     Members: {board.members.count()}")
                
                # Check for new fields
                if hasattr(board, 'is_official_demo_board'):
                    print(f"     is_official_demo_board: {board.is_official_demo_board}")
                else:
                    print(f"     ❌ is_official_demo_board field MISSING")
                    
                if hasattr(board, 'created_by_session'):
                    print(f"     created_by_session: {board.created_by_session}")
                else:
                    print(f"     ❌ created_by_session field MISSING")
        else:
            print(f"\n✅ No boards found matching '{board_name}'")
    
    # Check total boards
    total_boards = Board.objects.all().count()
    print(f"\n📊 Total boards in database: {total_boards}")

def check_demo_users():
    """Check for demo personas"""
    print("\n" + "="*80)
    print("CHECKING DEMO PERSONAS")
    print("="*80)
    
    # Expected demo personas
    demo_personas = [
        ('alex.chen@demo.prizmai.local', 'Alex Chen'),
        ('sam.rivera@demo.prizmai.local', 'Sam Rivera'),
        ('jordan.taylor@demo.prizmai.local', 'Jordan Taylor'),
    ]
    
    # Also check old demo users
    old_demo_usernames = [
        'john_doe', 'jane_smith', 'robert_johnson', 'alice_williams',
        'bob_martinez', 'carol_anderson', 'david_taylor'
    ]
    
    found_personas = []
    
    for email, name in demo_personas:
        user = User.objects.filter(email=email).first()
        if user:
            print(f"\n⚠️  Found demo persona: {name}")
            print(f"   Email: {email}")
            print(f"   Username: {user.username}")
            found_personas.append(user)
        else:
            print(f"\n✅ Demo persona NOT found: {name} ({email})")
    
    for username in old_demo_usernames:
        user = User.objects.filter(username=username).first()
        if user:
            print(f"\n⚠️  Found old demo user: {username}")
            if hasattr(user, 'profile'):
                print(f"   Organization: {user.profile.organization.name}")
            found_personas.append(user)
    
    if not found_personas:
        print("\n✅ No demo personas found - Clean slate confirmed!")
    
    # Check total users
    total_users = User.objects.all().count()
    print(f"\n📊 Total users in database: {total_users}")

def check_demo_tasks():
    """Check for demo-related tasks"""
    print("\n" + "="*80)
    print("CHECKING DEMO TASKS")
    print("="*80)
    
    # Check if created_by_session field exists
    if hasattr(Task, 'created_by_session'):
        print("✅ Task.created_by_session field EXISTS")
        
        # Check for tasks with session tracking
        session_tasks = Task.objects.exclude(created_by_session__isnull=True).exclude(created_by_session='')
        if session_tasks.exists():
            print(f"⚠️  Found {session_tasks.count()} tasks with session tracking")
        else:
            print("✅ No tasks with session tracking")
    else:
        print("❌ Task.created_by_session field MISSING (need to add via migration)")
    
    # Check total tasks
    total_tasks = Task.objects.all().count()
    print(f"\n📊 Total tasks in database: {total_tasks}")

def check_analytics_models():
    """Check analytics models"""
    print("\n" + "="*80)
    print("CHECKING ANALYTICS MODELS")
    print("="*80)
    
    # Check UserSession model (existing)
    print("\n✅ UserSession model EXISTS")
    total_sessions = UserSession.objects.all().count()
    print(f"   Total sessions: {total_sessions}")
    
    # Check for new demo analytics models
    try:
        from analytics.models import DemoSession
        print("\n✅ DemoSession model EXISTS")
        total_demo_sessions = DemoSession.objects.all().count()
        print(f"   Total demo sessions: {total_demo_sessions}")
    except ImportError:
        print("\n❌ DemoSession model MISSING (need to create)")
    
    try:
        from analytics.models import DemoAnalytics
        print("\n✅ DemoAnalytics model EXISTS")
        total_demo_analytics = DemoAnalytics.objects.all().count()
        print(f"   Total demo events: {total_demo_analytics}")
    except ImportError:
        print("\n❌ DemoAnalytics model MISSING (need to create)")
    
    try:
        from analytics.models import DemoConversion
        print("\n✅ DemoConversion model EXISTS")
        total_demo_conversions = DemoConversion.objects.all().count()
        print(f"   Total demo conversions: {total_demo_conversions}")
    except ImportError:
        print("\n❌ DemoConversion model MISSING (need to create)")

def print_summary():
    """Print summary and next steps"""
    print("\n" + "="*80)
    print("SUMMARY & NEXT STEPS")
    print("="*80)
    
    print("\n📋 Status:")
    print("   1. ✅ Verified database structure")
    print("   2. ✅ Checked for existing demo data")
    print("   3. ✅ Identified missing fields/models")
    
    print("\n🎯 Next Steps:")
    print("   1. Add missing fields to existing models (Organization, Board, Task)")
    print("   2. Create new demo analytics models (DemoSession, DemoAnalytics, DemoConversion)")
    print("   3. Run migrations")
    print("   4. Create demo data management commands")
    
    print("\n" + "="*80)

if __name__ == '__main__':
    print("\n" + "="*80)
    print("DEMO STATE VERIFICATION - Step 1")
    print("="*80)
    print("Checking if demo data exists and verifying database structure...")
    
    try:
        check_demo_organizations()
        check_demo_boards()
        check_demo_users()
        check_demo_tasks()
        check_analytics_models()
        print_summary()
        
    except Exception as e:
        print(f"\n❌ Error during verification: {str(e)}")
        import traceback
        traceback.print_exc()
