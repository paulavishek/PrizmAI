"""Verify retrospective demo data for board #94"""
import os, sys, django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'kanban_board.settings')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
django.setup()

from django.db.models import Count
from kanban.retrospective_models import (
    ProjectRetrospective, LessonLearned, ImprovementMetric,
    RetrospectiveActionItem, RetrospectiveTrend,
)
from kanban.models import Board

board = Board.objects.get(id=94)

# Dashboard view filters: status__in=['reviewed', 'finalized']
retros = ProjectRetrospective.objects.filter(
    board=board, status__in=['reviewed', 'finalized']
).order_by('-period_end')[:10]
print(f"Retrospectives (reviewed/finalized): {retros.count()}")
for r in retros:
    print(f"  - {r.title} | status={r.status} | sentiment={r.overall_sentiment_score}")

# Lessons by category
lessons_by_cat = (
    LessonLearned.objects.filter(board=board)
    .values('category')
    .annotate(count=Count('id'))
    .order_by('-count')[:5]
)
print(f"\nLessons by category:")
for lc in lessons_by_cat:
    print(f"  {lc['category']}: {lc['count']}")

# Urgent actions
urgent = RetrospectiveActionItem.objects.filter(
    board=board, priority__in=['high', 'critical'], status='pending'
)[:10]
print(f"\nUrgent actions: {urgent.count()}")
for a in urgent:
    print(f"  - {a.title} | priority={a.priority} | assigned={a.assigned_to}")

# All actions
all_actions = RetrospectiveActionItem.objects.filter(board=board)
print(f"\nAll action items: {all_actions.count()}")
for a in all_actions:
    print(f"  - {a.title} | status={a.status} | progress={a.progress_percentage}%")

# Metrics
metrics = ImprovementMetric.objects.filter(board=board)
print(f"\nMetrics: {metrics.count()}")
for m in metrics:
    print(f"  - {m.metric_name} ({m.metric_type}): {m.metric_value} {m.unit_of_measure} | trend={m.trend}")

# Trend
trend = RetrospectiveTrend.objects.filter(
    board=board, period_type='quarterly'
).order_by('-analysis_date').first()
if trend:
    print(f"\nTrend: analyzed={trend.retrospectives_analyzed}, velocity={trend.velocity_trend}, quality={trend.quality_trend}")
else:
    print("\nNo trend data found")
