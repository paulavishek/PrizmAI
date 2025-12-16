"""
Test script to verify auto-progress update when moving tasks to Done/Complete columns
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'kanban_board.settings')
django.setup()

from kanban.models import Task, Column, Board
from django.db import models

print("=" * 70)
print("Testing Auto-Progress Update for Done/Complete Columns")
print("=" * 70)

# Find all boards with Done/Complete columns
boards = Board.objects.filter(
    columns__name__iregex=r'(done|complete)'
).distinct()

if not boards.exists():
    print("\n❌ No boards found with Done/Complete columns.")
    exit()

print(f"\nFound {boards.count()} boards with Done/Complete columns:")
for board in boards:
    print(f"  - {board.name}")

# Test: Create a test task and move it to Done
test_board = boards.first()
print(f"\n📋 Testing with board: {test_board.name}")

# Find a Done/Complete column
done_column = test_board.columns.filter(
    models.Q(name__icontains='done') | models.Q(name__icontains='complete')
).first()

if not done_column:
    print("❌ No Done/Complete column found in this board.")
    exit()

print(f"✅ Found column: {done_column.name}")

# Find a non-done column for testing
other_column = test_board.columns.exclude(id=done_column.id).first()
if not other_column:
    print("❌ No other columns found for testing.")
    exit()

print(f"✅ Found other column for testing: {other_column.name}")

# Create a test task with low progress
test_task = Task.objects.create(
    title="[TEST] Progress Auto-Update Test",
    description="This is a test task to verify auto-progress update",
    column=other_column,
    created_by=test_board.created_by,
    progress=25,
    position=9999
)

print(f"\n✅ Created test task #{test_task.id}: {test_task.title}")
print(f"   Initial progress: {test_task.progress}%")
print(f"   Initial column: {test_task.column.name}")

# Move task to Done column
print(f"\n🔄 Moving task to '{done_column.name}' column...")
test_task.column = done_column
test_task.save()

# Refresh from database to get updated values
test_task.refresh_from_db()

print(f"✅ Task moved successfully!")
print(f"   Current column: {test_task.column.name}")
print(f"   Current progress: {test_task.progress}%")

# Verify the progress was updated
if test_task.progress == 100:
    print("\n✅ SUCCESS! Progress was automatically updated to 100%")
else:
    print(f"\n❌ FAILED! Progress is still {test_task.progress}% (expected 100%)")

# Clean up: Delete the test task
print(f"\n🧹 Cleaning up test task #{test_task.id}...")
test_task.delete()
print("✅ Test task deleted")

print("\n" + "=" * 70)
print("Test completed!")
print("=" * 70)
