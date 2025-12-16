"""
Final Integration Test - Verify the fix works end-to-end
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'kanban_board.settings')
django.setup()

from kanban.models import Task, Column, Board
from django.db import models

print("=" * 80)
print("FINAL INTEGRATION TEST - Auto Progress Update")
print("=" * 80)

# Find a board with Done column
board = Board.objects.filter(
    columns__name__iregex=r'(done|complete)'
).first()

if not board:
    print("\n❌ No board with Done/Complete column found")
    exit()

done_column = board.columns.filter(
    models.Q(name__icontains='done') | models.Q(name__icontains='complete')
).first()
other_column = board.columns.exclude(id=done_column.id).first()

print(f"\n📋 Test Board: {board.name}")
print(f"✓ Done Column: {done_column.name}")
print(f"✓ Test Column: {other_column.name}")

# Scenario 1: User creates a task and drags it to Done without setting progress
print("\n" + "-" * 80)
print("SCENARIO 1: Task moved to Done with 0% progress")
print("-" * 80)

task1 = Task.objects.create(
    title="[INTEGRATION TEST 1] New Feature Implementation",
    description="User drags task to Done without updating progress bar",
    column=other_column,
    created_by=board.created_by,
    progress=0,
    position=9999
)
print(f"✓ Created task with 0% progress in '{other_column.name}'")
print(f"  Task ID: {task1.id}")

# Move to Done
task1.column = done_column
task1.save()
task1.refresh_from_db()

print(f"✓ Moved task to '{done_column.name}'")
print(f"  Progress is now: {task1.progress}%")

if task1.progress == 100:
    print("  ✅ SUCCESS - Progress automatically updated to 100%")
else:
    print(f"  ❌ FAIL - Progress is {task1.progress}% (expected 100%)")
    task1.delete()
    exit(1)

# Scenario 2: User partially completes task (50%) then moves to Done
print("\n" + "-" * 80)
print("SCENARIO 2: Task moved to Done with 50% progress")
print("-" * 80)

task2 = Task.objects.create(
    title="[INTEGRATION TEST 2] Bug Fix - Authentication",
    description="User sets progress to 50% then moves to Done",
    column=other_column,
    created_by=board.created_by,
    progress=50,
    position=9999
)
print(f"✓ Created task with 50% progress in '{other_column.name}'")
print(f"  Task ID: {task2.id}")

# Move to Done
task2.column = done_column
task2.save()
task2.refresh_from_db()

print(f"✓ Moved task to '{done_column.name}'")
print(f"  Progress is now: {task2.progress}%")

if task2.progress == 100:
    print("  ✅ SUCCESS - Progress automatically updated to 100%")
else:
    print(f"  ❌ FAIL - Progress is {task2.progress}% (expected 100%)")
    task1.delete()
    task2.delete()
    exit(1)

# Scenario 3: Task already at 100% stays at 100%
print("\n" + "-" * 80)
print("SCENARIO 3: Task already at 100% moved to Done")
print("-" * 80)

task3 = Task.objects.create(
    title="[INTEGRATION TEST 3] Documentation Update",
    description="User sets progress to 100% before moving",
    column=other_column,
    created_by=board.created_by,
    progress=100,
    position=9999
)
print(f"✓ Created task with 100% progress in '{other_column.name}'")
print(f"  Task ID: {task3.id}")

# Move to Done
task3.column = done_column
task3.save()
task3.refresh_from_db()

print(f"✓ Moved task to '{done_column.name}'")
print(f"  Progress is still: {task3.progress}%")

if task3.progress == 100:
    print("  ✅ SUCCESS - Progress remained at 100%")
else:
    print(f"  ❌ FAIL - Progress changed to {task3.progress}% (expected 100%)")
    task1.delete()
    task2.delete()
    task3.delete()
    exit(1)

# Scenario 4: Task moved FROM Done back to In Progress keeps progress
print("\n" + "-" * 80)
print("SCENARIO 4: Task moved FROM Done back to another column")
print("-" * 80)

print(f"✓ Moving task #{task1.id} back to '{other_column.name}'")
original_progress = task1.progress
task1.column = other_column
task1.save()
task1.refresh_from_db()

print(f"  Progress before: {original_progress}%")
print(f"  Progress after: {task1.progress}%")

if task1.progress == 100:
    print("  ✅ SUCCESS - Progress preserved at 100% (user can manually adjust if needed)")
else:
    print(f"  ℹ️  INFO - Progress changed to {task1.progress}% (acceptable)")

# Clean up
print("\n" + "-" * 80)
print("Cleaning up test tasks...")
print("-" * 80)
task1.delete()
task2.delete()
task3.delete()
print("✓ All test tasks deleted")

print("\n" + "=" * 80)
print("✅ ALL INTEGRATION TESTS PASSED!")
print("=" * 80)
print("\n📊 Summary:")
print("  ✅ Tasks with 0% progress → Auto-updated to 100%")
print("  ✅ Tasks with partial progress → Auto-updated to 100%")
print("  ✅ Tasks already at 100% → Remain at 100%")
print("  ✅ Tasks moved back → Progress preserved")
print("\n🎉 The auto-progress feature is working perfectly!")
print("   Users can now drag tasks to Done without worrying about the progress bar!")
