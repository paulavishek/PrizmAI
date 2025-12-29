"""
Comprehensive check of all demo data in the system
This will show what demo data currently exists before deletion
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'kanban_board.settings')
django.setup()

from django.contrib.auth.models import User
from accounts.models import Organization, UserProfile
from kanban.models import Board, Column, Task, Comment, TaskActivity
from messaging.models import ChatRoom, ChatMessage
from wiki.models import WikiCategory, WikiPage
from ai_assistant.models import AIAssistantSession
from kanban.coach_models import CoachingSuggestion, CoachingFeedback, PMMetrics
from kanban.resource_leveling_models import UserPerformanceProfile, TaskAssignmentHistory
from analytics.models import UserSession, Feedback
from kanban.permission_models import BoardMembership

def check_demo_data():
    """Check all demo data in the system"""
    
    print("="*80)
    print("DEMO DATA STATUS CHECK")
    print("="*80)
    print()
    
    # Demo identifiers
    demo_usernames = [
        'john_doe', 'jane_smith', 'robert_johnson', 
        'alice_williams', 'bob_martinez', 
        'carol_anderson', 'david_taylor',
        'emily_chen', 'michael_brown', 'sarah_davis', 'james_wilson'
    ]
    demo_org_names = ['Dev Team', 'Marketing Team']
    demo_board_names = ['Software Project', 'Bug Tracking', 'Marketing Campaign']
    
    # Check Users
    print("📊 DEMO USERS:")
    print("-" * 80)
    demo_users = User.objects.filter(username__in=demo_usernames)
    if demo_users.exists():
        for user in demo_users:
            try:
                org_name = user.profile.organization.name if hasattr(user, 'profile') and user.profile.organization else "No Org"
                board_count = user.member_boards.count()
                print(f"  ✓ {user.username:20} | Org: {org_name:20} | Boards: {board_count}")
            except Exception as e:
                print(f"  ✓ {user.username:20} | Error: {str(e)}")
        print(f"\n  Total Demo Users: {demo_users.count()}")
    else:
        print("  ✅ No demo users found")
    print()
    
    # Check Organizations
    print("🏢 DEMO ORGANIZATIONS:")
    print("-" * 80)
    demo_orgs = Organization.objects.filter(name__in=demo_org_names)
    if demo_orgs.exists():
        for org in demo_orgs:
            board_count = org.boards.count()
            user_count = UserProfile.objects.filter(organization=org).count()
            print(f"  ✓ {org.name:20} | Boards: {board_count:3} | Users: {user_count:3}")
        print(f"\n  Total Demo Organizations: {demo_orgs.count()}")
    else:
        print("  ✅ No demo organizations found")
    print()
    
    # Check Boards
    print("📋 DEMO BOARDS:")
    print("-" * 80)
    demo_boards = Board.objects.filter(organization__in=demo_orgs) if demo_orgs.exists() else Board.objects.none()
    if demo_boards.exists():
        for board in demo_boards:
            task_count = Task.objects.filter(column__board=board).count()
            member_count = board.members.count()
            column_count = board.columns.count()
            print(f"  ✓ {board.name:30} | Tasks: {task_count:4} | Members: {member_count:3} | Columns: {column_count}")
        print(f"\n  Total Demo Boards: {demo_boards.count()}")
    else:
        print("  ✅ No demo boards found")
    print()
    
    # Check Tasks
    print("📝 TASKS IN DEMO BOARDS:")
    print("-" * 80)
    if demo_boards.exists():
        tasks = Task.objects.filter(column__board__in=demo_boards)
        if tasks.exists():
            print(f"  Total Tasks: {tasks.count()}")
            print(f"  - By Priority:")
            for priority in ['low', 'medium', 'high', 'urgent']:
                count = tasks.filter(priority=priority).count()
                if count > 0:
                    print(f"    • {priority.capitalize()}: {count}")
            print(f"  - By Status:")
            for board in demo_boards:
                for column in board.columns.all():
                    count = tasks.filter(column=column).count()
                    if count > 0:
                        print(f"    • {board.name} - {column.name}: {count}")
        else:
            print("  ✅ No tasks in demo boards")
    else:
        print("  ✅ No demo boards to check tasks")
    print()
    
    # Check Board Memberships
    print("👥 BOARD MEMBERSHIPS:")
    print("-" * 80)
    if demo_boards.exists():
        memberships = BoardMembership.objects.filter(board__in=demo_boards)
        if memberships.exists():
            print(f"  Total Memberships: {memberships.count()}")
            for board in demo_boards:
                count = memberships.filter(board=board).count()
                if count > 0:
                    print(f"  - {board.name}: {count} members")
                    roles = {}
                    for membership in memberships.filter(board=board):
                        role_name = membership.role.name if membership.role else "No Role"
                        roles[role_name] = roles.get(role_name, 0) + 1
                    for role, count in roles.items():
                        print(f"    • {role}: {count}")
        else:
            print("  ✅ No board memberships found")
    else:
        print("  ✅ No demo boards to check memberships")
    print()
    
    # Check Comments
    print("💬 COMMENTS:")
    print("-" * 80)
    if demo_boards.exists():
        comments = Comment.objects.filter(task__column__board__in=demo_boards)
        print(f"  Total Comments: {comments.count()}")
        if comments.count() > 0:
            print("  ⚠️  Demo comments exist")
    else:
        print("  ✅ No demo boards to check comments")
    print()
    
    # Check Chat Rooms & Messages
    print("💬 CHAT ROOMS & MESSAGES:")
    print("-" * 80)
    if demo_boards.exists():
        chat_rooms = ChatRoom.objects.filter(board__in=demo_boards)
        if chat_rooms.exists():
            total_messages = ChatMessage.objects.filter(chat_room__in=chat_rooms).count()
            print(f"  Total Chat Rooms: {chat_rooms.count()}")
            print(f"  Total Messages: {total_messages}")
            if total_messages > 0:
                print("  ⚠️  Demo chat messages exist")
        else:
            print("  ✅ No chat rooms in demo boards")
    else:
        print("  ✅ No demo boards to check chat")
    print()
    
    # Check Wiki Pages
    print("📖 WIKI PAGES:")
    print("-" * 80)
    if demo_orgs.exists():
        wiki_pages = WikiPage.objects.filter(organization__in=demo_orgs)
        wiki_categories = WikiCategory.objects.filter(organization__in=demo_orgs)
        print(f"  Total Wiki Categories: {wiki_categories.count()}")
        print(f"  Total Wiki Pages: {wiki_pages.count()}")
        if wiki_pages.count() > 0 or wiki_categories.count() > 0:
            print("  ⚠️  Demo wiki content exists")
    else:
        print("  ✅ No demo organizations to check wiki")
    print()
    
    # Check AI Assistant Data
    print("🤖 AI ASSISTANT DATA:")
    print("-" * 80)
    if demo_users.exists():
        ai_sessions = AIAssistantSession.objects.filter(user__in=demo_users)
        print(f"  Total AI Sessions: {ai_sessions.count()}")
        if ai_sessions.count() > 0:
            print("  ⚠️  Demo AI sessions exist")
    else:
        print("  ✅ No demo users to check AI data")
    print()
    
    # Check Coaching Data
    print("🎓 COACHING DATA:")
    print("-" * 80)
    if demo_boards.exists():
        suggestions = CoachingSuggestion.objects.filter(board__in=demo_boards)
        feedback = CoachingFeedback.objects.filter(suggestion__board__in=demo_boards)
        metrics = PMMetrics.objects.filter(board__in=demo_boards)
        print(f"  Total Coaching Suggestions: {suggestions.count()}")
        print(f"  Total Coaching Feedback: {feedback.count()}")
        print(f"  Total PM Metrics: {metrics.count()}")
        if suggestions.count() > 0 or feedback.count() > 0 or metrics.count() > 0:
            print("  ⚠️  Demo coaching data exists")
    else:
        print("  ✅ No demo boards to check coaching data")
    print()
    
    # Check Resource Leveling Data
    print("⚖️ RESOURCE LEVELING DATA:")
    print("-" * 80)
    if demo_users.exists() and demo_orgs.exists():
        profiles = UserPerformanceProfile.objects.filter(user__in=demo_users, organization__in=demo_orgs)
        print(f"  Total Performance Profiles: {profiles.count()}")
        if profiles.count() > 0:
            print("  ⚠️  Demo performance profiles exist")
    else:
        print("  ✅ No demo users/orgs to check resource data")
    print()
    
    # Check Analytics Data
    print("📊 ANALYTICS DATA:")
    print("-" * 80)
    if demo_users.exists():
        sessions = UserSession.objects.filter(user__in=demo_users)
        feedbacks = Feedback.objects.filter(user__in=demo_users)
        print(f"  Total User Sessions: {sessions.count()}")
        print(f"  Total Feedback Records: {feedbacks.count()}")
        if sessions.count() > 0 or feedbacks.count() > 0:
            print("  ⚠️  Demo analytics data exists")
    else:
        print("  ✅ No demo users to check analytics")
    print()
    
    # Summary
    print("="*80)
    print("SUMMARY:")
    print("="*80)
    
    has_data = False
    if demo_users.exists():
        print(f"⚠️  Found {demo_users.count()} demo users")
        has_data = True
    if demo_orgs.exists():
        print(f"⚠️  Found {demo_orgs.count()} demo organizations")
        has_data = True
    if demo_boards.exists():
        print(f"⚠️  Found {demo_boards.count()} demo boards")
        has_data = True
        tasks_count = Task.objects.filter(column__board__in=demo_boards).count()
        if tasks_count > 0:
            print(f"⚠️  Found {tasks_count} demo tasks")
    
    if not has_data:
        print("✅ NO DEMO DATA FOUND - System is clean!")
    else:
        print("\n⚠️  DEMO DATA EXISTS - Ready for deletion")
    
    print("="*80)
    print()

if __name__ == '__main__':
    check_demo_data()
