"""
Test script to verify HubSpot configuration
"""
import os
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'kanban_board.settings')
django.setup()

from django.conf import settings

print("=" * 60)
print("HubSpot Configuration Check")
print("=" * 60)

hubspot_portal_id = settings.HUBSPOT_PORTAL_ID
hubspot_form_id = settings.HUBSPOT_FORM_ID
hubspot_region = settings.HUBSPOT_REGION
hubspot_access_token = settings.HUBSPOT_ACCESS_TOKEN
hubspot_api_key = settings.HUBSPOT_API_KEY

print(f"\n✓ HUBSPOT_PORTAL_ID: {hubspot_portal_id or '❌ NOT SET'}")
print(f"✓ HUBSPOT_FORM_ID: {hubspot_form_id or '❌ NOT SET'}")
print(f"✓ HUBSPOT_REGION: {hubspot_region or 'na1 (default)'}")
print(f"✓ HUBSPOT_ACCESS_TOKEN: {'✓ SET' if hubspot_access_token else '❌ NOT SET'}")
print(f"✓ HUBSPOT_API_KEY: {'✓ SET' if hubspot_api_key else '❌ NOT SET'}")

print(f"\n✓ Min Engagement for Feedback: {settings.ANALYTICS_MIN_ENGAGEMENT_FOR_FEEDBACK} minutes")

print("\n" + "=" * 60)
print("HubSpot Form Embed URL:")
print("=" * 60)
if hubspot_portal_id and hubspot_form_id:
    print(f"\n//js.hsforms.net/forms/embed/v2.js")
    print(f"\nForm will be created with:")
    print(f"  - Portal ID: {hubspot_portal_id}")
    print(f"  - Form ID: {hubspot_form_id}")
    print(f"  - Region: {hubspot_region}")
    print(f"\n✓ Configuration looks good!")
else:
    print("\n❌ Missing Portal ID or Form ID!")
    print("\nTo fix this, set environment variables or update settings:")
    print("  HUBSPOT_PORTAL_ID=244661638")
    print("  HUBSPOT_FORM_ID=0451cb1c-53b3-47d6-abf4-338f73832a88")
    print("  HUBSPOT_REGION=na2")

print("\n" + "=" * 60)
