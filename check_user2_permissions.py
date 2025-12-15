"""Check user2's board access and permissions"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'kanban_board.settings')
django.setup()

from django.contrib.auth.models import User
from kanban.models import Board
from kanban.permission_models import BoardMembership, Role

u = User.objects.get(username='user2')
boards = Board.objects.filter(members=u)

print('=== USER2 BOARD ACCESS ===\n')
print(f'User: {u.username}')
print(f'Organization: {u.profile.organization.name}')
print(f'Is admin: {u.profile.is_admin}\n')

for board in boards:
    print(f'\nBoard: {board.name} ({board.organization.name})')
    print(f'  Created by: {board.created_by.username}')
    print(f'  Total members: {board.members.count()}')
    
    # Check BoardMembership
    membership = BoardMembership.objects.filter(board=board, user=u).first()
    if membership:
        print(f'  ✓ BoardMembership exists')
        print(f'    Role: {membership.role.name if membership.role else "NO ROLE"}')
        print(f'    Added: {membership.added_at}')
    else:
        print(f'  ✗ NO BoardMembership record (just in members list)')

print('\n\n=== AVAILABLE ROLES ===')
roles = Role.objects.all()
for role in roles:
    print(f'  {role.name} (org: {role.organization.name if role.organization else "Global"})')

print('\n\n=== DEMO DATA CHECK ===')
# Check messages
try:
    from messaging.models import ChatMessage, ChatRoom
    room_count = ChatRoom.objects.filter(board__in=boards).count()
    msg_count = ChatMessage.objects.filter(chat_room__board__in=boards).count()
    print(f'Chat rooms in demo boards: {room_count}')
    print(f'Messages in demo boards: {msg_count}')
except Exception as e:
    print(f'Messages check failed: {e}')

# Check conflicts
try:
    from kanban.conflict_models import ConflictDetection
    conflict_count = ConflictDetection.objects.filter(board__in=boards).count()
    print(f'Conflicts in demo boards: {conflict_count}')
except Exception as e:
    print(f'Conflicts check failed: {e}')

# Check wiki pages
try:
    from wiki.models import WikiPage
    wiki_count = WikiPage.objects.filter(organization__in=[b.organization for b in boards]).count()
    print(f'Wiki pages for demo orgs: {wiki_count}')
except Exception as e:
    print(f'Wiki check failed: {e}')
