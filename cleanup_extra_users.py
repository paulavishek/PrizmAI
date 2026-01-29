"""
Script to remove demo_admin and demo_admin_solo users from the database
Keeps only the three official demo users: alex_chen_demo, sam_rivera_demo, jordan_taylor_demo
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'kanban_board.settings')
django.setup()

from django.contrib.auth.models import User
from kanban.models import (
    UserPerformanceProfile, SkillDevelopmentPlan, SystemAuditLog, 
    SecurityEvent
)
from kanban.budget_models import BudgetRecommendation
from ai_assistant.models import AIAssistantSession, AIAssistantAnalytics
from wiki.models import WikiPage, WikiPageAccess
from api.models import AIRequestLog
from webhooks.models import WebhookEvent
from analytics.models import UserSession
from messaging.models import TaskThreadComment, ChatMessage

def cleanup_user(username):
    """Remove a user and all their related data"""
    try:
        user = User.objects.get(username=username)
        print(f"\n{'='*60}")
        print(f"Cleaning up user: {username} (ID: {user.id})")
        print(f"{'='*60}")
        
        # Delete related records
        print("\nDeleting related records...")
        
        # Kanban
        UserPerformanceProfile.objects.filter(user=user).delete()
        print(f"  ✓ UserPerformanceProfile")
        
        SkillDevelopmentPlan.objects.filter(created_by=user).delete()
        print(f"  ✓ SkillDevelopmentPlan")
        
        SystemAuditLog.objects.filter(user=user).delete()
        print(f"  ✓ SystemAuditLog")
        
        SecurityEvent.objects.filter(user=user).delete()
        print(f"  ✓ SecurityEvent")
        
        # For BudgetRecommendation, set reviewed_by to NULL instead of deleting
        BudgetRecommendation.objects.filter(reviewed_by=user).update(reviewed_by=None)
        print(f"  ✓ BudgetRecommendation (set reviewed_by to NULL)")
        
        # AI Assistant
        AIAssistantSession.objects.filter(user=user).delete()
        print(f"  ✓ AIAssistantSession")
        
        AIAssistantAnalytics.objects.filter(user=user).delete()
        print(f"  ✓ AIAssistantAnalytics")
        
        # Wiki
        # Reassign wiki pages to alex_chen_demo instead of deleting
        alex = User.objects.get(username='alex_chen_demo')
        WikiPage.objects.filter(created_by=user).update(created_by=alex)
        WikiPage.objects.filter(updated_by=user).update(updated_by=alex)
        print(f"  ✓ WikiPage (reassigned to alex_chen_demo)")
        
        WikiPageAccess.objects.filter(user=user).delete()
        print(f"  ✓ WikiPageAccess")
        
        # API
        AIRequestLog.objects.filter(user=user).delete()
        print(f"  ✓ AIRequestLog")
        
        # Webhooks
        # Set triggered_by to NULL instead of deleting webhook events
        WebhookEvent.objects.filter(triggered_by=user).update(triggered_by=None)
        print(f"  ✓ WebhookEvent (set triggered_by to NULL)")
        
        # Analytics
        UserSession.objects.filter(user=user).delete()
        print(f"  ✓ UserSession")
        
        # Messaging - Remove from mentioned_users (many-to-many)
        for comment in TaskThreadComment.objects.filter(mentioned_users=user):
            comment.mentioned_users.remove(user)
        print(f"  ✓ TaskThreadComment.mentioned_users")
        
        for message in ChatMessage.objects.filter(mentioned_users=user):
            message.mentioned_users.remove(user)
        print(f"  ✓ ChatMessage.mentioned_users")
        
        # Finally delete the user
        print(f"\nDeleting user {username}...")
        user.delete()
        print(f"  ✓ User deleted successfully!\n")
        return True
        
    except User.DoesNotExist:
        print(f"\nUser '{username}' not found - already deleted or never existed")
        return False
    except Exception as e:
        print(f"\n❌ Error deleting user {username}: {e}")
        return False

def main():
    print("\n" + "="*60)
    print("USER CLEANUP SCRIPT")
    print("="*60)
    
    # Show current users
    users = User.objects.all().order_by('id')
    print(f"\nCurrent users ({users.count()}):")
    for u in users:
        print(f"  {u.id} | {u.username} | {u.email}")
    
    # Cleanup users
    cleanup_user('demo_admin')
    cleanup_user('demo_admin_solo')
    
    # Show final users
    print("\n" + "="*60)
    print("FINAL USER LIST")
    print("="*60)
    users = User.objects.all().order_by('id')
    print(f"\nTotal users: {users.count()}\n")
    for u in users:
        print(f"  {u.id} | {u.username} | {u.email} | {u.first_name} {u.last_name}")
    
    print("\n✅ Cleanup completed successfully!")
    print("You now have only the three official demo users:\n")
    print("  1. alex_chen_demo")
    print("  2. sam_rivera_demo")
    print("  3. jordan_taylor_demo")
    print()

if __name__ == '__main__':
    main()
