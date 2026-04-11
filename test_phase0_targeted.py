"""Targeted Phase 0 RBAC & Sandbox test with real users who have boards."""
import django, os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'kanban_board.settings')
django.setup()

from ai_assistant.utils.rbac_utils import get_accessible_boards_for_spectra
from django.contrib.auth import get_user_model
from kanban.models import Board

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


# Test with testuser1 who has both sandbox and personal boards
user1 = User.objects.get(username='testuser1')
org1 = user1.profile.organization

print("=== Test 1: testuser1 workspace isolation ===")
personal = get_accessible_boards_for_spectra(user1, is_demo_mode=False, organization=org1)
demo = get_accessible_boards_for_spectra(user1, is_demo_mode=True, organization=org1)

print(f"  Personal boards ({personal.count()}):")
for b in personal:
    print(f"    - {b.name} (sandbox={b.is_sandbox_copy}, demo={b.is_official_demo_board}, ws_demo={getattr(b.workspace, 'is_demo', 'N/A') if b.workspace else 'no_ws'})")

print(f"  Demo boards ({demo.count()}):")
for b in demo:
    print(f"    - {b.name} (sandbox={b.is_sandbox_copy}, owner={b.owner}, ws_demo={getattr(b.workspace, 'is_demo', 'N/A') if b.workspace else 'no_ws'})")

personal_ids = set(personal.values_list('id', flat=True))
demo_ids = set(demo.values_list('id', flat=True))
check("No overlap between personal and demo", len(personal_ids & demo_ids) == 0)

# Verify no sandbox boards in personal
for b in personal:
    check(f"Personal '{b.name}' not sandbox_copy", not b.is_sandbox_copy)

# Verify demo boards are valid sandbox/demo
for b in demo:
    is_valid = b.is_sandbox_copy or b.is_official_demo_board
    check(f"Demo '{b.name}' is sandbox or official_demo", is_valid)


print("\n=== Test 2: testuser2 can't see testuser1's sandbox ===")
user2 = User.objects.get(username='testuser2')
org2 = user2.profile.organization

demo2 = get_accessible_boards_for_spectra(user2, is_demo_mode=True, organization=org2)
print(f"  testuser2 demo boards ({demo2.count()}):")
for b in demo2:
    print(f"    - {b.name} (owner={b.owner})")

# testuser2's demo boards should only be owned by testuser2 or be official demos
for b in demo2:
    if b.is_sandbox_copy:
        check(f"Sandbox '{b.name}' owned by testuser2", b.owner_id == user2.id)
    else:
        check(f"Board '{b.name}' is official demo", b.is_official_demo_board)

# Check testuser1's sandbox boards are NOT in testuser2's demo list
user1_sandbox = Board.objects.filter(owner=user1, is_sandbox_copy=True)
demo2_ids = set(demo2.values_list('id', flat=True))
for b in user1_sandbox:
    check(f"testuser1's sandbox '{b.name}' NOT in testuser2's demo", b.id not in demo2_ids)


print("\n=== Test 3: get_response RBAC gate in demo mode ===")
from ai_assistant.utils.chatbot_service import TaskFlowChatbotService

# Try to access testuser1's sandbox board as testuser2 in demo mode
user1_sandbox_board = Board.objects.filter(owner=user1, is_sandbox_copy=True).first()
if user1_sandbox_board:
    service = TaskFlowChatbotService(
        user=user2, board=user1_sandbox_board, session_id=None, is_demo_mode=True
    )
    response = service.get_response("Give me a summary of this board")
    is_denied = response.get('source') == 'rbac_denial' or "don't" in response.get('response', '').lower() or 'access' in response.get('response', '').lower()
    print(f"  Response source: {response.get('source')}")
    print(f"  Response text: {response.get('response', '')[:200]}")
    check("Demo sandbox isolation: testuser2 denied testuser1's board", response.get('source') == 'rbac_denial')
else:
    print("  SKIP: testuser1 has no sandbox boards")


# --- Summary ---
print(f"\n{'='*50}")
print(f"Results: {PASS} passed, {FAIL} failed")
if FAIL == 0:
    print("ALL PHASE 0 CHECKS PASSED!")
else:
    print("SOME CHECKS FAILED — review above.")
