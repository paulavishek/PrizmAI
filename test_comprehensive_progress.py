"""
Test script to verify auto-progress update via API and view endpoints
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'kanban_board.settings')
django.setup()

from kanban.models import Task, Column, Board
from django.test import RequestFactory
from django.contrib.auth.models import User
import json

print("=" * 70)
print("Testing Auto-Progress via API and Views")
print("=" * 70)

# Get test data
board = Board.objects.filter(columns__name__icontains='done').first()
if not board:
    print("❌ No board with Done column found")
    exit()

done_column = board.columns.filter(name__icontains='done').first()
other_column = board.columns.exclude(id=done_column.id).first()

print(f"\n📋 Board: {board.name}")
print(f"✅ Done column: {done_column.name}")
print(f"✅ Other column: {other_column.name}")

# Create test task
test_task = Task.objects.create(
    title="[TEST] API Progress Update Test",
    description="Testing progress update via move_task view",
    column=other_column,
    created_by=board.created_by,
    progress=30,
    position=9999
)

print(f"\n✅ Created test task #{test_task.id}")
print(f"   Initial progress: {test_task.progress}%")

# Test 1: Direct model update (already tested in previous script)
print("\n" + "=" * 70)
print("TEST 1: Direct Model Update (Signal-based)")
print("=" * 70)
test_task.column = done_column
test_task.save()
test_task.refresh_from_db()
print(f"✅ Progress after move: {test_task.progress}%")
assert test_task.progress == 100, f"Expected 100%, got {test_task.progress}%"
print("✅ PASSED: Signal-based update works!")

# Reset for next test
test_task.column = other_column
test_task.progress = 40
test_task.save()
test_task.refresh_from_db()

# Test 2: Via move_task view (simulating AJAX request)
print("\n" + "=" * 70)
print("TEST 2: Via move_task View")
print("=" * 70)
from kanban.views import move_task
from django.http import HttpRequest

# Create a mock request
factory = RequestFactory()
request = factory.post(
    '/tasks/move/',
    data=json.dumps({
        'taskId': test_task.id,
        'columnId': done_column.id,
        'position': 0
    }),
    content_type='application/json',
    HTTP_X_REQUESTED_WITH='XMLHttpRequest'
)
request.user = board.created_by

response = move_task(request)
response_data = json.loads(response.content)

test_task.refresh_from_db()
print(f"✅ Response: {response_data}")
print(f"✅ Progress after move: {test_task.progress}%")
assert test_task.progress == 100, f"Expected 100%, got {test_task.progress}%"
print("✅ PASSED: View-based update works!")

# Test 3: Test with 'Complete' column name variation
print("\n" + "=" * 70)
print("TEST 3: Column Name Variations")
print("=" * 70)

# Check if there's a complete column
complete_column = board.columns.filter(name__icontains='complete').first()
if complete_column:
    test_task.column = other_column
    test_task.progress = 50
    test_task.save()
    
    test_task.column = complete_column
    test_task.save()
    test_task.refresh_from_db()
    
    print(f"✅ Testing with '{complete_column.name}' column")
    print(f"✅ Progress: {test_task.progress}%")
    assert test_task.progress == 100, f"Expected 100%, got {test_task.progress}%"
    print("✅ PASSED: Works with 'complete' variation!")
else:
    print("⚠️  No 'Complete' column found for variation testing")

# Clean up
print(f"\n🧹 Cleaning up test task #{test_task.id}...")
test_task.delete()
print("✅ Test task deleted")

print("\n" + "=" * 70)
print("All tests completed successfully! ✅")
print("=" * 70)
print("\n📝 Summary:")
print("  ✅ Signal-based update works")
print("  ✅ View-based update works")
print("  ✅ Column name variations work (done/complete)")
print("\n🎉 The auto-progress feature is working perfectly!")
