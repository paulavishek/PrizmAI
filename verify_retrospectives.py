"""
Quick script to verify retrospective demo data
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'kanban_board.settings')
django.setup()

from kanban.models import Board
from kanban.retrospective_models import (
    ProjectRetrospective, LessonLearned, ImprovementMetric, 
    RetrospectiveActionItem
)

print("\n" + "=" * 80)
print("RETROSPECTIVE DEMO DATA VERIFICATION")
print("=" * 80)

# Check each demo board
boards = Board.objects.filter(name__in=['Software Project', 'Marketing Campaign', 'Bug Tracking'])

for board in boards:
    print(f"\n📋 Board: {board.name}")
    print("-" * 80)
    
    retros = ProjectRetrospective.objects.filter(board=board).order_by('-period_end')
    print(f"   Retrospectives: {retros.count()}")
    
    for retro in retros:
        print(f"   • {retro.title}")
        print(f"     - Type: {retro.get_retrospective_type_display()}")
        print(f"     - Status: {retro.get_status_display()}")
        print(f"     - Period: {retro.period_start} to {retro.period_end}")
        print(f"     - Lessons: {retro.lessons.count()}")
        print(f"     - Metrics: {retro.metrics.count()}")
        print(f"     - Action Items: {retro.action_items.count()}")

print("\n" + "=" * 80)
print("✅ Verification Complete!")
print("=" * 80 + "\n")
