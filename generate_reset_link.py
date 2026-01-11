#!/usr/bin/env python
"""
Generate a password reset link for a user
Usage: python generate_reset_link.py <username>
"""
import os
import sys
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'kanban_board.settings')
django.setup()

from django.contrib.auth.models import User
from django.contrib.auth.tokens import default_token_generator
from django.utils.http import urlsafe_base64_encode
from django.utils.encoding import force_bytes

def generate_reset_link(username):
    try:
        user = User.objects.get(username=username)
        token = default_token_generator.make_token(user)
        uid = urlsafe_base64_encode(force_bytes(user.pk))
        
        reset_link = f"http://127.0.0.1:8000/accounts/reset/{uid}/{token}/"
        
        print("\n" + "="*70)
        print(f"PASSWORD RESET LINK FOR: {user.username}")
        print(f"Email: {user.email}")
        print("="*70)
        print(f"\n{reset_link}\n")
        print("="*70)
        print("\nCopy and paste this link in your browser to reset your password.")
        print("="*70 + "\n")
        
    except User.DoesNotExist:
        print(f"\n❌ ERROR: User '{username}' does not exist!\n")
        sys.exit(1)

if __name__ == '__main__':
    if len(sys.argv) != 2:
        print("Usage: python generate_reset_link.py <username>")
        sys.exit(1)
    
    generate_reset_link(sys.argv[1])
