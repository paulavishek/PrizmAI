"""
Update Demo User Passwords

This script sets all demo user accounts to have the password 'demo123'
so users can login and test features from multiple browser windows.
"""

import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'kanban_board.settings')
django.setup()

from django.contrib.auth.models import User


def update_demo_passwords():
    """Update all demo user passwords to 'demo123'"""
    
    demo_usernames = [
        'demo_admin_solo',
        'alex_chen_demo',
        'sam_rivera_demo',
        'jordan_taylor_demo'
    ]
    
    print("\n" + "="*60)
    print("Updating Demo User Passwords")
    print("="*60 + "\n")
    
    updated_count = 0
    not_found = []
    
    for username in demo_usernames:
        try:
            user = User.objects.get(username=username)
            user.set_password('demo123')
            user.save()
            print(f"✓ Updated password for: {username}")
            updated_count += 1
        except User.DoesNotExist:
            print(f"✗ User not found: {username}")
            not_found.append(username)
    
    print("\n" + "="*60)
    print(f"Summary: {updated_count} passwords updated")
    
    if not_found:
        print(f"\nUsers not found: {', '.join(not_found)}")
        print("Run: python manage.py create_demo_organization")
    
    print("\n" + "="*60)
    print("Demo User Credentials:")
    print("="*60)
    print("Username              | Password")
    print("-"*60)
    for username in demo_usernames:
        if username not in not_found:
            print(f"{username:<20} | demo123")
    print("="*60)
    print("\nUsers can now login with these credentials!")
    print("Test messaging: Open incognito window → Login as different user")
    print("="*60 + "\n")


if __name__ == '__main__':
    update_demo_passwords()
