"""Check superuser accounts"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'kanban_board.settings')
django.setup()

from django.contrib.auth.models import User

print("\n" + "=" * 60)
print("SUPERUSER ACCOUNTS")
print("=" * 60)

superusers = User.objects.filter(is_superuser=True)

if superusers.exists():
    print(f"\nFound {superusers.count()} superuser(s):\n")
    for user in superusers:
        print(f"  Username: {user.username}")
        print(f"  Email:    {user.email}")
        print(f"  Created:  {user.date_joined.strftime('%Y-%m-%d %H:%M')}")
        print(f"  Active:   {user.is_active}")
        print("-" * 60)
else:
    print("\n❌ No superuser accounts found!")
    print("\nTo create a superuser, run:")
    print("  python manage.py createsuperuser")

print("\n" + "=" * 60)
print("\nNOTE: Passwords are encrypted and cannot be displayed.")
print("If you forgot your password, you can reset it:")
print("  python manage.py changepassword <username>")
print("=" * 60)
