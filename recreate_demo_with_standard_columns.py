"""
Quick script to recreate demo boards with standardized columns
Run this after updating the management commands
"""
import os
import sys
import django

# Setup Django environment
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'prizmAI.settings')
django.setup()

from django.core.management import call_command

print("="*80)
print("RECREATING DEMO BOARDS WITH STANDARDIZED COLUMNS")
print("="*80)
print()
print("This will:")
print("  1. Delete existing demo organization and all demo data")
print("  2. Create new demo organization with standardized columns (To Do, In Progress, Done)")
print("  3. Populate demo boards with tasks")
print()

response = input("Continue? (yes/no): ").strip().lower()

if response != 'yes':
    print("\nCancelled.")
    sys.exit(0)

print("\n" + "="*80)
print("Step 1: Recreating demo organization...")
print("="*80)
call_command('create_demo_organization', '--reset')

print("\n" + "="*80)
print("Step 2: Populating demo boards with tasks...")
print("="*80)
call_command('populate_demo_data')

print("\n" + "="*80)
print("✅ COMPLETE!")
print("="*80)
print()
print("All demo boards now have standardized columns:")
print("  • To Do (with 'Add Task' button)")
print("  • In Progress")
print("  • Done")
print()
print("Visit /demo/ to test the new experience!")
print()
