"""
Seed board 63 (Core AI Protocol Development) with the feature data that was empty
across all test boards, so Spectra's retrieval (not just "no data" honesty) can be
tested: Budget+TaskCost, Time entries, Stakeholders, Requirements, Retrospective,
Commitments, Shadow branch.

Idempotent: clears any rows it previously created on board 63, then recreates.
Run: python manage.py shell -v0 -c "exec(open('scripts/spectra_seed_board63.py',encoding='utf-8').read())"
Cleanup: set env SPECTRA_SEED_CLEAR=1 to only delete and not recreate.
"""
import os
from datetime import date, timedelta
from decimal import Decimal
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.apps import apps

from kanban.models import Board, Task

U = get_user_model()
b = Board.objects.get(id=63)
u1 = U.objects.get(email='paul.biotech10@gmail.com')   # testuser1 (owner)
u2 = U.objects.get(email='avip3310@gmail.com')          # testuser2 (member)

def M(name):
    return [m for m in apps.get_models() if m.__name__ == name][0]

from kanban.stakeholder_models import ProjectStakeholder
ProjectBudget = M('ProjectBudget')
TaskCost = M('TaskCost')
TimeEntry = M('TimeEntry')
Requirement = M('Requirement')
ProjectRetrospective = M('ProjectRetrospective')
CommitmentProtocol = M('CommitmentProtocol')
ShadowBranch = M('ShadowBranch')
BranchSnapshot = M('BranchSnapshot')

tasks = list(Task.objects.filter(column__board=b).order_by('id'))
t_research, t_draft, t_poc, t_review, t_urgent = tasks  # 5 known tasks

# ── Clear anything previously seeded on this board ─────────────────────
ProjectBudget.objects.filter(board=b).delete()
TaskCost.objects.filter(task__column__board=b).delete()
TimeEntry.objects.filter(task__column__board=b).delete()
ProjectStakeholder.objects.filter(board=b).delete()
Requirement.objects.filter(board=b).delete()
ProjectRetrospective.objects.filter(board=b).delete()
CommitmentProtocol.objects.filter(board=b).delete()
BranchSnapshot.objects.filter(branch__board=b).delete()
ShadowBranch.objects.filter(board=b).delete()
print("cleared prior seed rows on board 63")

if os.environ.get('SPECTRA_SEED_CLEAR'):
    print("SPECTRA_SEED_CLEAR set -> cleared only, not recreating")
else:
    today = timezone.now().date()

    # ── Budget ($50,000 allocated) + task costs (spend $37,000 -> 74%) ──
    ProjectBudget.objects.create(
        board=b, allocated_budget=Decimal('50000'), currency='USD',
        allocated_hours=Decimal('400'), created_by=u1,
        warning_threshold=70, critical_threshold=90,
    )
    TaskCost.objects.create(task=t_poc, estimated_cost=Decimal('20000'),
                            actual_cost=Decimal('22000'), estimated_hours=Decimal('160'),
                            hourly_rate=Decimal('120'))
    TaskCost.objects.create(task=t_draft, estimated_cost=Decimal('12000'),
                            actual_cost=Decimal('15000'), estimated_hours=Decimal('100'),
                            hourly_rate=Decimal('120'))
    print("budget + 2 task costs (spent 37000/50000 = 74%)")

    # ── Time entries (total 26h; testuser1 = top with 20h) ──
    TimeEntry.objects.create(task=t_poc, user=u1, hours_spent=Decimal('12.0'),
                             work_date=today - timedelta(days=5),
                             description='POC scaffolding + message schema', is_billable=True)
    TimeEntry.objects.create(task=t_draft, user=u1, hours_spent=Decimal('8.0'),
                             work_date=today - timedelta(days=3),
                             description='Protocol spec drafting', is_billable=True)
    TimeEntry.objects.create(task=t_urgent, user=u2, hours_spent=Decimal('6.0'),
                             work_date=today - timedelta(days=2),
                             description='Automated testing suite setup', is_billable=True)
    print("3 time entries (total 26h; testuser1 top at 20h)")

    # ── Stakeholders (power/interest matrix) ──
    ProjectStakeholder.objects.create(
        board=b, name='Dr. Sarah Chen', role='VP of Engineering', organization='Acme Corp',
        influence_level='high', interest_level='high',
        current_engagement='consult', desired_engagement='collaborate', is_active=True, created_by=u1)
    ProjectStakeholder.objects.create(
        board=b, name='Tom Reyes', role='Finance Controller', organization='Acme Corp',
        influence_level='high', interest_level='low',
        current_engagement='inform', desired_engagement='consult', is_active=True, created_by=u1)
    ProjectStakeholder.objects.create(
        board=b, name='Priya Nair', role='QA Lead', organization='Acme Corp',
        influence_level='low', interest_level='high',
        current_engagement='involve', desired_engagement='involve', is_active=True, created_by=u1)
    print("3 stakeholders")

    # ── Requirements (mixed statuses) ──
    reqs = [
        ('REQ-001', 'Message format must support versioning',
         'All inter-agent messages must carry a schema version field for backward compatibility.',
         'approved', 'high', 'functional'),
        ('REQ-002', 'Protocol must handle request-reply timeouts',
         'The protocol must define timeout and retry semantics for request-reply exchanges.',
         'in_review', 'critical', 'functional'),
        ('REQ-003', 'Security validation checkpoint before production',
         'A security validation gate must run before any protocol build is promoted to production.',
         'draft', 'high', 'non_functional'),
        ('REQ-004', 'Adapter for AutoGen/CrewAI message formats',
         'Provide a translation adapter so external frameworks can interoperate with the core protocol.',
         'approved', 'medium', 'technical'),
    ]
    for ident, title, desc, status, pri, typ in reqs:
        Requirement.objects.create(
            board=b, identifier=ident, title=title, description=desc,
            status=status, priority=pri, type=typ, created_by=u1)
    print("4 requirements (2 approved, 1 in_review, 1 draft)")

    # ── Retrospective (finalized sprint) ──
    ProjectRetrospective.objects.create(
        board=b, title='Sprint 1 Retrospective — Core AI Protocol',
        retrospective_type='sprint', status='finalized',
        period_start=today - timedelta(days=21), period_end=today - timedelta(days=7),
        what_went_well='Research phase identified viable communication patterns early '
                       '(publish-subscribe, request-reply, event-driven).',
        what_needs_improvement='Scope grew late from poorly defined ad-hoc tasks; deadlines slipped.',
        lessons_learned=[
            'Lock the protocol spec baseline before opening implementation tasks.',
            'Add a security validation checkpoint to the definition of done.',
            'External framework message formats (AutoGen, CrewAI) need a custom adapter.',
        ],
        team_morale_indicator='neutral', created_by=u1,
        finalized_by=u1, finalized_at=timezone.now())
    print("1 finalized retrospective with 3 lessons")

    # ── Commitments (confidence as 0-1 fractions) ──
    CommitmentProtocol.objects.create(
        board=b, title='Deliver protocol v1.0 to clinical pilot',
        description='Commit to a working v1.0 protocol for the clinical pilot milestone.',
        target_date=today + timedelta(days=30),
        initial_confidence=0.80, current_confidence=0.82,
        status='active', decay_model='exponential', created_by=u1)
    CommitmentProtocol.objects.create(
        board=b, title='Complete security validation gate',
        description='Commit to standing up the security validation checkpoint.',
        target_date=today + timedelta(days=14),
        initial_confidence=0.70, current_confidence=0.55,
        status='at_risk', decay_model='exponential', created_by=u1)
    print("2 commitments (0.82 active, 0.55 at_risk)")

    # ── Shadow branch + snapshot (feasibility score) ──
    branch = ShadowBranch.objects.create(
        board=b, name='Aggressive Timeline', created_by=u1, status='active',
        description='Compress the schedule by 2 weeks and add one engineer.',
        is_starred=True)
    BranchSnapshot.objects.create(
        branch=branch, scope_delta=0, team_delta=1, deadline_delta_weeks=-2,
        feasibility_score=Decimal('68.50'),
        projected_completion_date=today + timedelta(days=24))
    print("1 shadow branch 'Aggressive Timeline' (feasibility 68.5/100)")

    print("SEED COMPLETE on board 63")
