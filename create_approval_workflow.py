"""
Create Approval Workflow Example
Sets up column permissions so members can't self-approve tasks
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'kanban_board.settings')
django.setup()

from django.contrib.auth.models import User
from kanban.models import Board, Column
from kanban.permission_models import Role, ColumnPermission

print("=" * 80)
print("CREATING APPROVAL WORKFLOW")
print("=" * 80)

# Get a demo board to apply approval workflow
boards = Board.objects.filter(organization__name__in=['Dev Team', 'Marketing Team'])

if not boards.exists():
    print("\n❌ No demo boards found. Please load demo data first.")
    exit(1)

board = boards.first()
print(f"\n📋 Setting up approval workflow for: {board.name}")
print(f"   Organization: {board.organization.name}")

# Get or create workflow columns
print("\n[1/4] Checking/Creating workflow columns...")
column_names = ['To Do', 'In Progress', 'Review', 'Done']
columns = {}

for name in column_names:
    column, created = Column.objects.get_or_create(
        board=board,
        name=name,
        defaults={'position': len(columns)}
    )
    columns[name] = column
    status = "✓ Created" if created else "- Exists"
    print(f"  {status}: {name}")

# Get Member and Admin roles
print("\n[2/4] Getting roles...")
member_role = Role.objects.filter(
    organization=board.organization,
    name='Member'
).first()

admin_role = Role.objects.filter(
    organization=board.organization,
    name='Admin'
).first()

if not member_role or not admin_role:
    print("  ❌ Required roles not found")
    exit(1)

print(f"  ✓ Member role: {member_role.name}")
print(f"  ✓ Admin role: {admin_role.name}")

# Set up approval workflow restrictions
print("\n[3/4] Setting up approval workflow restrictions...")

# Members can't move tasks INTO Review (they must be reviewed by someone else)
review_perm, created = ColumnPermission.objects.get_or_create(
    column=columns['Review'],
    role=member_role,
    defaults={
        'can_move_to': False,      # ❌ Can't move to Review (no self-submit for review)
        'can_move_from': True,     # ✓ Can move out (fix issues)
        'can_create_in': False,    # ❌ Can't create directly in Review
        'can_edit_in': True        # ✓ Can edit (fix review comments)
    }
)
if created:
    print("  ✓ Created: Members CANNOT move tasks to Review")
else:
    print("  - Updated: Members CANNOT move tasks to Review")

# Members can't move tasks INTO Done (requires approval)
done_perm, created = ColumnPermission.objects.get_or_create(
    column=columns['Done'],
    role=member_role,
    defaults={
        'can_move_to': False,      # ❌ Can't move to Done (requires approval)
        'can_move_from': False,    # ❌ Can't reopen (must ask admin)
        'can_create_in': False,    # ❌ Can't create in Done
        'can_edit_in': False       # ❌ Can't edit completed tasks
    }
)
if created:
    print("  ✓ Created: Members CANNOT move tasks to Done or reopen")
else:
    print("  - Updated: Members CANNOT move tasks to Done or reopen")

# Members CAN work freely in To Do and In Progress
for col_name in ['To Do', 'In Progress']:
    perm, created = ColumnPermission.objects.get_or_create(
        column=columns[col_name],
        role=member_role,
        defaults={
            'can_move_to': True,
            'can_move_from': True,
            'can_create_in': True,
            'can_edit_in': True
        }
    )
    status = "✓ Created" if created else "- Updated"
    print(f"  {status}: Members have full access to {col_name}")

# Admins have full access to ALL columns (no restrictions)
print("\n  ℹ️  Admins have full access to all columns (no restrictions needed)")

# Summary
print("\n[4/4] Approval Workflow Summary:")
print("=" * 80)
print("\n  📊 WORKFLOW STAGES:")
print("  1. To Do        → Members: Full access")
print("  2. In Progress  → Members: Full access")
print("  3. Review       → Members: Cannot submit for review (prevents self-review)")
print("  4. Done         → Members: Cannot approve (requires admin/reviewer)")
print("\n  🔐 PERMISSION LOGIC:")
print("  ✓ Members work on tasks in 'To Do' and 'In Progress'")
print("  ✓ When ready, they move to 'In Progress' and complete work")
print("  ❌ Members CANNOT move to 'Review' (must be reviewed by team lead)")
print("  ❌ Members CANNOT move to 'Done' (requires approval)")
print("  ✓ Admins/Reviewers move tasks from 'In Progress' → 'Review' → 'Done'")
print("\n  💡 BENEFIT:")
print("  - Enforces code review / approval process")
print("  - Prevents premature task closure")
print("  - Maintains quality control")
print("  - Clear separation of duties")

print("\n" + "=" * 80)
print("✅ Approval Workflow Created Successfully!")
print("=" * 80)

print("\n📝 NEXT STEPS:")
print("  1. Assign some users the 'Member' role")
print("  2. Try moving a task as a Member - you'll see restrictions")
print("  3. Log in as Admin to approve tasks")
print("  4. View permission audit log: /permissions/audit/")

print("\n🔗 QUICK LINKS:")
print(f"  Board: http://localhost:8000/boards/{board.id}/")
print(f"  Manage Members: http://localhost:8000/board/{board.id}/members/manage/")
print(f"  Role Management: http://localhost:8000/permissions/roles/")
