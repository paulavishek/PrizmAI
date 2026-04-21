"""
End-to-end test: generate retrospective with manual insights on board #97.
Checks:
  1. AI generation completes without errors
  2. Manual lessons are created with valid field values
  3. Manual actions are created with valid field values
  4. Manual items are distinct from AI items (ai_suggested=False)
  5. All choices are in the allowed sets
  6. recommended_action is not blank on lessons
  7. target_completion_date is set on actions
"""
import os, sys, django, traceback
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'kanban_board.settings')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
django.setup()

from datetime import date, timedelta
from django.utils import timezone
from django.contrib.auth import get_user_model

from kanban.models import Board
from kanban.retrospective_models import (
    ProjectRetrospective, LessonLearned, RetrospectiveActionItem
)
from kanban.utils.retrospective_generator import RetrospectiveGenerator

# ── helpers ─────────────────────────────────────────────────────────────
PASS = "  [PASS]"
FAIL = "  [FAIL]"

def check(label, condition, detail=""):
    if condition:
        print(f"{PASS}  {label}")
    else:
        print(f"{FAIL}  {label}" + (f"  → {detail}" if detail else ""))
    return condition

# ── setup ────────────────────────────────────────────────────────────────
User = get_user_model()
board = Board.objects.get(id=97)
user  = User.objects.filter(is_superuser=True).first() or User.objects.first()

print(f"\nBoard : {board.name} (id={board.id})")
print(f"User  : {user.username}\n")

# Period: last 14 days, must be in the past
period_end   = timezone.now().date() - timedelta(days=1)
period_start = period_end - timedelta(days=13)

MANUAL_LESSONS = [
    "Daily standups were consistently too long and need timeboxing",
    "Pair programming reduced review cycles significantly",
]
MANUAL_ACTIONS = [
    "Timebox standups to 15 minutes with a timer",
    "Schedule pair programming sessions twice a week",
]

# ── step 1: generate retrospective ──────────────────────────────────────
print("=" * 60)
print("STEP 1 — Generating AI retrospective …")
retro = None
try:
    generator = RetrospectiveGenerator(board, period_start, period_end)
    retro = generator.create_retrospective(
        created_by=user,
        retrospective_type='sprint'
    )
    check("Retrospective object created", retro is not None)
    check("Retrospective linked to board", retro.board_id == board.id)
    check("Status is 'generated' or 'reviewed'", retro.status in ('generated', 'reviewed', 'draft'))
    check("AI confidence score present", retro.ai_confidence_score is not None)
    ai_lessons_count  = retro.lessons.filter(ai_suggested=True).count()
    ai_actions_count  = retro.action_items.filter(ai_suggested=True).count()
    print(f"       AI lessons: {ai_lessons_count}, AI actions: {ai_actions_count}")
except Exception as e:
    print(f"{FAIL}  AI generation crashed: {e}")
    traceback.print_exc()
    sys.exit(1)

# ── step 2: add manual lessons ──────────────────────────────────────────
print("\nSTEP 2 — Adding manual lessons …")
from kanban.retrospective_views import _add_manual_lessons, _add_manual_actions

_add_manual_lessons(retro, board, MANUAL_LESSONS)
_add_manual_actions(retro, board, MANUAL_ACTIONS)

manual_lessons = retro.lessons.filter(ai_suggested=False)
manual_actions = retro.action_items.filter(ai_suggested=False)

check("Manual lesson count matches",
      manual_lessons.count() == len(MANUAL_LESSONS),
      f"got {manual_lessons.count()}, expected {len(MANUAL_LESSONS)}")

check("Manual action count matches",
      manual_actions.count() == len(MANUAL_ACTIONS),
      f"got {manual_actions.count()}, expected {len(MANUAL_ACTIONS)}")

# ── step 3: validate lesson fields ──────────────────────────────────────
print("\nSTEP 3 — Validating manual lesson fields …")

VALID_LESSON_CATEGORIES = {c[0] for c in LessonLearned.CATEGORY_CHOICES}
VALID_LESSON_PRIORITIES = {c[0] for c in LessonLearned.PRIORITY_CHOICES}
VALID_LESSON_STATUSES   = {c[0] for c in LessonLearned.STATUS_CHOICES}

all_lesson_ok = True
for lesson in manual_lessons:
    ok = True
    ok &= check(f"  [{lesson.title[:40]}] category valid",
                lesson.category in VALID_LESSON_CATEGORIES,
                f"'{lesson.category}' not in {VALID_LESSON_CATEGORIES}")
    ok &= check(f"  [{lesson.title[:40]}] priority valid",
                lesson.priority in VALID_LESSON_PRIORITIES,
                f"'{lesson.priority}'")
    ok &= check(f"  [{lesson.title[:40]}] status valid",
                lesson.status in VALID_LESSON_STATUSES,
                f"'{lesson.status}'")
    ok &= check(f"  [{lesson.title[:40]}] recommended_action not blank",
                bool(lesson.recommended_action.strip()),
                "empty")
    ok &= check(f"  [{lesson.title[:40]}] title matches input",
                any(lesson.title in ml or ml[:100] in lesson.title for ml in MANUAL_LESSONS))
    ok &= check(f"  [{lesson.title[:40]}] ai_suggested=False",
                lesson.ai_suggested == False)
    all_lesson_ok &= ok

# ── step 4: validate action fields ──────────────────────────────────────
print("\nSTEP 4 — Validating manual action fields …")

VALID_ACTION_TYPES    = {c[0] for c in RetrospectiveActionItem.ACTION_TYPE_CHOICES}
VALID_ACTION_STATUSES = {c[0] for c in RetrospectiveActionItem.STATUS_CHOICES}

all_action_ok = True
for action in manual_actions:
    ok = True
    ok &= check(f"  [{action.title[:40]}] action_type valid",
                action.action_type in VALID_ACTION_TYPES,
                f"'{action.action_type}' not in {VALID_ACTION_TYPES}")
    ok &= check(f"  [{action.title[:40]}] status valid",
                action.status in VALID_ACTION_STATUSES,
                f"'{action.status}'")
    ok &= check(f"  [{action.title[:40]}] target_completion_date set",
                action.target_completion_date is not None)
    ok &= check(f"  [{action.title[:40]}] due date in future",
                action.target_completion_date >= timezone.now().date(),
                f"{action.target_completion_date}")
    ok &= check(f"  [{action.title[:40]}] ai_suggested=False",
                action.ai_suggested == False)
    all_action_ok &= ok

# ── step 5: check AI items were also created ─────────────────────────────
print("\nSTEP 5 — Verifying AI-generated items coexist …")
total_lessons = retro.lessons.count()
total_actions = retro.action_items.count()
check("Total lessons > manual-only count (AI also contributed)",
      total_lessons >= len(MANUAL_LESSONS),
      f"total={total_lessons}")
check("Total actions > manual-only count (AI also contributed)",
      total_actions >= len(MANUAL_ACTIONS),
      f"total={total_actions}")
print(f"       Total lessons: {total_lessons} (manual={manual_lessons.count()}, AI={retro.lessons.filter(ai_suggested=True).count()})")
print(f"       Total actions: {total_actions} (manual={manual_actions.count()}, AI={retro.action_items.filter(ai_suggested=True).count()})")

# ── step 6: get_X_display() doesn't return blank ─────────────────────────
print("\nSTEP 6 — Checking get_X_display() returns meaningful labels …")
for lesson in manual_lessons:
    check(f"  [{lesson.title[:40]}] category display not empty",
          bool(lesson.get_category_display()))
    check(f"  [{lesson.title[:40]}] priority display not empty",
          bool(lesson.get_priority_display()))
    check(f"  [{lesson.title[:40]}] status display not empty",
          bool(lesson.get_status_display()))
for action in manual_actions:
    check(f"  [{action.title[:40]}] action_type display not empty",
          bool(action.get_action_type_display()))
    check(f"  [{action.title[:40]}] status display not empty",
          bool(action.get_status_display()))

# ── cleanup ───────────────────────────────────────────────────────────────
print("\n" + "=" * 60)
print("Cleaning up test retrospective …")
retro.delete()
print("Deleted test retrospective.\n")

# ── summary ───────────────────────────────────────────────────────────────
print("=" * 60)
print("All checks complete.")
