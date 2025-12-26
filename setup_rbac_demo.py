"""
Setup RBAC Demo Features
Makes all enhanced permission features visible and testable in demo boards
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'kanban_board.settings')
django.setup()

from django.contrib.auth.models import User
from kanban.models import Board, Column, Task
from kanban.permission_models import Role, BoardMembership, ColumnPermission
from accounts.models import Organization

print("=" * 80)
print("ENHANCED RBAC DEMO SETUP")
print("Setting up permission features for demo boards")
print("=" * 80)

# Get demo boards
demo_orgs = Organization.objects.filter(name__in=['Dev Team', 'Marketing Team'])
demo_boards = Board.objects.filter(organization__in=demo_orgs)

if not demo_boards.exists():
    print("\n❌ No demo boards found. Please run demo data setup first.")
    exit(1)

print(f"\n✓ Found {demo_boards.count()} demo boards")

# For each demo board, set up RBAC features
for board in demo_boards:
    print(f"\n{'='*80}")
    print(f"📋 Setting up: {board.name}")
    print(f"   Organization: {board.organization.name}")
    print(f"{'='*80}")
    
    # Ensure we have the workflow columns
    print("\n[1/5] Checking columns...")
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
    
    # Get roles
    print("\n[2/5] Setting up roles...")
    member_role = Role.objects.filter(
        organization=board.organization,
        name='Member'
    ).first()
    
    admin_role = Role.objects.filter(
        organization=board.organization,
        name='Admin'
    ).first()
    
    editor_role = Role.objects.filter(
        organization=board.organization,
        name='Editor'
    ).first()
    
    if not all([member_role, admin_role, editor_role]):
        print(f"  ⚠ Some roles missing, creating defaults...")
        Role.create_default_roles(board.organization)
        member_role = Role.objects.get(organization=board.organization, name='Member')
        admin_role = Role.objects.get(organization=board.organization, name='Admin')
        editor_role = Role.objects.get(organization=board.organization, name='Editor')
    
    print(f"  ✓ Member role: {member_role.name}")
    print(f"  ✓ Editor role: {editor_role.name}")
    print(f"  ✓ Admin role: {admin_role.name}")
    
    # Set up approval workflow on columns
    print("\n[3/5] Setting up approval workflow...")
    
    # Members can't move to Review (prevents self-review)
    if 'Review' in columns:
        review_perm, created = ColumnPermission.objects.get_or_create(
            column=columns['Review'],
            role=member_role,
            defaults={
                'can_move_to': False,
                'can_move_from': True,
                'can_create_in': False,
                'can_edit_in': True
            }
        )
        status = "✓ Created" if created else "- Updated"
        print(f"  {status}: Members CANNOT move to 'Review' (approval required)")
    
    # Members can't move to Done (requires approval)
    if 'Done' in columns:
        done_perm, created = ColumnPermission.objects.get_or_create(
            column=columns['Done'],
            role=member_role,
            defaults={
                'can_move_to': False,
                'can_move_from': False,
                'can_create_in': False,
                'can_edit_in': False
            }
        )
        status = "✓ Created" if created else "- Updated"
        print(f"  {status}: Members CANNOT move to 'Done' (approval required)")
    
    # Members have full access to To Do and In Progress
    for col_name in ['To Do', 'In Progress']:
        if col_name in columns:
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
            print(f"  {status}: Members have full access to '{col_name}'")
    
    # Assign different roles to existing board members (for demo purposes)
    print("\n[4/5] Assigning demo roles to members...")
    members = board.members.all()[:10]  # Get first 10 members
    role_assignment_count = 0
    
    for idx, member in enumerate(members):
        # Assign different roles to demonstrate RBAC
        # First member: Admin
        # Next few: Editor (default)
        # Last few: Member (restricted)
        
        if idx == 0:
            # First member is Admin
            role_to_assign = admin_role
        elif idx < 5:
            # Next 4 are Editors (full access)
            role_to_assign = editor_role
        else:
            # Rest are Members (restricted)
            role_to_assign = member_role
        
        membership, created = BoardMembership.objects.update_or_create(
            board=board,
            user=member,
            defaults={
                'role': role_to_assign,
                'added_by': board.created_by
            }
        )
        
        if created or membership.role != role_to_assign:
            role_assignment_count += 1
            print(f"  ✓ {member.username}: {role_to_assign.name}")
    
    print(f"\n  📊 Assigned roles to {role_assignment_count} members")
    
    # Create some demo tasks in different columns
    print("\n[5/5] Ensuring demo tasks exist...")
    task_count = Task.objects.filter(column__board=board).count()
    
    if task_count < 5:
        print("  📝 Creating demo tasks...")
        task_titles = [
            ("Implement login feature", "To Do"),
            ("Fix navigation bug", "In Progress"),
            ("Review API documentation", "Review"),
            ("Deploy to production", "Done"),
            ("Write unit tests", "To Do"),
        ]
        
        for title, col_name in task_titles:
            if col_name in columns:
                task, created = Task.objects.get_or_create(
                    title=title,
                    column=columns[col_name],
                    defaults={
                        'created_by': board.created_by,
                        'description': f'Demo task to showcase RBAC workflow',
                        'priority': 'medium',
                        'progress': 0 if col_name in ['To Do', 'In Progress'] else 100
                    }
                )
                if created:
                    print(f"    ✓ Created: '{title}' in {col_name}")
    else:
        print(f"  ✓ Board already has {task_count} tasks")

# Summary
print("\n" + "=" * 80)
print("📊 DEMO SETUP SUMMARY")
print("=" * 80)

total_boards = demo_boards.count()
total_columns = Column.objects.filter(board__in=demo_boards).count()
total_restrictions = ColumnPermission.objects.filter(
    column__board__in=demo_boards
).count()
total_memberships = BoardMembership.objects.filter(
    board__in=demo_boards
).count()

print(f"\n✅ Demo Boards: {total_boards}")
print(f"✅ Workflow Columns: {total_columns}")
print(f"✅ Column Restrictions: {total_restrictions}")
print(f"✅ Board Memberships: {total_memberships}")

print("\n" + "=" * 80)
print("🎯 WHAT DEMO USERS WILL EXPERIENCE")
print("=" * 80)

print("\n1. 📋 ROLE VISIBILITY")
print("   - See role badge in board header (Member/Editor/Admin)")
print("   - Different users get different roles")
print("   - Role determines what they can do")

print("\n2. 🔒 COLUMN RESTRICTIONS")
print("   - Members see 'Restricted' badges on Review/Done columns")
print("   - Yellow warning badges indicate limitations")
print("   - Clear visual feedback before attempting actions")

print("\n3. 🚫 WORKFLOW ENFORCEMENT")
print("   - Members CANNOT move tasks to Review or Done")
print("   - Error messages explain why action was blocked")
print("   - Admins/Editors can move tasks anywhere")

print("\n4. 👥 MEMBER MANAGEMENT")
print("   - Access via board settings → 'Manage Members & Roles'")
print("   - See all members with their assigned roles")
print("   - Change roles via dropdown (if admin)")

print("\n5. 📊 PERMISSION AUDIT LOG")
print("   - Access via board settings → 'Permission Audit Log'")
print("   - See history of all permission changes")
print("   - Filter by action type, date, user")

print("\n6. 🎨 VISUAL INDICATORS")
print("   - Info banner at top explains restrictions")
print("   - Lock icons on restricted columns")
print("   - Role badge always visible")
print("   - Clear error messages on permission denial")

print("\n" + "=" * 80)
print("🚀 HOW TO TEST THE DEMO")
print("=" * 80)

print("\n1. Log in and go to: http://localhost:8000/demo/")
print("\n2. Click on any demo board (e.g., 'Software Project')")
print("\n3. Notice:")
print("   - Your role badge in the header")
print("   - Blue info banner with restrictions")
print("   - 🔒 badges on Review/Done columns")
print("\n4. Try to drag a task to 'Done' column")
print("   - If you're a Member: You'll see an error")
print("   - If you're an Admin/Editor: It will work")
print("\n5. Go to Board Settings → 'Manage Members & Roles'")
print("   - See all members with their roles")
print("   - Change someone's role (if you're admin)")
print("\n6. Go to Board Settings → 'Permission Audit Log'")
print("   - See history of permission changes")

print("\n" + "=" * 80)
print("✅ RBAC DEMO SETUP COMPLETE!")
print("=" * 80)
print("\nAll enhanced permission features are now visible in demo boards.")
print("Users can experience the full RBAC system without affecting real data.")
print("\n🎉 Demo is ready for testing!")
