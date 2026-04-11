"""Debug why personal mode returns 0 for testuser1."""
import django, os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'kanban_board.settings')
django.setup()
from kanban.models import Board
from django.contrib.auth import get_user_model
from django.db.models import Q

u = get_user_model().objects.get(username='testuser1')
org = u.profile.organization
print(f"User org: {org} (id={org.id if org else None})")

# Step by step filter debug
base = Board.objects.filter(is_archived=False)
print(f"Base (non-archived): {base.count()}")

# Filter by membership
membership_qs = base.filter(
    Q(created_by=u) | Q(owner=u) | Q(memberships__user=u)
)
print(f"With membership: {membership_qs.count()}")

# Filter by org
with_org = membership_qs.filter(organization=org)
print(f"With org filter: {with_org.count()}")

# Filter by workspace
with_ws = with_org.filter(Q(workspace__is_demo=False) | Q(workspace__isnull=True))
print(f"With workspace filter: {with_ws.count()}")

# Exclude demo artifacts
final = with_ws.exclude(
    created_by_session__startswith='spectra_demo_'
).exclude(
    is_official_demo_board=True
).exclude(
    is_sandbox_copy=True
).distinct()
print(f"Final (after excludes): {final.count()}")
for b in final:
    print(f"  {b.name}")

# Check: do these boards have the right org?
for b in membership_qs:
    print(f"  Board: {b.name} | org_id={b.organization_id} | user_org_id={org.id if org else None} | match={b.organization_id == (org.id if org else None)}")
