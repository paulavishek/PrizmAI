"""
Clean up DELETED users from the database
"""

import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'kanban_board.settings')
django.setup()

from django.contrib.auth.models import User

def cleanup_deleted_users():
    """Remove users with 'deleted' in their username"""
    
    deleted_users = User.objects.filter(username__icontains='deleted')
    
    if deleted_users.exists():
        print(f"\n🗑️  Found {deleted_users.count()} deleted users:")
        for user in deleted_users:
            print(f"   - {user.username} ({user.email})")
        
        confirm = input("\n⚠️  Delete these users? (yes/no): ")
        if confirm.lower() == 'yes':
            count = deleted_users.count()
            deleted_users.delete()
            print(f"\n✅ Deleted {count} users")
        else:
            print("\n❌ Cancelled")
    else:
        print("\n✅ No deleted users found")

if __name__ == '__main__':
    cleanup_deleted_users()
