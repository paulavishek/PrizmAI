"""Quick check: find users with boards for testing."""
import django, os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'kanban_board.settings')
django.setup()
from django.contrib.auth import get_user_model
from kanban.models import Board
User = get_user_model()

for u in User.objects.filter(is_superuser=False)[:15]:
    p = getattr(u, 'profile', None)
    org = getattr(p, 'organization', None) if p else None
    owned = Board.objects.filter(owner=u).count()
    sandbox = Board.objects.filter(owner=u, is_sandbox_copy=True).count()
    member = Board.objects.filter(memberships__user=u).count()
    print(f"{u.username:20s} | org={str(org):30s} | owned={owned} | sandbox={sandbox} | member_of={member} | email={u.email}")
