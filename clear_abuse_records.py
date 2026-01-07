"""
Clear demo abuse prevention records for local development.
This allows unlimited demo sessions during testing.

DEVELOPMENT ONLY - Do not run on production!
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'kanban_board.settings')
django.setup()

from analytics.models import DemoAbusePrevention, DemoSession
from django.db import models

print("\n" + "=" * 80)
print("CLEARING DEMO ABUSE PREVENTION RECORDS")
print("=" * 80)

# Get counts before deletion
abuse_count = DemoAbusePrevention.objects.count()
session_count = DemoSession.objects.count()

print(f"\nCurrent records:")
print(f"  - Abuse Prevention Records: {abuse_count}")
print(f"  - Demo Sessions: {session_count}")

# Show some details about abuse records
if abuse_count > 0:
    print(f"\nAbuse Prevention Records:")
    for record in DemoAbusePrevention.objects.all()[:5]:
        print(f"  - IP: {record.ip_address}")
        print(f"    Sessions Created: {record.total_sessions_created}")
        print(f"    AI Generations: {record.total_ai_generations}")
        print(f"    Flagged: {record.is_flagged}")
        print(f"    Blocked: {record.is_blocked}")

# Ask for confirmation
confirm = input(f"\n⚠️  Delete all {abuse_count} abuse prevention records? (yes/no): ")

if confirm.lower() == 'yes':
    # Delete all abuse prevention records
    DemoAbusePrevention.objects.all().delete()
    print(f"\n✅ Deleted {abuse_count} abuse prevention records")
    
    # Optionally clear demo sessions
    clear_sessions = input(f"\nAlso clear {session_count} demo session records? (yes/no): ")
    if clear_sessions.lower() == 'yes':
        DemoSession.objects.all().delete()
        print(f"✅ Deleted {session_count} demo session records")
    
    print("\n" + "=" * 80)
    print("✅ ABUSE PREVENTION CLEARED")
    print("=" * 80)
    print("\nYou can now access demo mode without restrictions.")
    print("Refresh your browser and try again.")
else:
    print("\n❌ Operation cancelled")

print("\n" + "=" * 80)
