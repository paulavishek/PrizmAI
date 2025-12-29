"""
Deep verification script to ensure no demo data remains anywhere in the system
Checks for any orphaned or hidden demo data that might exist
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'kanban_board.settings')
django.setup()

from django.contrib.auth.models import User
from accounts.models import Organization, UserProfile
from kanban.models import (
    Board, Column, Task, Comment, TaskActivity, TaskLabel,
    ResourceDemandForecast, TeamCapacityAlert, WorkloadDistributionRecommendation
)
from messaging.models import ChatRoom, ChatMessage, Notification, TaskThreadComment
from wiki.models import WikiCategory, WikiPage, WikiAttachment, MeetingNotes
from ai_assistant.models import AIAssistantSession, AIAssistantMessage, ProjectKnowledgeBase
from kanban.coach_models import CoachingSuggestion, CoachingFeedback, PMMetrics, CoachingInsight
from kanban.resource_leveling_models import (
    UserPerformanceProfile, TaskAssignmentHistory, ResourceLevelingSuggestion
)
from analytics.models import UserSession, Feedback, FeedbackPrompt, AnalyticsEvent
from kanban.permission_models import BoardMembership, Role
from kanban.stakeholder_models import (
    ProjectStakeholder, StakeholderTaskInvolvement, 
    StakeholderEngagementRecord
)

def deep_verification():
    """Perform deep verification to ensure system is completely clean of demo data"""
    
    print("="*80)
    print("DEEP DEMO DATA VERIFICATION")
    print("="*80)
    print()
    
    issues_found = []
    
    # Demo identifiers
    demo_usernames = [
        'john_doe', 'jane_smith', 'robert_johnson', 
        'alice_williams', 'bob_martinez', 
        'carol_anderson', 'david_taylor',
        'emily_chen', 'michael_brown', 'sarah_davis', 'james_wilson'
    ]
    demo_org_names = ['Dev Team', 'Marketing Team']
    demo_board_names = ['Software Project', 'Bug Tracking', 'Marketing Campaign']
    
    print("🔍 Checking for Demo Users...")
    demo_users = User.objects.filter(username__in=demo_usernames)
    if demo_users.exists():
        issues_found.append(f"Found {demo_users.count()} demo users: {[u.username for u in demo_users]}")
        print(f"  ❌ Found {demo_users.count()} demo users")
    else:
        print("  ✅ No demo users")
    
    print("\n🔍 Checking for Demo Organizations...")
    demo_orgs = Organization.objects.filter(name__in=demo_org_names)
    if demo_orgs.exists():
        issues_found.append(f"Found {demo_orgs.count()} demo organizations: {[o.name for o in demo_orgs]}")
        print(f"  ❌ Found {demo_orgs.count()} demo organizations")
    else:
        print("  ✅ No demo organizations")
    
    print("\n🔍 Checking for Demo Boards (by name)...")
    demo_boards_by_name = Board.objects.filter(name__in=demo_board_names)
    if demo_boards_by_name.exists():
        issues_found.append(f"Found {demo_boards_by_name.count()} demo boards by name")
        print(f"  ❌ Found {demo_boards_by_name.count()} boards with demo names")
        for board in demo_boards_by_name:
            print(f"    - {board.name} (Org: {board.organization.name})")
    else:
        print("  ✅ No boards with demo names")
    
    print("\n🔍 Checking for Orphaned User Profiles...")
    orphaned_profiles = UserProfile.objects.filter(user__isnull=True)
    if orphaned_profiles.exists():
        issues_found.append(f"Found {orphaned_profiles.count()} orphaned user profiles")
        print(f"  ❌ Found {orphaned_profiles.count()} orphaned profiles")
    else:
        print("  ✅ No orphaned profiles")
    
    print("\n🔍 Checking for Orphaned Board Memberships...")
    orphaned_memberships = BoardMembership.objects.filter(
        models.Q(user__isnull=True) | models.Q(board__isnull=True)
    )
    if orphaned_memberships.exists():
        issues_found.append(f"Found {orphaned_memberships.count()} orphaned board memberships")
        print(f"  ❌ Found {orphaned_memberships.count()} orphaned memberships")
    else:
        print("  ✅ No orphaned memberships")
    
    print("\n🔍 Checking for Orphaned Chat Rooms...")
    orphaned_chat_rooms = ChatRoom.objects.filter(board__isnull=True)
    if orphaned_chat_rooms.exists():
        issues_found.append(f"Found {orphaned_chat_rooms.count()} orphaned chat rooms")
        print(f"  ❌ Found {orphaned_chat_rooms.count()} orphaned chat rooms")
    else:
        print("  ✅ No orphaned chat rooms")
    
    print("\n🔍 Checking for Orphaned Tasks...")
    orphaned_tasks = Task.objects.filter(column__isnull=True)
    if orphaned_tasks.exists():
        issues_found.append(f"Found {orphaned_tasks.count()} orphaned tasks")
        print(f"  ❌ Found {orphaned_tasks.count()} orphaned tasks")
    else:
        print("  ✅ No orphaned tasks")
    
    print("\n🔍 Checking for Orphaned Columns...")
    orphaned_columns = Column.objects.filter(board__isnull=True)
    if orphaned_columns.exists():
        issues_found.append(f"Found {orphaned_columns.count()} orphaned columns")
        print(f"  ❌ Found {orphaned_columns.count()} orphaned columns")
    else:
        print("  ✅ No orphaned columns")
    
    print("\n🔍 Checking for Wiki Pages referencing demo orgs...")
    if demo_orgs.exists():
        wiki_pages = WikiPage.objects.filter(organization__in=demo_orgs)
        wiki_categories = WikiCategory.objects.filter(organization__in=demo_orgs)
        if wiki_pages.exists() or wiki_categories.exists():
            issues_found.append(f"Found {wiki_pages.count()} wiki pages and {wiki_categories.count()} categories")
            print(f"  ❌ Found {wiki_pages.count()} wiki pages, {wiki_categories.count()} categories")
        else:
            print("  ✅ No wiki content for demo orgs")
    else:
        print("  ✅ No demo orgs to check wiki content")
    
    print("\n🔍 Checking for AI Sessions from demo users...")
    if demo_users.exists():
        ai_sessions = AIAssistantSession.objects.filter(user__in=demo_users)
        if ai_sessions.exists():
            issues_found.append(f"Found {ai_sessions.count()} AI assistant sessions")
            print(f"  ❌ Found {ai_sessions.count()} AI sessions")
        else:
            print("  ✅ No AI sessions from demo users")
    else:
        print("  ✅ No demo users to check AI sessions")
    
    print("\n🔍 Checking for Coaching Data...")
    if demo_orgs.exists():
        demo_boards = Board.objects.filter(organization__in=demo_orgs)
        if demo_boards.exists():
            suggestions = CoachingSuggestion.objects.filter(board__in=demo_boards)
            feedback = CoachingFeedback.objects.filter(suggestion__board__in=demo_boards)
            metrics = PMMetrics.objects.filter(board__in=demo_boards)
            total = suggestions.count() + feedback.count() + metrics.count()
            if total > 0:
                issues_found.append(f"Found {total} coaching-related records")
                print(f"  ❌ Found {suggestions.count()} suggestions, {feedback.count()} feedback, {metrics.count()} metrics")
            else:
                print("  ✅ No coaching data")
        else:
            print("  ✅ No demo boards to check coaching data")
    else:
        print("  ✅ No demo orgs to check coaching data")
    
    print("\n🔍 Checking for Analytics Data...")
    if demo_users.exists():
        sessions = UserSession.objects.filter(user__in=demo_users)
        feedbacks = Feedback.objects.filter(user__in=demo_users)
        events = AnalyticsEvent.objects.filter(user_session__user__in=demo_users)
        total = sessions.count() + feedbacks.count() + events.count()
        if total > 0:
            issues_found.append(f"Found {total} analytics records")
            print(f"  ❌ Found {sessions.count()} sessions, {feedbacks.count()} feedback, {events.count()} events")
        else:
            print("  ✅ No analytics data")
    else:
        print("  ✅ No demo users to check analytics")
    
    print("\n🔍 Checking for Stakeholder Data...")
    if demo_orgs.exists():
        demo_boards = Board.objects.filter(organization__in=demo_orgs)
        if demo_boards.exists():
            stakeholders = ProjectStakeholder.objects.filter(board__in=demo_boards)
            if stakeholders.exists():
                issues_found.append(f"Found {stakeholders.count()} stakeholders")
                print(f"  ❌ Found {stakeholders.count()} stakeholders")
            else:
                print("  ✅ No stakeholder data")
        else:
            print("  ✅ No demo boards to check stakeholders")
    else:
        print("  ✅ No demo orgs to check stakeholders")
    
    print("\n🔍 Checking for Notifications...")
    if demo_users.exists():
        notifications = Notification.objects.filter(
            models.Q(recipient__in=demo_users) | models.Q(sender__in=demo_users)
        )
        if notifications.exists():
            issues_found.append(f"Found {notifications.count()} notifications")
            print(f"  ❌ Found {notifications.count()} notifications")
        else:
            print("  ✅ No notifications")
    else:
        print("  ✅ No demo users to check notifications")
    
    print("\n🔍 Checking for Roles in demo organizations...")
    if demo_orgs.exists():
        roles = Role.objects.filter(organization__in=demo_orgs)
        if roles.exists():
            issues_found.append(f"Found {roles.count()} roles in demo organizations")
            print(f"  ❌ Found {roles.count()} roles")
            for role in roles:
                print(f"    - {role.name} ({role.organization.name})")
        else:
            print("  ✅ No roles in demo organizations")
    else:
        print("  ✅ No demo orgs to check roles")
    
    # Final Summary
    print("\n" + "="*80)
    print("VERIFICATION SUMMARY")
    print("="*80)
    
    if issues_found:
        print("\n❌ ISSUES FOUND:")
        for i, issue in enumerate(issues_found, 1):
            print(f"  {i}. {issue}")
        print("\n⚠️  System is NOT clean - demo data still exists")
    else:
        print("\n✅ ALL CHECKS PASSED!")
        print("✅ System is completely clean of demo data")
        print("✅ No orphaned records found")
        print("✅ Ready for fresh demo data setup")
    
    print("="*80)
    print()

if __name__ == '__main__':
    from django.db import models  # Import for Q objects in orphaned checks
    deep_verification()
