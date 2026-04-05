import django, os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'kanban_board.settings')
django.setup()

from kanban.models import Board
from kanban.preset_models import BoardPreset, WorkspacePreset
from accounts.models import Organization

b = Board.objects.get(id=24)
print("Board 24:", b.name)
print("  org_id:", b.organization_id)
print("  org:", b.organization)
print("  owner:", b.owner)
print("  created_by:", b.created_by)
print("  is_demo:", getattr(b, 'is_official_demo_board', False))

bp = BoardPreset.objects.filter(board=b).first()
if bp:
    print("  BoardPreset local:", bp.local_preset)
    print("  BoardPreset effective:", bp.effective_preset())
else:
    print("  BoardPreset: NONE")

if b.organization:
    wp = WorkspacePreset.objects.filter(organization=b.organization).first()
    if wp:
        print("  WorkspacePreset global:", wp.global_preset)
    else:
        print("  WorkspacePreset: NONE for org", b.organization)
else:
    print("  No organization on this board")

print()
print("All WorkspacePresets:")
for wp in WorkspacePreset.objects.select_related('organization').all():
    print(f"  org={wp.organization} (id={wp.organization_id}) preset={wp.global_preset}")

print()
print("All boards:")
for board in Board.objects.all().order_by('id'):
    demo = getattr(board, 'is_official_demo_board', False)
    print(f"  id={board.id}  org_id={board.organization_id}  demo={demo}  name={board.name}")
