#!/usr/bin/env python
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'kanban_board.settings')
django.setup()

from allauth.socialaccount.models import SocialApp

google_app = SocialApp.objects.filter(provider='google').first()
if google_app:
    print(f"✓ Google OAuth found in database")
    print(f"  Provider: {google_app.provider}")
    print(f"  Name: {google_app.name}")
    print(f"  Client ID: {google_app.client_id[:20]}...")
    print(f"  Associated Sites: {[site.domain for site in google_app.sites.all()]}")
else:
    print("✗ Google OAuth NOT found in database")
