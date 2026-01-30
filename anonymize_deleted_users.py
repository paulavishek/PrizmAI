"""
Deactivate and rename DELETED users
"""

import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'kanban_board.settings')
django.setup()

from django.contrib.auth.models import User
import uuid

def cleanup_deleted_users():
    """Deactivate and anonymize users with 'deleted' in their username"""
    
    deleted_users = User.objects.filter(username__icontains='deleted')
    
    if deleted_users.exists():
        print(f"\n🗑️  Found {deleted_users.count()} deleted users:")
        for user in deleted_users:
            print(f"   - {user.username} ({user.email})")
            # Deactivate and anonymize
            user.is_active = False
            user.username = f"_deleted_{uuid.uuid4().hex[:8]}"
            user.email = f"deleted_{uuid.uuid4().hex[:8]}@deleted.local"
            user.save()
            print(f"     → Anonymized to: {user.username}")
        
        print(f"\n✅ Anonymized {deleted_users.count()} users")
    else:
        print("\n✅ No deleted users found")

if __name__ == '__main__':
    cleanup_deleted_users()
