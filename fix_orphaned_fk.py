"""Fix orphaned foreign key references before migration"""
from django.contrib.auth.models import User
from kanban.stakeholder_models import ProjectStakeholder

# Get the first available user (admin or any user)
admin_user = User.objects.first()

if admin_user:
    # Update orphaned records to point to an existing user
    updated = ProjectStakeholder.objects.filter(created_by_id=6).update(created_by_id=admin_user.id)
    print(f"Fixed {updated} orphaned ProjectStakeholder record(s), assigned to user: {admin_user.username}")
else:
    # If no users exist, set to NULL (if the field allows it)
    updated = ProjectStakeholder.objects.filter(created_by_id=6).update(created_by_id=None)
    print(f"Fixed {updated} orphaned ProjectStakeholder record(s), set created_by to NULL")
