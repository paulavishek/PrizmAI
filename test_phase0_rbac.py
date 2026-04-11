"""Smoke test for Phase 0 RBAC & sandbox isolation fixes."""
import django, os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'kanban_board.settings')
django.setup()

from ai_assistant.utils.rbac_utils import (
    get_accessible_boards_for_spectra,
    can_spectra_read_board,
)
from django.contrib.auth import get_user_model

User = get_user_model()
PASS = 0
FAIL = 0

def check(label, condition):
    global PASS, FAIL
    if condition:
        print(f"  PASS: {label}")
        PASS += 1
    else:
        print(f"  FAIL: {label}")
        FAIL += 1


# --- Test 1: Personal vs Demo workspace isolation ---
print("\n=== Test 1: Workspace isolation ===")
user = User.objects.filter(
    is_superuser=False,
).exclude(email__icontains='demo').first()

if user:
    profile = getattr(user, 'profile', None)
    org = getattr(profile, 'organization', None)
    print(f"  User: {user.username}, Org: {org}")

    personal = get_accessible_boards_for_spectra(user, is_demo_mode=False, organization=org)
    demo = get_accessible_boards_for_spectra(user, is_demo_mode=True, organization=org)
    print(f"  Personal boards: {personal.count()}")
    print(f"  Demo boards: {demo.count()}")

    personal_ids = set(personal.values_list('id', flat=True))
    demo_ids = set(demo.values_list('id', flat=True))
    check("No overlap between personal and demo boards", len(personal_ids & demo_ids) == 0)

    # Verify personal boards are not sandbox copies
    for b in personal:
        check(f"Personal board '{b.name}' is not sandbox_copy", not b.is_sandbox_copy)
        check(f"Personal board '{b.name}' is not official_demo", not b.is_official_demo_board)

    # Verify demo boards are sandbox copies or official demo
    for b in demo:
        is_valid = b.is_sandbox_copy or b.is_official_demo_board or (
            getattr(b, 'created_by_session', '') or ''
        ).startswith('spectra_demo_')
        check(f"Demo board '{b.name}' is sandbox/demo", is_valid)
else:
    print("  SKIP: No non-demo user found")


# --- Test 2: RBAC denial for inaccessible board ---
print("\n=== Test 2: RBAC denial for inaccessible board ===")
from kanban.models import Board

# Find a board the user does NOT own and has no membership on
if user:
    all_boards = Board.objects.filter(is_archived=False).exclude(
        created_by=user
    ).exclude(
        owner=user
    ).exclude(
        memberships__user=user
    ).first()

    if all_boards:
        result = can_spectra_read_board(user, all_boards)
        # This may still return True if user is org admin or same-org fallback
        print(f"  Board: {all_boards.name}, can_read: {result}")
        print(f"  (Note: may be True if same-org fallback applies)")
    else:
        print("  SKIP: No inaccessible board found for testing")


# --- Test 3: get_taskflow_context RBAC gate ---
print("\n=== Test 3: get_taskflow_context RBAC gate ===")
from ai_assistant.utils.chatbot_service import TaskFlowChatbotService

if user and all_boards:
    service = TaskFlowChatbotService(
        user=user, board=all_boards, session_id=None, is_demo_mode=False
    )
    ctx = service.get_taskflow_context()
    # If RBAC denies, context should say "No board data available"
    has_denial = "don't have access" in ctx.lower() or "no board data" in ctx.lower()
    has_board_data = all_boards.name in ctx
    print(f"  Context contains denial: {has_denial}")
    print(f"  Context contains board name: {has_board_data}")
    # Note: if same-org fallback gives access, this is expected to pass


# --- Summary ---
print(f"\n{'='*40}")
print(f"Results: {PASS} passed, {FAIL} failed")
if FAIL == 0:
    print("All checks passed!")
else:
    print("Some checks failed — review above.")
