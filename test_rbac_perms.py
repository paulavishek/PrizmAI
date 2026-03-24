"""Quick RBAC permission test — delete after use."""
import os, django
os.environ['DJANGO_SETTINGS_MODULE'] = 'kanban_board.settings'
django.setup()

from kanban.models import Board, BoardMembership
from django.contrib.auth.models import User
# Force kanban.permissions to load (registers rules)
import kanban.permissions

user = User.objects.get(username='testuser1')

# ── Test 1: Board where user is OWNER ──
board = Board.objects.filter(owner=user).first()
print(f'=== Owner test: {user.username} on "{board.name}" ===')
print(f'  view_board:   {user.has_perm("prizmai.view_board", board)}')  # True
print(f'  edit_board:   {user.has_perm("prizmai.edit_board", board)}')  # True
print(f'  delete_board: {user.has_perm("prizmai.delete_board", board)}')  # True
print(f'  invite:       {user.has_perm("prizmai.invite_board_member", board)}')  # True

# ── Test 2: Board where user is MEMBER only ──
member_board = Board.objects.filter(memberships__user=user, memberships__role='member').first()
if member_board:
    print(f'\n=== Member test: {user.username} on "{member_board.name}" ===')
    print(f'  view_board:   {user.has_perm("prizmai.view_board", member_board)}')  # True
    print(f'  edit_board:   {user.has_perm("prizmai.edit_board", member_board)}')  # True
    print(f'  delete_board: {user.has_perm("prizmai.delete_board", member_board)}')  # False
    print(f'  invite:       {user.has_perm("prizmai.invite_board_member", member_board)}')  # False

# ── Test 3: Demo board ──
demo_board = Board.objects.filter(is_official_demo_board=True).first()
if demo_board:
    print(f'\n=== Demo board test: {user.username} on "{demo_board.name}" ===')
    print(f'  view_board:   {user.has_perm("prizmai.view_board", demo_board)}')  # True
    print(f'  edit_board:   {user.has_perm("prizmai.edit_board", demo_board)}')  # True
    print(f'  delete_board: {user.has_perm("prizmai.delete_board", demo_board)}')  # depends

# ── Test 4: User with NO access to a board ──
other_user = User.objects.exclude(pk=user.pk).first()
if other_user and board:
    has_mem = BoardMembership.objects.filter(board=board, user=other_user).exists()
    print(f'\n=== No-access test: {other_user.username} on "{board.name}" (membership={has_mem}) ===')
    print(f'  view_board:   {other_user.has_perm("prizmai.view_board", board)}')  # False
    print(f'  edit_board:   {other_user.has_perm("prizmai.edit_board", board)}')  # False
    print(f'  delete_board: {other_user.has_perm("prizmai.delete_board", board)}')  # False
    print(f'  invite:       {other_user.has_perm("prizmai.invite_board_member", board)}')  # False

print('\nAll tests completed.')
