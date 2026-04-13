"""Verify all Spectra Phase 6 context builder fixes."""
import os, sys, django
os.environ['DJANGO_SETTINGS_MODULE'] = 'kanban_board.settings'
sys.path.insert(0, os.path.dirname(__file__))
django.setup()

from django.contrib.auth import get_user_model
from ai_assistant.utils.chatbot_service import TaskFlowChatbotService

User = get_user_model()
user = User.objects.get(username='testuser1')
from kanban.models import Board
board = Board.objects.get(id=78)

# Simulate demo mode
service = TaskFlowChatbotService(user=user, board=board, is_demo_mode=True)

print("=" * 70)
print("FIX 1: Milestone names/dates in live snapshot")
print("=" * 70)
snapshot = service._get_live_project_snapshot_context()
if snapshot:
    if 'Milestones' in snapshot and 'Foundation Architecture' in snapshot:
        print("✅ PASS — Milestones with names and dates present")
    else:
        print("❌ FAIL — Milestone names missing")
    # Print milestone section
    for line in snapshot.split('\n'):
        if 'milestone' in line.lower() or '🏁' in line:
            print(f"  {line}")
else:
    print("❌ FAIL — Snapshot returned None")

print()
print("=" * 70)
print("FIX 2: M2M dependencies in taskflow context")
print("=" * 70)
taskflow = service.get_taskflow_context()
if taskflow and 'Dependencies:' in taskflow:
    dep_lines = [l for l in taskflow.split('\n') if 'Dependencies:' in l]
    print(f"✅ PASS — Found {len(dep_lines)} task(s) with M2M dependencies listed")
    for line in dep_lines[:5]:
        print(f"  {line.strip()}")
else:
    print("❌ FAIL — No M2M dependencies in taskflow context")

print()
print("=" * 70)
print("FIX 3: Dependency context reads M2M field")
print("=" * 70)
dep_ctx = service._get_dependency_context("What dependencies might cause delays?")
if dep_ctx:
    if 'No task dependencies' in dep_ctx:
        print("❌ FAIL — Still says 'no dependencies'")
    elif 'Task Dependencies' in dep_ctx or 'Depends On' in dep_ctx:
        # Count unique deps mentioned
        dep_lines = [l for l in dep_ctx.split('\n') if 'Depends On' in l]
        print(f"✅ PASS — Found {len(dep_lines)} dependency relationships")
        for line in dep_lines[:5]:
            print(f"  {line.strip()}")
    else:
        print("⚠️  PARTIAL — Context returned but unclear content")
        print(dep_ctx[:500])
else:
    print("❌ FAIL — Dependency context returned None")

print()
print("=" * 70)
print("FIX 4: Strategic workflow (goals/missions/strategies)")
print("=" * 70)
strat_ctx = service._get_strategic_workflow_context("What are our organization goals?")
if strat_ctx:
    if 'No Organization Goals' in strat_ctx:
        print("❌ FAIL — Still says 'no goals'")
    elif 'Increase Market Share' in strat_ctx:
        print("✅ PASS — Found goal 'Increase Market Share in Asia by 15%'")
        # Check for missions/strategies
        if 'Mission' in strat_ctx:
            print("  ✅ Missions visible")
        if 'Strategy' in strat_ctx:
            print("  ✅ Strategies visible")
    else:
        print("⚠️  PARTIAL — Context returned but goal not found")
        print(strat_ctx[:500])
else:
    print("❌ FAIL — Strategic context returned None")

print()
print("=" * 70)
print("FIX 5: Wiki/documentation context")
print("=" * 70)
wiki_ctx = service._get_wiki_context("Find documentation about API")
if wiki_ctx:
    if 'wiki pages' in wiki_ctx.lower() or 'documentation' in wiki_ctx.lower():
        page_count = wiki_ctx.count('📄')
        print(f"✅ PASS — Wiki context returned with {page_count} page(s)")
        for line in wiki_ctx.split('\n'):
            if '📄' in line:
                print(f"  {line.strip()}")
    else:
        print("⚠️  PARTIAL — Wiki context returned but unclear")
        print(wiki_ctx[:300])
else:
    print("❌ FAIL — Wiki context returned None")

# Also test documentation summary
doc_ctx = service._get_documentation_summary_context()
if doc_ctx:
    print(f"  ✅ Documentation summary also working ({len(doc_ctx)} chars)")
else:
    print("  ❌ Documentation summary returned None")

print()
print("=" * 70)
print("SUMMARY")
print("=" * 70)
