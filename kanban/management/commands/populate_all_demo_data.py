"""
Consolidated Demo Data Population Command
=========================================
Single source of truth for PrizmAI demo data.

Produces ONE Software Development board under the "Demo - Acme Corporation"
organisation, owned by Priya Sharma, with:
  - 5 columns (Backlog / To Do / In Progress / In Review / Done)
  - 13 labels (3 Lean + 9 technical + 1 Epic marker)
  - 4 epic parent tasks   (item_type='epic', live in Backlog)
  - 28 child tasks        (8 Done + 2 In Review + 4 In Progress + 6 To Do + 8 Backlog)
  - 3 milestones          (item_type='milestone' on the Gantt)
  - 4 stakeholders, 1 project budget, 28 task-cost rows, ~80 time entries
  - 4 AI coach suggestions, 1 Phase-1 retrospective
  - 3 chat rooms with ~20 messages
  - 30 PriorityDecision records  (ML training data)
  - 25 historical completed tasks on a hidden archive board (ML training data)
  - 3 wiki pages under an "Engineering" category

Every date is calculated relative to TODAY at runtime - re-running the command
shifts the project forward so "today" always sits inside Phase 2 (~40% through).

Usage:
    python manage.py populate_all_demo_data            # idempotent top-up
    python manage.py populate_all_demo_data --reset    # wipe demo data + reseed
"""

from datetime import datetime, time, timedelta
from decimal import Decimal
import random

from django.contrib.auth.models import User
from django.core.management import call_command
from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from accounts.models import Organization
from accounts.demo_personas import (
    DEMO_PERSONAS, DEMO_USERNAMES, LEGACY_DEMO_USERNAMES, LEGACY_DEMO_EMAILS,
)
from kanban.models import (
    Board, Column, Task, TaskLabel, Comment, BoardMembership, ChecklistItem,
    Workspace,
)
from kanban.custom_field_models import (
    CustomFieldDefinition, CustomFieldOption, TaskCustomFieldValue,
)
from kanban.budget_models import ProjectBudget, TaskCost, TimeEntry
from kanban.coach_models import CoachingSuggestion
from kanban.priority_models import PriorityDecision
from kanban.retrospective_models import (
    ProjectRetrospective, LessonLearned, RetrospectiveActionItem,
    ImprovementMetric,
)
from kanban.stakeholder_models import ProjectStakeholder, StakeholderTaskInvolvement
from messaging.models import ChatRoom, ChatMessage
from wiki.models import WikiCategory, WikiPage


# ---------------------------------------------------------------------------
# Constants & helpers
# ---------------------------------------------------------------------------

DEMO_ORG_NAME = 'Demo - Acme Corporation'
DEMO_BOARD_NAME = 'Software Development'
ARCHIVE_BOARD_NAME = 'Historical Reference Data'

# Codebase storage values (NOT the display labels - see Task model choices)
LSS_VA = 'value_added'
LSS_NVA = 'necessary_nva'
LSS_WASTE = 'waste'

# risk_likelihood / risk_impact are IntegerFields 1=Low, 2=Med, 3=High
RISK = {'low': 1, 'medium': 2, 'high': 3}

# Demo persona identifiers come from accounts.demo_personas — the single
# source of truth for username/email/role. Re-exported under the old local
# names so internal references stay short.
PERSONA_USERNAMES = DEMO_USERNAMES
LEGACY_USERNAMES = LEGACY_DEMO_USERNAMES
LEGACY_EMAILS = LEGACY_DEMO_EMAILS
LEGACY_BOARD_NAMES = ('Marketing Campaign', 'Bug Tracking', 'Software Project')

# Phase labels stored on Task.phase (CharField). Must match the bare "Phase N"
# format expected by the Gantt view's phase grouping (kanban/views.py l.3517) and
# the CPM toggle's JS filter (gantt_chart.html l.2503).
PHASE_FOUNDATION = 'Phase 1'
PHASE_CORE = 'Phase 2'
PHASE_INTEGRATIONS = 'Phase 3'
PHASE_LAUNCH = 'Phase 4'


def _aware_due(d):
    """Promote a date to an aware datetime at 12:00 in the project tz."""
    return timezone.make_aware(datetime.combine(d, time(12, 0)))


class Command(BaseCommand):
    help = (
        'Populate the Software Development demo board with realistic, '
        'dynamically-dated data. Safe to run multiple times.'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--reset',
            action='store_true',
            help='Delete existing demo tasks/related data before reseeding',
        )

    # ------------------------------------------------------------------
    # Main entry point
    # ------------------------------------------------------------------
    def handle(self, *args, **options):
        self.TODAY = timezone.now().date()
        self.NOW = timezone.now()
        self.reset = options.get('reset', False)

        self.stdout.write(self.style.SUCCESS('=' * 80))
        self.stdout.write(self.style.SUCCESS('DEMO DATA POPULATION - Software Development board'))
        self.stdout.write(self.style.SUCCESS('=' * 80))
        self.stdout.write(f'Today: {self.TODAY}  (project mid-point)')
        self.stdout.write('')

        # Ensure org + personas + board scaffolding exist (self-healing).
        self._ensure_scaffolding()

        with transaction.atomic():
            if self.reset:
                self._reset_demo_data()

            # Always: delete legacy boards from the demo org (Marketing/Bug Tracking)
            self._delete_legacy_demo_boards()

            # Always: purge legacy demo persona accounts. Old User+BoardMembership
            # rows would otherwise still appear in AI Resource Optimization and
            # other per-board reports. Self-heals on every seeder invocation.
            self._delete_legacy_demo_accounts()

            # Idempotency: if the board already has seed tasks AND we're not
            # resetting, this is a no-op (the heavy seed work has nothing safe
            # to add - singletons like ProjectBudget would clash).
            existing_tasks = Task.objects.filter(
                column__board=self.board, is_seed_demo_data=True,
            ).count()
            if existing_tasks > 0 and not self.reset:
                self.stdout.write(self.style.WARNING(
                    f'  Board already has {existing_tasks} seed tasks. '
                    'Skipping seed (pass --reset to rebuild).'
                ))
                # Always refresh labels - cheap and matches new colour scheme
                self._create_labels(self.board)
            else:
                # Core seed sequence
                labels = self._create_labels(self.board)
                epics = self._create_epics(labels)
                tasks_by_code = self._create_child_tasks(epics, labels)
                self._link_dependencies(tasks_by_code)
                self._create_milestones(tasks_by_code)
                self._create_budget_and_time(tasks_by_code, epics)
                self._create_stakeholders(tasks_by_code)
                self._create_scope_baseline()
                self._create_scope_autopsy()
                self._create_retrospective()
                self._create_chat_rooms()
                self._create_coaching_suggestions(tasks_by_code)
                self._create_historical_tasks_for_ml()
                self._create_priority_decisions(tasks_by_code)
                self._create_wiki_pages()
                self._create_velocity_snapshots()

            # Always run — idempotent via get_or_create
            self._create_custom_fields()

        # Optional sub-seeders (best-effort, outside the transaction)
        self._call_optional_subseeders()

        self._print_verification_report()

    # ------------------------------------------------------------------
    # Scaffolding (org / users / board)
    # ------------------------------------------------------------------
    def _ensure_scaffolding(self):
        """Ensure demo org, personas, and the Software Development board exist."""
        try:
            self.demo_org = Organization.objects.get(name=DEMO_ORG_NAME, is_demo=True)
        except Organization.DoesNotExist:
            self.stdout.write('Demo organisation missing - running create_demo_organization...')
            call_command('create_demo_organization')
            self.demo_org = Organization.objects.get(name=DEMO_ORG_NAME, is_demo=True)

        # Ensure all three personas exist (self-heal if missing)
        if User.objects.filter(username__in=PERSONA_USERNAMES).count() < 3:
            self.stdout.write('One or more personas missing - running create_demo_organization...')
            call_command('create_demo_organization')

        self.priya = User.objects.get(username=DEMO_PERSONAS['lead']['username'])
        self.marcus = User.objects.get(username=DEMO_PERSONAS['frontend']['username'])
        self.elena = User.objects.get(username=DEMO_PERSONAS['devops']['username'])
        # testuser1 is the real observer/tester account in the demo workspace.
        # Optional: not present in every environment (e.g. CI). Falls back to
        # marcus so the archive-board spread still uses 4 slots.
        self.testuser1 = User.objects.filter(username='testuser1').first()
        self.fourth_member = self.testuser1 or self.marcus

        # Board: created by create_demo_organization
        try:
            self.board = Board.objects.get(
                name=DEMO_BOARD_NAME,
                organization=self.demo_org,
                is_official_demo_board=True,
            )
        except Board.DoesNotExist:
            call_command('create_demo_organization')
            self.board = Board.objects.get(
                name=DEMO_BOARD_NAME,
                organization=self.demo_org,
                is_official_demo_board=True,
            )

        # Refresh deadline + phases on each run so dates stay current.
        self.board.project_deadline = self.TODAY + timedelta(days=56)
        self.board.num_phases = 4
        self.board.save(update_fields=['project_deadline', 'num_phases'])

        # Column lookup (will all exist after create_demo_organization)
        self.columns = {c.name: c for c in self.board.columns.all()}
        for needed in ('Backlog', 'To Do', 'In Progress', 'In Review', 'Done'):
            if needed not in self.columns:
                raise RuntimeError(
                    f'Demo board missing column "{needed}". '
                    'Run create_demo_organization first.'
                )

    # ------------------------------------------------------------------
    # Cleanup
    # ------------------------------------------------------------------
    def _reset_demo_data(self):
        """Wipe demo-board content (tasks + dependents) so we can reseed clean."""
        self.stdout.write(self.style.WARNING('Resetting demo data...'))

        # All boards in the demo org that are seed/official: the main board plus
        # any historical/archive board. We never touch user-owned boards.
        boards = list(Board.objects.filter(
            organization=self.demo_org,
            is_seed_demo_data=True,
        ))

        for b in boards:
            task_ids = list(Task.objects.filter(column__board=b).values_list('id', flat=True))
            if task_ids:
                # Clear M2M before deleting tasks
                for t in Task.objects.filter(id__in=task_ids):
                    t.dependencies.clear()
                    t.related_tasks.clear()
                Comment.objects.filter(task_id__in=task_ids).delete()
                TaskCost.objects.filter(task_id__in=task_ids).delete()
                TimeEntry.objects.filter(task_id__in=task_ids).delete()
                ChecklistItem.objects.filter(task_id__in=task_ids).delete()
                try:
                    StakeholderTaskInvolvement.objects.filter(task_id__in=task_ids).delete()
                except Exception:
                    pass
                try:
                    PriorityDecision.objects.filter(task_id__in=task_ids).delete()
                except Exception:
                    pass
                Task.objects.filter(id__in=task_ids).delete()

            # Board-scoped children
            ProjectBudget.objects.filter(board=b).delete()
            ProjectStakeholder.objects.filter(board=b).delete()
            ProjectRetrospective.objects.filter(board=b).delete()
            CoachingSuggestion.objects.filter(board=b).delete()
            ChatMessage.objects.filter(chat_room__board=b).delete()
            ChatRoom.objects.filter(board=b).delete()

            # Scope tracking: snapshots, alerts, autopsy reports, and per-task
            # reasons. Without this, every --reset run accumulates another
            # baseline row, producing the duplicate "May 09, 2026" entries in
            # the Scope History list. Also reset the cached baseline_* fields
            # on the board so the next seed call can set them cleanly.
            from kanban.models import ScopeChangeSnapshot, ScopeCreepAlert
            from kanban.scope_autopsy_models import (
                ScopeAutopsyReport, TaskScopeReason,
            )
            ScopeCreepAlert.objects.filter(board=b).delete()
            ScopeChangeSnapshot.objects.filter(board=b).delete()
            # Cascades to ScopeTimelineEvent via the FK on_delete=CASCADE
            ScopeAutopsyReport.objects.filter(board=b).delete()
            TaskScopeReason.objects.filter(board=b).delete()
            Board.objects.filter(pk=b.pk).update(
                baseline_task_count=None,
                baseline_complexity_total=None,
                baseline_set_date=None,
                baseline_set_by=None,
            )

        # Custom field definitions for the demo workspace (cascade deletes values)
        demo_workspaces = Workspace.objects.filter(
            organization=self.demo_org, is_demo=True
        )
        CustomFieldDefinition.objects.filter(workspace__in=demo_workspaces).delete()

        self.stdout.write('  [OK] Reset complete')

    def _delete_legacy_demo_boards(self):
        """Delete Marketing Campaign / Bug Tracking / Software Project boards
        that belong to the demo org. Safe - never touches real user boards
        because of the organization filter."""
        legacy = Board.objects.filter(
            organization=self.demo_org,
            name__in=LEGACY_BOARD_NAMES,
        )
        deleted = []
        for b in legacy:
            deleted.append(b.name)
            # Cascade everything
            task_ids = list(Task.objects.filter(column__board=b).values_list('id', flat=True))
            for t in Task.objects.filter(id__in=task_ids):
                t.dependencies.clear()
                t.related_tasks.clear()
            Comment.objects.filter(task_id__in=task_ids).delete()
            TaskCost.objects.filter(task_id__in=task_ids).delete()
            TimeEntry.objects.filter(task_id__in=task_ids).delete()
            ChecklistItem.objects.filter(task_id__in=task_ids).delete()
            Task.objects.filter(id__in=task_ids).delete()
            b.columns.all().delete()
            b.delete()
        if deleted:
            self.stdout.write(self.style.WARNING(
                f'  [OK] Deleted legacy demo boards: {", ".join(deleted)}'
            ))

    def _delete_legacy_demo_accounts(self):
        """Neutralise old persona accounts (alex_chen_demo / sam_rivera_demo /
        jordan_taylor_demo) so they stop appearing in AI Resource Optimization
        and other per-board reports.

        We deliberately do NOT ``delete()`` the User rows: ``Organization.created_by``
        and several other FKs cascade-on-delete to the User, so removing a
        legacy User would wipe the entire demo Organization, Workspace, Board,
        Tasks, and historical training data.

        Instead we:
          1. Drop their BoardMembership rows on demo-org boards — this removes
             them from the team-workload report query
             (``User.objects.filter(board_memberships__board=board)``).
          2. Drop their WorkspaceMembership rows on demo workspaces.
          3. Set ``is_active=False`` so they can't log in.
          4. Tag profile.is_demo_account=False so demo-only queries skip them.
        """
        from kanban.models import BoardMembership, WorkspaceMembership, Board, Workspace
        from accounts.models import UserProfile

        legacy_qs = User.objects.filter(
            Q(username__in=LEGACY_USERNAMES) | Q(email__in=LEGACY_EMAILS)
        )
        legacy_ids = list(legacy_qs.values_list('id', flat=True))
        if not legacy_ids:
            return

        # 1. Strip board memberships on demo-org boards
        demo_board_ids = list(Board.objects.filter(
            organization=self.demo_org
        ).values_list('id', flat=True))
        bm_deleted, _ = BoardMembership.objects.filter(
            user_id__in=legacy_ids, board_id__in=demo_board_ids
        ).delete()

        # 2. Strip workspace memberships on demo workspaces
        demo_ws_ids = list(Workspace.objects.filter(
            organization=self.demo_org
        ).values_list('id', flat=True))
        wm_deleted, _ = WorkspaceMembership.objects.filter(
            user_id__in=legacy_ids, workspace_id__in=demo_ws_ids
        ).delete()

        # 3. Deactivate accounts (prevents login + removes from active dropdowns)
        legacy_qs.update(is_active=False)

        # 4. Untag as demo accounts so demo-only filters exclude them
        UserProfile.objects.filter(user_id__in=legacy_ids).update(is_demo_account=False)

        names = list(legacy_qs.values_list('username', flat=True))
        self.stdout.write(self.style.WARNING(
            f'  [OK] Neutralised legacy demo accounts ({", ".join(names)}): '
            f'{bm_deleted} board memberships, {wm_deleted} workspace memberships removed; '
            f'accounts deactivated'
        ))

    # ------------------------------------------------------------------
    # Labels
    # ------------------------------------------------------------------
    def _create_labels(self, board):
        """Create the board's regular labels (idempotent) and return a name -> obj map.

        Lean Six Sigma labels are intentionally NOT seeded: LSS is an
        operations/manufacturing methodology unfamiliar to most software teams.
        Users who want them can opt in via the "Add Lean Six Sigma labels"
        button on the label manager. Task seeding uses an `if ln in labels`
        guard, so any leftover 'Value-Added' references simply go untagged.
        """
        defs = [
            # Technical
            ('Backend', '#6366f1', 'regular'),
            ('Frontend', '#06b6d4', 'regular'),
            ('DevOps', '#8b5cf6', 'regular'),
            ('Security', '#dc2626', 'regular'),
            ('Database', '#d97706', 'regular'),
            ('API', '#0891b2', 'regular'),
            ('Testing', '#16a34a', 'regular'),
            ('Documentation', '#6b7280', 'regular'),
            ('Performance', '#c2410c', 'regular'),
            ('Epic', '#7c3aed', 'regular'),
        ]
        labels = {}
        for name, color, category in defs:
            obj, _ = TaskLabel.objects.get_or_create(
                board=board,
                name=name,
                defaults={'color': color, 'category': category},
            )
            # Keep color/category in sync on re-runs
            obj.color = color
            obj.category = category
            obj.save(update_fields=['color', 'category'])
            labels[name] = obj
        return labels

    # ------------------------------------------------------------------
    # Helpers for task creation
    # ------------------------------------------------------------------
    def _days_ago(self, n):
        return self.NOW - timedelta(days=n)

    def _make_task(self, *, code, title, description, column, phase, parent,
                   priority, start_offset, due_offset, progress,
                   complexity, risk_l, risk_i, risk_level, lss,
                   workload, collab, est_cost, est_hours, hourly, actual_cost,
                   assignee, creator, completed_offset=None, item_type='task',
                   label_names=(), checklist=(), comments=(), labels=None):
        """Create a Task + its TaskCost + checklist + comments in one shot.

        `code` is a short opaque id (D1, P1, T2, ...) used for dependency wiring;
        it is not stored on the model.
        """
        due_date = _aware_due(self.TODAY + timedelta(days=due_offset))
        start_date = self.TODAY + timedelta(days=start_offset)
        completed_at = self._days_ago(completed_offset) if completed_offset is not None else None

        task = Task.objects.create(
            title=title,
            description=description,
            column=column,
            phase=phase,
            parent_task=parent,
            item_type=item_type,
            priority=priority,
            start_date=start_date,
            due_date=due_date,
            progress=progress,
            complexity_score=complexity,
            risk_likelihood=RISK[risk_l],
            risk_impact=RISK[risk_i],
            risk_score=RISK[risk_l] * RISK[risk_i],
            risk_level=risk_level,
            lss_classification=lss,
            workload_impact=workload,
            collaboration_required=collab,
            assigned_to=assignee,
            created_by=creator,
            completed_at=completed_at,
            is_seed_demo_data=True,
        )

        if completed_at is not None and start_date is not None:
            task.actual_duration_days = (completed_at.date() - start_date).days
            task.save(update_fields=['actual_duration_days'])

        TaskCost.objects.create(
            task=task,
            estimated_cost=Decimal(str(est_cost)),
            estimated_hours=Decimal(str(est_hours)),
            hourly_rate=Decimal(str(hourly)),
            actual_cost=Decimal(str(actual_cost)),
        )

        if labels is not None:
            for ln in label_names:
                if ln in labels:
                    task.labels.add(labels[ln])

        for pos, (text, done) in enumerate(checklist):
            ChecklistItem.objects.create(
                task=task, title=text, is_completed=done, position=pos,
                completed_at=self.NOW - timedelta(days=1) if done else None,
                completed_by=assignee if done else None,
            )

        for author, text, days_ago in comments:
            c = Comment.objects.create(task=task, user=author, content=text)
            # Backdate created_at (auto_now_add bypass)
            Comment.objects.filter(pk=c.pk).update(
                created_at=self.NOW - timedelta(days=days_ago)
            )

        return task

    # ------------------------------------------------------------------
    # Epics
    # ------------------------------------------------------------------
    def _create_epics(self, labels):
        """Create 4 epic parent tasks in the Backlog column."""
        backlog = self.columns['Backlog']
        common = dict(
            column=backlog, item_type='epic', progress=0, parent=None,
            risk_l='medium', risk_i='medium', risk_level='medium',
            lss=LSS_VA, workload='high', collab=True,
            est_cost=0, est_hours=0, hourly=0, actual_cost=0,
            creator=self.priya, label_names=['Epic'], labels=labels,
        )
        epic_foundation = self._make_task(
            code='E1', title='EPIC: Foundation & Infrastructure',
            description=('All tasks related to setting up the development environment, '
                         'system architecture, and foundational infrastructure that all '
                         'other work depends on.'),
            phase=PHASE_FOUNDATION, priority='high',
            start_offset=-56, due_offset=-21, complexity=9,
            assignee=self.marcus, **common,
        )
        epic_auth = self._make_task(
            code='E2', title='EPIC: Authentication & Security',
            description=('All tasks related to user authentication, authorization, OAuth '
                         'integrations, and security hardening across the platform.'),
            phase=PHASE_CORE, priority='urgent',
            start_offset=-35, due_offset=7, complexity=9,
            assignee=self.priya, **common,
        )
        epic_api = self._make_task(
            code='E3', title='EPIC: Core API & Database Layer',
            description=('REST API endpoints, database schema design, migrations, and '
                         'the data access layer powering all product features.'),
            phase=PHASE_CORE, priority='high',
            start_offset=-28, due_offset=14, complexity=8,
            assignee=self.priya, **common,
        )
        epic_integrations = self._make_task(
            code='E4', title='EPIC: Integrations & Notifications',
            description=('Third-party service integrations including OAuth providers, '
                         'push notification systems, and external API connectors.'),
            phase=PHASE_INTEGRATIONS, priority='medium',
            start_offset=14, due_offset=49, complexity=7,
            assignee=self.elena, **common,
        )
        return {
            'foundation': epic_foundation,
            'auth': epic_auth,
            'api': epic_api,
            'integrations': epic_integrations,
        }

    # ------------------------------------------------------------------
    # 28 child tasks
    # ------------------------------------------------------------------
    def _create_child_tasks(self, epics, labels):
        """Create the 28 child tasks across all columns. Returns code -> task."""
        col = self.columns
        out = {}

        # ===================== DONE (8) =====================
        out['D1'] = self._make_task(
            code='D1', title='Requirements Analysis & Planning',
            description=('Define functional and non-functional requirements for the platform. '
                         'Conduct stakeholder interviews, document user stories, establish acceptance '
                         'criteria, and create the product requirements document (PRD) that will guide '
                         'the entire development programme.'),
            column=col['Done'], phase=PHASE_FOUNDATION, parent=epics['foundation'],
            priority='high', start_offset=-56, due_offset=-49, progress=100,
            complexity=5, risk_l='low', risk_i='medium', risk_level='low',
            lss=LSS_NVA, workload='medium', collab=True,
            est_cost=3200, est_hours=40, hourly=80, actual_cost=3050,
            assignee=self.priya, creator=self.priya, completed_offset=49,
            label_names=['Documentation', 'Value-Added'], labels=labels,
            checklist=[
                ('Conduct stakeholder interviews with all department heads', True),
                ('Draft and review product requirements document (PRD)', True),
                ('Define acceptance criteria for all major user stories', True),
            ],
            comments=[
                (self.priya, 'Stakeholder interviews completed. Three rounds of review needed before sign-off - more iterations than planned but the final PRD is solid.', 51),
                (self.marcus, 'PRD approved by all stakeholders. Ready to move to architecture.', 49),
            ],
        )
        out['D2'] = self._make_task(
            code='D2', title='Development Environment Setup',
            description=('Configure local development environments, set up Docker containers, '
                         'establish the CI/CD pipeline with GitHub Actions, configure code quality '
                         'tools (linting, formatting, pre-commit hooks), and document the onboarding '
                         'process for new developers.'),
            column=col['Done'], phase=PHASE_FOUNDATION, parent=epics['foundation'],
            priority='high', start_offset=-52, due_offset=-44, progress=100,
            complexity=6, risk_l='low', risk_i='high', risk_level='medium',
            lss=LSS_NVA, workload='high', collab=True,
            est_cost=2800, est_hours=32, hourly=87.5, actual_cost=2650,
            assignee=self.elena, creator=self.priya, completed_offset=44,
            label_names=['DevOps', 'Value-Added'], labels=labels,
            checklist=[
                ('Set up Docker Compose for local development', True),
                ('Configure GitHub Actions CI pipeline with test + lint', True),
                ('Write developer onboarding documentation', True),
            ],
            comments=[
                (self.elena, 'Docker setup is done. The CI pipeline runs in under 4 minutes with dependency caching. All green.', 46),
                (self.marcus, 'Onboarding doc is excellent - I got up and running in 30 minutes as a test.', 44),
            ],
        )
        out['D3'] = self._make_task(
            code='D3', title='System Architecture Design',
            description=('Design the overall system architecture including the Django backend, '
                         'REST API layer, WebSocket server, Celery task queue, Redis caching '
                         'strategy, PostgreSQL schema approach, and deployment topology on Google '
                         'Cloud Run. Produce architecture decision records (ADRs) for all major '
                         'technology choices.'),
            column=col['Done'], phase=PHASE_FOUNDATION, parent=epics['foundation'],
            priority='urgent', start_offset=-48, due_offset=-40, progress=100,
            complexity=9, risk_l='medium', risk_i='high', risk_level='high',
            lss=LSS_VA, workload='high', collab=True,
            est_cost=5600, est_hours=64, hourly=87.5, actual_cost=5950,
            assignee=self.marcus, creator=self.priya, completed_offset=40,
            label_names=['Backend', 'Documentation', 'Value-Added'], labels=labels,
            checklist=[
                ('Design Django app structure and module boundaries', True),
                ('Document API versioning strategy and REST conventions', True),
                ('Write ADRs for PostgreSQL, Redis, and Celery decisions', True),
                ('Review architecture with full team and incorporate feedback', True),
            ],
            comments=[
                (self.marcus, 'Architecture review completed. Decision to use Django Channels for WebSockets was debated - Celery + Redis pub/sub was considered but Channels won on simplicity grounds.', 43),
                (self.priya, 'ADRs approved. Slight over-budget due to extra review cycles but the rigour was worth it.', 40),
            ],
        )
        out['D4'] = self._make_task(
            code='D4', title='Database Schema Design',
            description=('Design the complete PostgreSQL database schema including all entities, '
                         'relationships, indexes, and constraints. Create ER diagrams, write the '
                         'initial Django migrations, establish naming conventions, and document the '
                         'data model with field-level descriptions.'),
            column=col['Done'], phase=PHASE_FOUNDATION, parent=epics['api'],
            priority='high', start_offset=-39, due_offset=-33, progress=100,
            complexity=7, risk_l='low', risk_i='high', risk_level='medium',
            lss=LSS_VA, workload='medium', collab=False,
            est_cost=3500, est_hours=40, hourly=87.5, actual_cost=3325,
            assignee=self.fourth_member, creator=self.marcus, completed_offset=33,
            label_names=['Database', 'Backend', 'Value-Added'], labels=labels,
            checklist=[
                ('Create ER diagram for all core entities', True),
                ('Write and test initial Django migration set', True),
                ('Add indexes for all foreign keys and frequent query fields', True),
            ],
            comments=[
                (self.fourth_member, 'Added GIN indexes for full-text search fields. The initial migration set covers 23 tables. Composite indexes on (board_id, created_at) are showing sub-10ms query times in local testing.', 35),
                (self.marcus, 'Schema looks solid. Good call on the composite indexes.', 33),
            ],
        )
        out['D5'] = self._make_task(
            code='D5', title='Security Architecture Patterns',
            description=('Define and implement the security architecture for the platform: '
                         'authentication middleware, JWT token lifecycle management, CSRF protection, '
                         'Content Security Policy headers, SQL injection prevention via ORM-only '
                         'queries, XSS sanitization with bleach, and brute-force protection with '
                         'django-axes.'),
            column=col['Done'], phase=PHASE_FOUNDATION, parent=epics['auth'],
            priority='urgent', start_offset=-38, due_offset=-28, progress=100,
            complexity=8, risk_l='low', risk_i='high', risk_level='medium',
            lss=LSS_VA, workload='high', collab=True,
            est_cost=4200, est_hours=48, hourly=87.5, actual_cost=4050,
            assignee=self.priya, creator=self.priya, completed_offset=28,
            label_names=['Security', 'Backend', 'Value-Added'], labels=labels,
            checklist=[
                ('Implement JWT authentication middleware', True),
                ('Configure django-axes brute-force protection', True),
                ('Set up CSP headers and XSS sanitization', True),
            ],
            comments=[
                (self.priya, 'All security layers implemented and tested. Penetration test checklist passed. Brute-force lockout triggers after 5 failed attempts with exponential backoff.', 30),
                (self.elena, 'Ran OWASP ZAP scan - no critical findings. Two medium findings resolved.', 28),
            ],
        )
        out['D6'] = self._make_task(
            code='D6', title='Base API Structure',
            description=('Establish the Django REST Framework foundation: router configuration, '
                         'base serializer classes, pagination classes, global exception handler, '
                         'API versioning under /api/v1/, token authentication setup, and standardized '
                         'response envelope format. This is the foundation all feature APIs will build on.'),
            column=col['Done'], phase=PHASE_CORE, parent=epics['api'],
            priority='high', start_offset=-30, due_offset=-22, progress=100,
            complexity=6, risk_l='low', risk_i='medium', risk_level='low',
            lss=LSS_VA, workload='medium', collab=False,
            est_cost=2800, est_hours=32, hourly=87.5, actual_cost=2650,
            assignee=self.fourth_member, creator=self.marcus, completed_offset=22,
            label_names=['Backend', 'API', 'Value-Added'], labels=labels,
            checklist=[
                ('Configure DRF router and URL patterns under /api/v1/', True),
                ('Write base serializer and exception handler classes', True),
                ('Add token authentication and standardized response format', True),
            ],
            comments=[
                (self.fourth_member, 'API foundation is complete. Standardized error responses, pagination, and filtering are all in. Ready for feature teams to build on top.', 23),
            ],
        )
        out['D7'] = self._make_task(
            code='D7', title='Authentication Testing Suite',
            description=('Write comprehensive automated tests for all authentication flows: '
                         'registration, login, logout, password reset, JWT token refresh, session '
                         'expiry, brute-force lockout, and RBAC permission checks. Achieve minimum '
                         '90% code coverage on auth module.'),
            column=col['Done'], phase=PHASE_CORE, parent=epics['auth'],
            priority='high', start_offset=-25, due_offset=-16, progress=100,
            complexity=5, risk_l='low', risk_i='medium', risk_level='low',
            lss=LSS_VA, workload='medium', collab=False,
            est_cost=2400, est_hours=28, hourly=85, actual_cost=2380,
            assignee=self.elena, creator=self.priya, completed_offset=16,
            label_names=['Testing', 'Security', 'Value-Added'], labels=labels,
            checklist=[
                ('Write unit tests for JWT token generation and validation', True),
                ('Write integration tests for login/logout/reset flows', True),
                ('Verify 90%+ code coverage on auth module', True),
            ],
            comments=[
                (self.elena, 'Coverage is at 94% on the auth module. 47 tests total, all passing. Brute-force lockout and token expiry edge cases were the trickiest to test correctly.', 17),
            ],
        )
        out['D8'] = self._make_task(
            code='D8', title='Role-Based Access Control (RBAC)',
            description=('Implement the four-tier RBAC system: Org Admin, Owner, Member, and '
                         'Viewer roles. Build permission predicates using django-rules, enforce '
                         'board-level access checks on all views, implement automatic downward '
                         'permission inheritance through the Goal -> Mission -> Strategy -> Board '
                         'hierarchy, and add upward read-only visibility for board members.'),
            column=col['Done'], phase=PHASE_CORE, parent=epics['auth'],
            priority='urgent', start_offset=-22, due_offset=-12, progress=100,
            complexity=8, risk_l='low', risk_i='high', risk_level='medium',
            lss=LSS_VA, workload='high', collab=True,
            est_cost=4800, est_hours=56, hourly=85, actual_cost=4650,
            assignee=self.fourth_member, creator=self.priya, completed_offset=12,
            label_names=['Security', 'Backend', 'Value-Added'], labels=labels,
            checklist=[
                ('Implement django-rules permission predicates for all roles', True),
                ('Enforce board-level access on all views and API endpoints', True),
                ('Test permission inheritance through the hierarchy', True),
            ],
            comments=[
                (self.fourth_member, 'RBAC implementation complete. All 4 roles tested across the hierarchy. django-rules predicates are clean and easy to extend. Every view now has @permission_required decorators.', 13),
                (self.marcus, 'Security review passed. No privilege escalation paths found in testing.', 12),
            ],
        )

        # ===================== IN REVIEW (2) =====================
        # R1 - OVERDUE SCENARIO: code review running 4 days past deadline.
        # The daily refresh pins this task to always appear 4 days past-due
        # (see _OVERDUE_PINS in demo_date_refresh.py).
        out['R1'] = self._make_task(
            code='R1', title='Authentication System',
            description=('Implement the complete user authentication system: email/password '
                         'registration with verification, secure login with remember-me functionality, '
                         'password reset via email tokens, session management, and integration with '
                         'the JWT middleware established in the security architecture phase. '
                         'Currently waiting for security sign-off from the Security Officer (James Okonkwo) '
                         'before this PR can be merged to main — the review was requested 4 days ago '
                         'and remains outstanding.'),
            column=col['In Review'], phase=PHASE_CORE, parent=epics['auth'],
            priority='urgent', start_offset=-36, due_offset=-20, progress=90,
            complexity=8, risk_l='low', risk_i='high', risk_level='medium',
            lss=LSS_VA, workload='high', collab=False,
            est_cost=5200, est_hours=60, hourly=87.5, actual_cost=4980,
            assignee=self.priya, creator=self.priya,
            label_names=['Backend', 'Security', 'Value-Added'], labels=labels,
            checklist=[
                ('Implement email/password registration with verification', True),
                ('Build secure login and password reset flows', True),
                ('Integrate JWT middleware and session management', True),
            ],
            comments=[
                (self.priya, 'Implementation complete. Submitted for code review. All auth flows working, including edge cases like expired reset tokens and concurrent session handling.', 4),
                (self.marcus, 'Reviewing now. The token rotation logic is clean. One question on the session expiry behaviour - left a comment in the PR.', 2),
            ],
        )
        out['R2'] = self._make_task(
            code='R2', title='File Upload System',
            description=('Build secure file upload functionality for task attachments: MIME type '
                         'validation, malicious content detection, file size limits, storage on '
                         'Google Cloud Storage with signed URLs, and AI-powered content extraction '
                         'for document attachments (PDF, DOCX, TXT).'),
            column=col['In Review'], phase=PHASE_CORE, parent=epics['api'],
            priority='medium', start_offset=-14, due_offset=2, progress=88,
            complexity=6, risk_l='medium', risk_i='medium', risk_level='medium',
            lss=LSS_VA, workload='medium', collab=False,
            est_cost=3200, est_hours=36, hourly=87.5, actual_cost=2950,
            assignee=self.marcus, creator=self.priya,
            label_names=['Backend', 'API', 'Value-Added'], labels=labels,
            checklist=[
                ('Implement MIME type validation and malicious content scan', True),
                ('Configure GCS bucket with signed URL generation', True),
                ('Build AI content extraction for PDF/DOCX attachments', False),
            ],
            comments=[
                (self.marcus, 'MIME validation and GCS integration done. AI extraction working for PDFs - DOCX support needs one more day. Overall 88% complete.', 3),
            ],
        )

        # ===================== IN PROGRESS (4) =====================
        out['P1'] = self._make_task(
            code='P1', title='User Registration Flow',
            description=("Build the complete user registration experience: signup form with "
                         "real-time validation, email verification with single-use tokens, "
                         "onboarding wizard that guides new users to create their first board, "
                         "and AI-assisted workspace setup that generates a starter project "
                         "structure based on the user's stated goals."),
            column=col['In Progress'], phase=PHASE_CORE, parent=epics['auth'],
            priority='urgent', start_offset=-10, due_offset=4, progress=75,
            complexity=7, risk_l='medium', risk_i='medium', risk_level='medium',
            lss=LSS_VA, workload='medium', collab=True,
            est_cost=4200, est_hours=48, hourly=87.5, actual_cost=3150,
            assignee=self.marcus, creator=self.priya,
            label_names=['Frontend', 'Backend', 'Value-Added'], labels=labels,
            checklist=[
                ('Build signup form with real-time field validation', True),
                ('Implement email verification with single-use token links', True),
                ('Build onboarding wizard and AI workspace setup', False),
            ],
            comments=[
                (self.marcus, 'Signup form and email verification are working. The onboarding wizard is 60% done - the AI workspace generation is the last piece. On track for the deadline.', 2),
                (self.priya, 'Tested the verification flow - smooth experience. The real-time validation is a nice touch.', 1),
            ],
        )
        # P2 - OVERDUE SCENARIO: rollback complexity caused 3-day slip.
        # The daily refresh pins this task to always appear 3 days past-due
        # (see _OVERDUE_PINS in demo_date_refresh.py).
        out['P2'] = self._make_task(
            code='P2', title='Database Schema & Migrations',
            description=('Implement the full production database schema: write all Django '
                         'migrations for the 23-table schema, create database seed scripts for '
                         'lookup tables, implement migration testing in the CI pipeline, write '
                         'rollback procedures for each migration, and document the upgrade path '
                         'for production deployment. This task requires the Authentication System '
                         '(R1) API contract to be finalised before the oauth_tokens migration can '
                         'be validated against the live auth layer in CI. Currently slipping due '
                         'to a circular reference between Board and Organization that complicates '
                         'the rollback procedures.'),
            column=col['In Progress'], phase=PHASE_CORE, parent=epics['api'],
            priority='high', start_offset=-31, due_offset=-19, progress=55,
            complexity=7, risk_l='medium', risk_i='high', risk_level='high',
            lss=LSS_VA, workload='high', collab=False,
            est_cost=3800, est_hours=44, hourly=87.5, actual_cost=2090,
            assignee=self.priya, creator=self.marcus,
            label_names=['Database', 'Backend', 'Value-Added'], labels=labels,
            checklist=[
                ('Write migrations for all 23 tables with proper constraints', True),
                ('Create seed scripts for lookup and reference tables', True),
                ('Write rollback procedures and test in staging', False),
            ],
            comments=[
                (self.priya, 'Migrations for all core tables are done. Currently working on the rollback procedures - they are more complex than estimated because of the circular reference between Board and Organization. May need 2 extra days.', 1),
            ],
        )
        # P3 - OVERDUE SCENARIO: seed values are deeply negative so the task is
        # overdue right after population. The daily refresh pins this task to
        # always appear 8 days past-due (see _OVERDUE_PINS in demo_date_refresh.py).
        out['P3'] = self._make_task(
            code='P3', title='Social Login Integration',
            description=('Implement OAuth 2.0 social login for Google and GitHub providers using '
                         'django-allauth. This task is blocked by two upstream dependencies: '
                         'Database Schema & Migrations (P2) must complete the oauth_provider_tokens '
                         'table before provider tokens can be stored, and the Authentication System '
                         '(R1) depends on final security sign-off before the session integration '
                         'layer can be wired in. Handle account linking for users who register with '
                         'email first then try to login with social, manage token storage, implement '
                         'the consent screen flows, and add social login buttons to the authentication UI.'),
            column=col['In Progress'], phase=PHASE_CORE, parent=epics['auth'],
            priority='high', start_offset=-34, due_offset=-24, progress=45,
            complexity=6, risk_l='high', risk_i='medium', risk_level='high',
            lss=LSS_VA, workload='medium', collab=False,
            est_cost=3000, est_hours=34, hourly=87.5, actual_cost=1350,
            assignee=self.priya, creator=self.marcus,  # SAME ASSIGNEE AS P2 - intentional conflict
            label_names=['Backend', 'Security', 'Value-Added'], labels=labels,
            checklist=[
                ('Configure django-allauth for Google OAuth 2.0', True),
                ('Implement GitHub OAuth provider and token storage', False),
                ('Handle account linking edge cases', False),
            ],
            comments=[
                (self.priya, 'Google OAuth is working but I am blocked on two things simultaneously - the DB migrations are taking longer than expected AND the GitHub OAuth has an undocumented scope behaviour I need to investigate. Flagging for tomorrow\'s standup.', 1),
                (self.priya, "Noted. This is now past due. Let's discuss reprioritisation - Marcus can you pair with Priya on the GitHub OAuth piece?", 0),
            ],
        )
        out['P4'] = self._make_task(
            code='P4', title='API Gateway Configuration',
            description=('Configure the API gateway layer: implement global rate limiting '
                         '(100 requests/minute per user), set up API key management for external '
                         'integrations, add request/response logging middleware, configure CORS '
                         'policies for the frontend and mobile PWA, and establish API health check '
                         'endpoints.'),
            column=col['In Progress'], phase=PHASE_CORE, parent=epics['api'],
            priority='medium', start_offset=-8, due_offset=10, progress=35,
            complexity=5, risk_l='low', risk_i='medium', risk_level='low',
            lss=LSS_VA, workload='medium', collab=False,
            est_cost=2400, est_hours=28, hourly=85, actual_cost=840,
            assignee=self.elena, creator=self.priya,
            label_names=['DevOps', 'API', 'Value-Added'], labels=labels,
            checklist=[
                ('Implement rate limiting middleware with per-user quotas', True),
                ('Configure CORS policies for frontend and PWA origins', False),
                ('Set up API health check and readiness endpoints', False),
            ],
            comments=[
                (self.elena, 'Rate limiting is live. CORS configuration is next - need to confirm the production domain list with the team before locking it down.', 2),
            ],
        )

        # ===================== TO DO (6) =====================
        out['T1'] = self._make_task(
            code='T1', title='Google OAuth 2.0 Integration',
            description=('Full Google OAuth 2.0 integration for user login and Google Calendar '
                         'sync. Implement the OAuth consent screen, handle token storage with '
                         'AES-256 encryption, build the token refresh mechanism, and set up the '
                         'two-way Google Calendar sync that automatically mirrors task due dates '
                         'as Calendar events.'),
            column=col['To Do'], phase=PHASE_INTEGRATIONS, parent=epics['integrations'],
            priority='high', start_offset=3, due_offset=16, progress=0,
            complexity=7, risk_l='medium', risk_i='medium', risk_level='medium',
            lss=LSS_VA, workload='medium', collab=False,
            est_cost=3600, est_hours=40, hourly=90, actual_cost=0,
            assignee=self.priya, creator=self.priya,
            label_names=['Backend', 'API', 'Value-Added'], labels=labels,
            checklist=[
                ('Implement Google OAuth consent screen and callback handler', False),
                ('Build AES-256 encrypted token storage and refresh logic', False),
                ('Set up two-way Google Calendar sync for task due dates', False),
            ],
            comments=[
                (self.priya, 'This is a key enterprise feature. Priority is high - calendar sync is one of the top-requested items from beta users.', 3),
            ],
        )
        out['T2'] = self._make_task(
            code='T2', title='GitHub OAuth 2.0 Integration',
            description=('Implement GitHub OAuth 2.0 login and the GitHub Webhook Receiver that '
                         'automatically moves tasks to "In Review" when a pull request mentions a '
                         'task ID (e.g., SD-101) in its title or description. Includes per-board '
                         'configuration, HMAC-SHA256 secret verification, and the PR-to-task linking '
                         'logic.'),
            column=col['To Do'], phase=PHASE_INTEGRATIONS, parent=epics['integrations'],
            priority='high', start_offset=5, due_offset=18, progress=0,
            complexity=6, risk_l='low', risk_i='medium', risk_level='low',
            lss=LSS_VA, workload='medium', collab=False,
            est_cost=3200, est_hours=36, hourly=90, actual_cost=0,
            assignee=self.marcus, creator=self.priya,
            label_names=['Backend', 'API', 'Value-Added'], labels=labels,
            checklist=[
                ('Implement GitHub OAuth callback and account linking', False),
                ('Build webhook receiver with HMAC-SHA256 verification', False),
                ('Implement PR title/body task ID parsing and column move', False),
            ],
            comments=[
                (self.marcus, 'Picked this up as a natural follow-on from the social login work. The webhook receiver should be straightforward - the PR parsing logic is the interesting part.', 4),
            ],
        )
        out['T3'] = self._make_task(
            code='T3', title='Mobile Push Notifications',
            description=('Implement real-time push notifications for the mobile PWA using '
                         'Firebase Cloud Messaging (FCM). Cover notification types: task '
                         'assignment, comment mentions, deadline warnings, and AI Coach alerts. '
                         'Include per-user notification preference management and a unified '
                         'notification centre in the app header.'),
            column=col['To Do'], phase=PHASE_INTEGRATIONS, parent=epics['integrations'],
            priority='medium', start_offset=10, due_offset=24, progress=0,
            complexity=7, risk_l='medium', risk_i='medium', risk_level='medium',
            lss=LSS_VA, workload='medium', collab=True,
            est_cost=4200, est_hours=48, hourly=87.5, actual_cost=0,
            assignee=self.marcus, creator=self.priya,
            label_names=['Frontend', 'Backend', 'Value-Added'], labels=labels,
            checklist=[
                ('Configure Firebase Cloud Messaging and service worker', False),
                ('Implement 4 notification types with payload schemas', False),
                ('Build notification preference centre and unread badge', False),
            ],
            comments=[
                (self.priya, "This is gated on the API gateway work. Make sure Elena's rate limiting covers the FCM callback endpoints.", 5),
            ],
        )
        out['T4'] = self._make_task(
            code='T4', title='iOS APNs Integration',
            description=('Integrate Apple Push Notification Service (APNs) for iOS users of the '
                         'mobile PWA. Implement APNs token registration, the server-side APNs '
                         'delivery via the HTTP/2 APNs API, certificate management, and fallback '
                         'to FCM for cross-platform notification unification.'),
            column=col['To Do'], phase=PHASE_INTEGRATIONS, parent=epics['integrations'],
            priority='medium', start_offset=18, due_offset=30, progress=0,
            complexity=6, risk_l='medium', risk_i='low', risk_level='low',
            lss=LSS_VA, workload='medium', collab=False,
            est_cost=2800, est_hours=32, hourly=87.5, actual_cost=0,
            assignee=self.elena, creator=self.priya,
            label_names=['DevOps', 'Backend', 'Value-Added'], labels=labels,
            checklist=[
                ('Configure APNs certificates and HTTP/2 delivery client', False),
                ('Implement APNs token registration flow on iOS', False),
                ('Build fallback logic to FCM for cross-platform unification', False),
            ],
            comments=[
                (self.elena, 'Blocked on T3 (Mobile Push Notifications) completing first - APNs is the iOS-specific layer on top of the FCM foundation.', 6),
            ],
        )
        out['T5'] = self._make_task(
            code='T5', title='API Rate Limiting & Abuse Prevention',
            description=('Implement comprehensive API abuse prevention: per-user and per-IP rate '
                         'limiting with configurable thresholds, free-tier AI credit quotas, model '
                         'tiering for BYOK users, response length caps, circuit breaker pattern for '
                         'external AI provider calls, and a self-service rate limit dashboard for '
                         'API key holders.'),
            column=col['To Do'], phase=PHASE_LAUNCH, parent=epics['api'],
            priority='high', start_offset=22, due_offset=35, progress=0,
            complexity=7, risk_l='medium', risk_i='high', risk_level='high',
            lss=LSS_NVA, workload='high', collab=True,
            est_cost=3800, est_hours=44, hourly=85, actual_cost=0,
            assignee=self.elena, creator=self.priya,
            label_names=['DevOps', 'Backend', 'Necessary NVA'], labels=labels,
            checklist=[
                ('Implement per-user and per-IP rate limiting with Redis', False),
                ('Build AI credit quota system with model tiering', False),
                ('Implement circuit breaker for external AI provider calls', False),
            ],
            comments=[
                (self.priya, 'This is critical for open source launch. Without abuse prevention the BYOK model will be exploited. Do not deprioritise this.', 7),
            ],
        )
        out['T6'] = self._make_task(
            code='T6', title='Accessibility Compliance (WCAG 2.1 AA)',
            description=('Audit and remediate the entire frontend for WCAG 2.1 AA compliance: '
                         'keyboard navigation for all interactive elements, ARIA labels on complex '
                         'components, color contrast ratio fixes (minimum 4.5:1 for normal text), '
                         'focus management in modals and drawers, screen reader testing with NVDA '
                         'and VoiceOver, and an automated accessibility test suite in CI.'),
            column=col['To Do'], phase=PHASE_LAUNCH, parent=epics['foundation'],
            priority='medium', start_offset=28, due_offset=42, progress=0,
            complexity=6, risk_l='low', risk_i='medium', risk_level='low',
            lss=LSS_NVA, workload='medium', collab=True,
            est_cost=3200, est_hours=36, hourly=87.5, actual_cost=0,
            assignee=self.marcus, creator=self.priya,
            label_names=['Frontend', 'Testing', 'Necessary NVA'], labels=labels,
            checklist=[
                ('Run automated WCAG audit and document all findings', False),
                ('Fix keyboard navigation and ARIA labelling issues', False),
                ('Add axe-core accessibility tests to CI pipeline', False),
            ],
            comments=[
                (self.marcus, 'Scheduled for Phase 4. Running a preliminary axe-core scan this week to scope the effort - want to flag any surprises early.', 8),
            ],
        )

        # ===================== BACKLOG (8) =====================
        out['B1'] = self._make_task(
            code='B1', title='Performance Optimisation Sprint',
            description=('Systematic performance audit and improvement: Django query optimisation '
                         'using select_related/prefetch_related, Redis caching strategy for '
                         'expensive computations, database query plan analysis and index tuning, '
                         'frontend bundle size reduction via code splitting, Lighthouse score '
                         'targets (Performance > 90 on mobile), and load testing with 500 concurrent '
                         'users.'),
            column=col['Backlog'], phase=PHASE_LAUNCH, parent=epics['foundation'],
            priority='high', start_offset=35, due_offset=49, progress=0,
            complexity=8, risk_l='medium', risk_i='high', risk_level='high',
            lss=LSS_VA, workload='high', collab=True,
            est_cost=5600, est_hours=64, hourly=87.5, actual_cost=0,
            assignee=self.elena, creator=self.priya,
            label_names=['DevOps', 'Backend', 'Performance', 'Value-Added'], labels=labels,
            checklist=[
                ('Profile all API endpoints and identify N+1 queries', False),
                ('Implement Redis caching for board analytics queries', False),
                ('Run load test and document baseline performance metrics', False),
            ],
        )
        out['B2'] = self._make_task(
            code='B2', title='Production Deployment to Google Cloud Run',
            description=('Deploy PrizmAI to Google Cloud Run with full production configuration: '
                         'Neon PostgreSQL for the database, Redis on Cloud Memorystore, Cloud '
                         'Storage for file uploads, environment variable management via Secret '
                         'Manager, custom domain configuration with SSL, health check endpoints, '
                         'auto-scaling configuration, and a staged rollout plan (dev -> staging -> '
                         'production).'),
            column=col['Backlog'], phase=PHASE_LAUNCH, parent=epics['foundation'],
            priority='urgent', start_offset=50, due_offset=60, progress=0,
            complexity=9, risk_l='high', risk_i='high', risk_level='high',
            lss=LSS_NVA, workload='high', collab=True,
            est_cost=6400, est_hours=72, hourly=90, actual_cost=0,
            assignee=self.elena, creator=self.priya,
            label_names=['DevOps', 'Necessary NVA'], labels=labels,
            checklist=[
                ('Configure Cloud Run service with auto-scaling policies', False),
                ('Set up Neon PostgreSQL and run production migration', False),
                ('Configure Secret Manager and production environment vars', False),
                ('Execute staged rollout with rollback plan', False),
            ],
        )
        out['B3'] = self._make_task(
            code='B3', title='Slack & Microsoft Teams Webhooks',
            description=('Implement outbound webhook integrations for Slack and Microsoft Teams: '
                         'formatted message delivery for task events (created, completed, overdue, '
                         'at-risk), AI Digest summaries posted on a schedule, one-click quick-setup '
                         'presets in the board settings UI, HMAC signature verification on incoming '
                         'webhooks, and a webhook activity log.'),
            column=col['Backlog'], phase=PHASE_LAUNCH, parent=epics['integrations'],
            priority='medium', start_offset=32, due_offset=45, progress=0,
            complexity=5, risk_l='low', risk_i='medium', risk_level='low',
            lss=LSS_VA, workload='medium', collab=False,
            est_cost=2800, est_hours=32, hourly=87.5, actual_cost=0,
            assignee=self.priya, creator=self.priya,
            label_names=['Backend', 'API', 'Value-Added'], labels=labels,
            checklist=[
                ('Build Slack webhook sender with Block Kit formatting', False),
                ('Build MS Teams webhook sender with Adaptive Cards', False),
                ('Add quick-setup preset UI in board settings', False),
            ],
        )
        out['B4'] = self._make_task(
            code='B4', title='Zapier Integration',
            description=('Build the Zapier integration: Django REST polling endpoints for New '
                         'Task, Task Completed, and Task Assigned triggers; Create Task and Update '
                         'Status actions; a self-contained Zapier CLI app in zapier-app/ directory; '
                         'and comprehensive documentation for publishing to the Zapier marketplace.'),
            column=col['Backlog'], phase=PHASE_LAUNCH, parent=epics['integrations'],
            priority='low', start_offset=38, due_offset=50, progress=0,
            complexity=5, risk_l='low', risk_i='low', risk_level='low',
            lss=LSS_VA, workload='low', collab=False,
            est_cost=2400, est_hours=28, hourly=85, actual_cost=0,
            assignee=self.marcus, creator=self.priya,
            label_names=['Backend', 'API', 'Value-Added'], labels=labels,
            checklist=[
                ('Build REST polling endpoints for all Zapier triggers', False),
                ('Write Zapier CLI app with authentication and test suite', False),
                ('Document marketplace submission requirements', False),
            ],
        )
        out['B5'] = self._make_task(
            code='B5', title='Open Source Launch Preparation',
            description=('Prepare PrizmAI for open source release: write CONTRIBUTING.md with '
                         'contribution guidelines and PR template, create INTEGRATIONS.md with '
                         'integration template for community contributions, write developer-facing '
                         'README architecture section, set up GitHub issue templates, configure '
                         'GitHub Actions for community PR CI, and produce a technical blog post '
                         'explaining the architecture.'),
            column=col['Backlog'], phase=PHASE_LAUNCH, parent=epics['foundation'],
            priority='high', start_offset=61, due_offset=72, progress=0,
            complexity=4, risk_l='low', risk_i='medium', risk_level='low',
            lss=LSS_NVA, workload='medium', collab=True,
            est_cost=2400, est_hours=28, hourly=85, actual_cost=0,
            assignee=self.priya, creator=self.priya,
            label_names=['Documentation', 'Necessary NVA'], labels=labels,
            checklist=[
                ('Write CONTRIBUTING.md and GitHub issue/PR templates', False),
                ('Create INTEGRATIONS.md with community contribution guide', False),
                ('Write architecture blog post for technical audiences', False),
            ],
        )
        out['B6'] = self._make_task(
            code='B6', title='End-to-End Test Suite',
            description=('Build a comprehensive end-to-end test suite using Playwright: cover '
                         'all critical user journeys (registration -> board creation -> task '
                         'management -> collaboration -> AI features), implement visual regression '
                         'testing for key UI components, set up test data factories, and integrate '
                         'E2E tests into the CI pipeline with parallel test execution.'),
            column=col['Backlog'], phase=PHASE_LAUNCH, parent=epics['foundation'],
            priority='medium', start_offset=30, due_offset=44, progress=0,
            complexity=7, risk_l='medium', risk_i='medium', risk_level='medium',
            lss=LSS_NVA, workload='medium', collab=False,
            est_cost=4000, est_hours=46, hourly=87.5, actual_cost=0,
            assignee=self.elena, creator=self.priya,
            label_names=['Testing', 'DevOps', 'Necessary NVA'], labels=labels,
            checklist=[
                ('Set up Playwright with test data factories and fixtures', False),
                ('Write E2E tests for all 8 critical user journeys', False),
                ('Integrate into CI with parallel execution and reporting', False),
            ],
        )
        out['B7'] = self._make_task(
            code='B7', title='API Documentation (Swagger/OpenAPI)',
            description=('Generate and publish comprehensive API documentation: auto-generate '
                         'OpenAPI 3.0 spec from DRF serializers, host interactive Swagger UI at '
                         '/api/docs/, write human-readable guides for authentication, pagination, '
                         'error handling, and rate limiting, add request/response examples for all '
                         '40+ endpoints, and create a Postman collection for developer testing.'),
            column=col['Backlog'], phase=PHASE_LAUNCH, parent=epics['api'],
            priority='medium', start_offset=40, due_offset=52, progress=0,
            complexity=4, risk_l='low', risk_i='low', risk_level='low',
            lss=LSS_NVA, workload='low', collab=False,
            est_cost=1800, est_hours=20, hourly=90, actual_cost=0,
            assignee=self.priya, creator=self.priya,
            label_names=['Documentation', 'API', 'Necessary NVA'], labels=labels,
            checklist=[
                ('Configure drf-spectacular for OpenAPI 3.0 auto-generation', False),
                ('Write narrative guides for auth, pagination, and errors', False),
                ('Export Postman collection and publish to team workspace', False),
            ],
        )
        out['B8'] = self._make_task(
            code='B8', title='Cognitive Load & Burnout Monitoring',
            description=('Enhance the Cognitive Load Guardian feature with richer monitoring: '
                         'implement per-member context-switching frequency scoring, add a weekly '
                         'cognitive load trend chart on the team dashboard, configure automated '
                         'alerts when any member exceeds the 80% overload threshold for 3 '
                         'consecutive days, and integrate recommendations into the AI Coach '
                         'recovery suggestions.'),
            column=col['Backlog'], phase=PHASE_LAUNCH, parent=epics['api'],
            priority='low', start_offset=46, due_offset=56, progress=0,
            complexity=6, risk_l='low', risk_i='medium', risk_level='low',
            lss=LSS_VA, workload='medium', collab=True,
            est_cost=3200, est_hours=36, hourly=87.5, actual_cost=0,
            assignee=self.marcus, creator=self.priya,
            label_names=['Backend', 'Frontend', 'Value-Added'], labels=labels,
            checklist=[
                ('Build context-switching frequency scoring algorithm', False),
                ('Add cognitive load trend chart to team dashboard', False),
                ('Wire burnout alerts into AI Coach recommendation engine', False),
            ],
        )

        self.stdout.write(f'  [OK] Created 4 epics + {len(out)} child tasks')
        return out

    # ------------------------------------------------------------------
    # Timeline dependencies
    # ------------------------------------------------------------------
    def _link_dependencies(self, t):
        """Set the M2M Task.dependencies arrows that drive the Gantt chart.

        Each phase carries its own internal chain so the Gantt shows realistic
        intra-phase links (not just cross-phase handoffs), and CPM has enough
        edges to compute meaningful slack inside each phase.
        """
        pairs = [
            # Phase 1 -- Foundation: requirements feed architecture, architecture
            # feeds DB schema and security patterns. D2 (env setup) runs in parallel.
            ('D1', 'D3'),
            ('D3', 'D4'),
            ('D3', 'D5'),
            # Phase 1 -> Phase 2 handoffs
            ('D4', 'P2'),
            ('D5', 'P3'),
            ('D5', 'R1'),
            # Phase 2 -- Core Features
            ('D6', 'P4'),
            ('D7', 'R1'),
            ('D8', 'R1'),
            ('R1', 'P1'),
            # Phase 2 -> Phase 3 handoffs
            ('P1', 'T1'),
            ('P1', 'T2'),
            # Phase 3 -- Integrations
            ('T1', 'T3'),
            ('T3', 'T4'),
            # Phase 2 / 3 -> Phase 4 handoffs
            ('P4', 'T5'),
            # Phase 4 -- Launch Readiness: perf + rate limit + E2E tests gate
            # the prod deploy; deploy + accessibility + API docs gate the OSS launch.
            ('B1', 'B2'),
            ('T5', 'B2'),
            ('B6', 'B2'),
            ('B2', 'B5'),
            ('T6', 'B5'),
            ('B7', 'B5'),
        ]
        for from_code, to_code in pairs:
            t[to_code].dependencies.add(t[from_code])
        self.stdout.write(f'  [OK] Linked {len(pairs)} timeline dependencies')

    # ------------------------------------------------------------------
    # Milestones
    # ------------------------------------------------------------------
    def _create_milestones(self, tasks_by_code):
        """Create 3 milestone Tasks (item_type='milestone') for the Gantt chart.

        Each milestone is anchored to the last task of its phase via
        position_after_task so it renders inline after that task in the Gantt
        row order (see buildOrderedTaskList in gantt_chart.html). Without the
        anchor, milestones fall through to the end of the list.
        """
        col = self.columns['Backlog']
        ms_defs = [
            ('Foundation Architecture Complete',
             'All Phase 1 infrastructure, architecture, and environment setup tasks completed and verified.',
             -21, 'completed', PHASE_FOUNDATION, 'D8'),
            ('Core Authentication Ready',
             'Complete authentication system, RBAC, security patterns, and auth test suite all passing.',
             7, 'upcoming', PHASE_CORE, 'P4'),
            ('Integration Sprint Complete',
             'All third-party integrations (Google, GitHub, FCM, APNs, webhooks) built, tested, and deployed.',
             49, 'upcoming', PHASE_INTEGRATIONS, 'T5'),
        ]
        for title, desc, due_off, status, phase, anchor_code in ms_defs:
            Task.objects.create(
                title=title,
                description=desc,
                column=col,
                phase=phase,
                item_type='milestone',
                milestone_status=status,
                priority='high',
                start_date=self.TODAY + timedelta(days=due_off),
                due_date=_aware_due(self.TODAY + timedelta(days=due_off)),
                progress=100 if status == 'completed' else 0,
                completed_at=self._days_ago(-due_off) if status == 'completed' else None,
                assigned_to=self.priya,
                created_by=self.priya,
                position_after_task=tasks_by_code[anchor_code],
                is_seed_demo_data=True,
            )
        self.stdout.write('  [OK] Created 3 milestones')

    # ------------------------------------------------------------------
    # Budget & time tracking
    # ------------------------------------------------------------------
    def _create_budget_and_time(self, tasks_by_code, epics):
        """Project budget + time entries for done/in-review/in-progress tasks."""
        ProjectBudget.objects.create(
            board=self.board,
            allocated_budget=Decimal('85000.00'),
            currency='USD',
            allocated_hours=Decimal('980.00'),
            warning_threshold=75,
            critical_threshold=92,
            ai_optimization_enabled=True,
            created_by=self.priya,
        )

        time_entry_count = 0
        for code, task in tasks_by_code.items():
            if task.column.name == 'Done':
                target_pct = 1.0
            elif task.column.name == 'In Review':
                target_pct = 0.9
            elif task.column.name == 'In Progress':
                target_pct = task.progress / 100.0
            else:
                continue

            cost = task.cost  # OneToOne
            total_hours = float(cost.estimated_hours) * target_pct
            if total_hours <= 0 or not task.start_date:
                continue

            # Spread across 3-6 entries within the task window
            num_entries = random.choice([3, 4, 5, 6])
            entries = self._distribute_hours(total_hours, num_entries)

            start = task.start_date
            end_date = (task.completed_at.date()
                        if task.completed_at
                        else self.TODAY)
            # Clamp window
            span_days = max((end_date - start).days, 1)

            descriptions = [
                'Implementation work and unit tests',
                'Pair programming session and code review',
                'Bug fixing and edge case handling',
                'Integration testing and verification',
                'Refactoring and documentation updates',
                'Code review feedback and follow-up changes',
            ]

            for i, hrs in enumerate(entries):
                work_date = start + timedelta(days=int((i + 1) * span_days / (num_entries + 1)))
                TimeEntry.objects.create(
                    task=task,
                    user=task.assigned_to,
                    hours_spent=Decimal(f'{hrs:.2f}'),
                    work_date=work_date,
                    description=random.choice(descriptions) + f' - {task.title}',
                    is_billable=True,
                )
                time_entry_count += 1

        self.stdout.write(
            f'  [OK] Budget created. {time_entry_count} time entries logged.'
        )

    @staticmethod
    def _distribute_hours(total, n):
        """Split `total` hours across `n` entries with mild random variation."""
        weights = [random.uniform(0.7, 1.3) for _ in range(n)]
        s = sum(weights)
        return [max(0.25, round(total * w / s, 2)) for w in weights]

    # ------------------------------------------------------------------
    # Stakeholders
    # ------------------------------------------------------------------
    def _create_stakeholders(self, tasks_by_code):
        defs = [
            ('Sarah Mitchell', 'Product Director', 'sarah.mitchell@demo.prizmai.local',
             'high', 'high', 'collaborate', 'empower'),
            ('David Park', 'CTO', 'david.park@demo.prizmai.local',
             'high', 'medium', 'consult', 'inform'),
            ('Rachel Torres', 'QA Lead', 'rachel.torres@demo.prizmai.local',
             'medium', 'high', 'involve', 'collaborate'),
            ('James Okonkwo', 'Security Officer', 'james.okonkwo@demo.prizmai.local',
             'high', 'medium', 'consult', 'consult'),
        ]
        stakeholders = {}
        for name, role, email, infl, intr, cur, des in defs:
            sh, _ = ProjectStakeholder.objects.get_or_create(
                board=self.board, name=name, email=email,
                defaults={
                    'role': role, 'organization': 'Acme Corporation',
                    'influence_level': infl, 'interest_level': intr,
                    'current_engagement': cur, 'desired_engagement': des,
                    'created_by': self.priya,
                },
            )
            stakeholders[name] = sh

        # Link key stakeholders to key tasks
        security_tasks = ['D5', 'D7', 'D8', 'R1', 'T5']
        for code in security_tasks:
            StakeholderTaskInvolvement.objects.get_or_create(
                stakeholder=stakeholders['James Okonkwo'],
                task=tasks_by_code[code],
                defaults={'involvement_type': 'reviewer',
                          'engagement_status': 'consulted'},
            )
        # Product Director on key Phase-2 deliverables
        for code in ['R1', 'P1', 'D8']:
            StakeholderTaskInvolvement.objects.get_or_create(
                stakeholder=stakeholders['Sarah Mitchell'],
                task=tasks_by_code[code],
                defaults={'involvement_type': 'approver',
                          'engagement_status': 'collaborated'},
            )
        for code in ['B6', 'R2']:
            StakeholderTaskInvolvement.objects.get_or_create(
                stakeholder=stakeholders['Rachel Torres'],
                task=tasks_by_code[code],
                defaults={'involvement_type': 'reviewer',
                          'engagement_status': 'involved'},
            )

        self.stdout.write(f'  [OK] Created {len(defs)} stakeholders')

    # ------------------------------------------------------------------
    # Scope baseline
    # ------------------------------------------------------------------
    def _create_scope_baseline(self):
        try:
            from kanban.models import ScopeChangeSnapshot
            # Idempotent: a non-reset re-run must not stack another baseline
            # row on top of the existing one.
            existing = ScopeChangeSnapshot.objects.filter(
                board=self.board, is_baseline=True,
            ).first()
            if existing:
                self.stdout.write('  [OK] Scope baseline already present - skipped')
                return
            self.board.create_scope_snapshot(
                user=self.priya,
                snapshot_type='manual',
                is_baseline=True,
                notes=('Initial project baseline - established at project kickoff '
                       'with 26 tasks across 4 phases.'),
            )
            self.stdout.write('  [OK] Scope baseline snapshot recorded')
        except Exception as e:
            self.stdout.write(self.style.WARNING(f'  [WARN] Could not create scope snapshot: {e}'))

    # ------------------------------------------------------------------
    # Scope Autopsy (forensic scope growth report)
    # ------------------------------------------------------------------
    def _create_scope_autopsy(self):
        """Seed a completed Scope Autopsy report with a believable
        Scope Growth Timeline.

        The Autopsy feature would normally be generated on demand by an AI
        worker, but for the demo we pre-populate a finished report so visitors
        immediately see the timeline, events, and recommendations without
        burning AI quota. The story is intentionally a *mild* growth scenario
        (16.7%, all documented) rather than a catastrophic one — the demo
        should showcase the feature, not slander the demo project.
        """
        try:
            from kanban.scope_autopsy_models import (
                ScopeAutopsyReport, ScopeTimelineEvent, TaskScopeReason,
            )
            from kanban.models import Task
            from decimal import Decimal

            # Remove any prior report so re-running this seeder is idempotent
            ScopeAutopsyReport.objects.filter(board=self.board).delete()

            current_task_count = Task.objects.filter(
                column__board=self.board, item_type='task',
            ).count()
            # Story: project started with 24 tasks, grew to current count
            # (typically 28) over the project lifecycle. All four additions
            # are documented, so the AI verdict is "well-managed scope".
            baseline_count = max(1, current_task_count - 4)
            growth_pct = round(
                ((current_task_count - baseline_count) / baseline_count) * 100, 1
            )

            kickoff = self.NOW - timedelta(days=56)
            baseline_date = kickoff + timedelta(hours=24)

            # Pre-build timeline event payload — dates flow chronologically
            # through Phases 1 and 2 so the timeline aligns with the rest of
            # the demo's narrative.
            events_payload = [
                {
                    'days_ago': 49,
                    'title': 'Authentication Testing Suite added',
                    'description': (
                        'Security team requested a dedicated testing harness for the '
                        'authentication flow after the threat-modeling workshop. Added 1 task '
                        'and updated the Security Architecture Patterns acceptance criteria.'
                    ),
                    'source_type': 'task_added',
                    'tasks_added': 1,
                    'delay_days': 2,
                    'budget_impact': Decimal('1800.00'),
                    'added_by': self.priya,
                    'reason': 'requirement_change',
                    'reason_note': (
                        'Security review at end of week 1 surfaced a gap in our auth test '
                        'coverage; scoped a dedicated suite rather than expanding existing tests.'
                    ),
                },
                {
                    'days_ago': 38,
                    'title': 'API Rate Limiting added during security review',
                    'description': (
                        'External penetration test highlighted brute-force exposure on the auth '
                        'endpoints. Added rate-limiting middleware as a Phase 1 deliverable.'
                    ),
                    'source_type': 'scope_alert',
                    'tasks_added': 1,
                    'delay_days': 3,
                    'budget_impact': Decimal('2400.00'),
                    'added_by': self.elena,
                    'reason': 'discovered_complexity',
                    'reason_note': (
                        'Pen-test finding — could not ship Phase 1 without remediation. '
                        'Scoped as a hard requirement, accepted small delay.'
                    ),
                },
                {
                    'days_ago': 24,
                    'title': 'Accessibility Compliance task added',
                    'description': (
                        'Product Director requested WCAG 2.1 AA compliance as a launch '
                        'requirement. Added an accessibility audit and remediation task to '
                        'Phase 2 ahead of the public beta.'
                    ),
                    'source_type': 'task_added',
                    'tasks_added': 1,
                    'delay_days': 2,
                    'budget_impact': Decimal('1900.00'),
                    'added_by': self.marcus,
                    'reason': 'stakeholder_request',
                    'reason_note': (
                        'Sarah Mitchell (Product Director) confirmed accessibility is a '
                        'launch gate; absorbed into Phase 2 with stakeholder sign-off.'
                    ),
                },
                {
                    'days_ago': 11,
                    'title': 'Error Tracking & Monitoring added',
                    'description': (
                        'AI Coach suggestion accepted: add Sentry-based error tracking and '
                        'a dashboard pre-launch so we can monitor the beta rollout.'
                    ),
                    'source_type': 'ai_suggestion',
                    'tasks_added': 1,
                    'delay_days': 1,
                    'budget_impact': Decimal('1200.00'),
                    'added_by': self.elena,
                    'reason': 'discovered_complexity',
                    'reason_note': (
                        'Observability gap flagged by AI Coach; better to add it before '
                        'launch than scramble post-launch.'
                    ),
                },
            ]

            total_delay = sum(e['delay_days'] for e in events_payload)
            total_budget = sum(e['budget_impact'] for e in events_payload)

            ai_summary = (
                f'The Software Development project grew from {baseline_count} tasks at '
                f'kickoff to {current_task_count} tasks today — a {growth_pct}% expansion '
                f'over roughly 8 weeks. All four scope additions were recorded with a '
                'documented reason, putting this project well below the 25%+ undocumented '
                'growth typical of comparable engineering programs. Two of the four '
                'additions (Rate Limiting, Error Tracking) addressed real risks discovered '
                'during execution; the other two (Auth Test Suite, Accessibility) were '
                'planning gaps surfaced in week-1 security review and stakeholder '
                'alignment.'
            )
            pattern_analysis = (
                'Scope growth was front-loaded and event-driven rather than chaotic — three '
                'of four additions came during Phase 1 security/quality reviews, which is '
                'the *right* time to absorb new requirements. The remaining Phase 2 addition '
                '(observability) was a coach-suggested gap closure. There is no evidence of '
                'gold-plating or stakeholder churn.'
            )
            recommendations = [
                {
                    'title': 'Move the threat-modeling workshop into kickoff week',
                    'description': (
                        'The Auth Test Suite and Rate Limiting tasks were both surfaced by '
                        'security reviews after kickoff. Folding a lightweight threat-modeling '
                        'session into Day 2 of kickoff would have captured both during the '
                        'initial baseline.'
                    ),
                    'applies_to': 'planning',
                },
                {
                    'title': 'Confirm launch-gate requirements with stakeholders pre-baseline',
                    'description': (
                        'Accessibility compliance was added in Phase 2 but is a launch-gate '
                        'requirement. A short pre-baseline stakeholder confirmation call (15 '
                        'minutes per key stakeholder) would catch these earlier.'
                    ),
                    'applies_to': 'stakeholder_management',
                },
                {
                    'title': 'Pre-commit observability into Phase 1 by default',
                    'description': (
                        'Error tracking is a standard launch requirement; rather than relying '
                        'on coach suggestions in Phase 2, ship it as a default Phase 1 '
                        'deliverable in the project template.'
                    ),
                    'applies_to': 'execution',
                },
            ]

            board_snapshot = {
                'board_name': self.board.name,
                'project_context': self.board.name,
                'baseline_task_count': baseline_count,
                'baseline_date': str(baseline_date),
                'final_task_count': current_task_count,
                'growth_percentage': growth_pct,
                'days_elapsed': 56,
                'total_events': len(events_payload),
            }

            timeline_json = []
            cumulative = baseline_count
            for e in events_payload:
                cumulative += e['tasks_added']
                timeline_json.append({
                    'date': str(self.NOW - timedelta(days=e['days_ago'])),
                    'title': e['title'],
                    'description': e['description'],
                    'source_type': e['source_type'],
                    'tasks_added': e['tasks_added'],
                    'net_task_change': e['tasks_added'],
                    'is_major_event': e['tasks_added'] >= 3,
                    'estimated_delay_days': e['delay_days'],
                    'estimated_budget_impact': float(e['budget_impact']),
                    'added_by_name': (
                        e['added_by'].get_full_name() or e['added_by'].username
                    ) if e['added_by'] else '',
                })

            report = ScopeAutopsyReport.objects.create(
                board=self.board,
                created_by=self.priya,
                status='complete',
                baseline_task_count=baseline_count,
                baseline_date=baseline_date,
                final_task_count=current_task_count,
                total_scope_growth_percentage=growth_pct,
                total_delay_days=total_delay,
                total_budget_impact=total_budget,
                timeline_json=timeline_json,
                pattern_analysis=pattern_analysis,
                ai_summary=ai_summary,
                recommendations=recommendations,
                board_snapshot=board_snapshot,
            )
            # ScopeAutopsyReport.created_at uses auto_now_add — override so
            # the report's "Analyzed" timestamp lives a few days back (the
            # original analysis happened during the last sprint review,
            # not literally today).
            ScopeAutopsyReport.objects.filter(pk=report.pk).update(
                created_at=self.NOW - timedelta(days=3),
            )

            # Timeline events (cumulative counts are computed inline)
            cumulative = baseline_count
            for e in events_payload:
                cumulative += e['tasks_added']
                ScopeTimelineEvent.objects.create(
                    report=report,
                    event_date=self.NOW - timedelta(days=e['days_ago']),
                    title=e['title'],
                    description=e['description'],
                    source_type=e['source_type'],
                    source_object_type='',
                    source_object_id=None,
                    tasks_added=e['tasks_added'],
                    tasks_removed=0,
                    net_task_change=e['tasks_added'],
                    added_by=e['added_by'],
                    estimated_delay_days=e['delay_days'],
                    estimated_budget_impact=e['budget_impact'],
                    cumulative_task_count=cumulative,
                    is_major_event=e['tasks_added'] >= 3,
                )

            # Backfill TaskScopeReason rows so the timeline shows the
            # documented reason + note alongside each task_added event. We
            # match each seeded event to a real demo task by title-keyword so
            # the Scope Reason modal isn't blank when the user clicks through.
            reason_targets = [
                ('Authentication Testing Suite',
                 events_payload[0]['reason'], events_payload[0]['reason_note'],
                 events_payload[0]['added_by']),
                ('API Rate Limiting',
                 events_payload[1]['reason'], events_payload[1]['reason_note'],
                 events_payload[1]['added_by']),
                ('Accessibility',
                 events_payload[2]['reason'], events_payload[2]['reason_note'],
                 events_payload[2]['added_by']),
                ('Error Tracking',
                 events_payload[3]['reason'], events_payload[3]['reason_note'],
                 events_payload[3]['added_by']),
            ]
            for keyword, reason, note, recorder in reason_targets:
                t = Task.objects.filter(
                    column__board=self.board,
                    item_type='task',
                    title__icontains=keyword,
                ).first()
                if t:
                    TaskScopeReason.objects.update_or_create(
                        task=t,
                        defaults={
                            'board': self.board,
                            'reason': reason,
                            'note': note,
                            'recorded_by': recorder,
                        },
                    )

            self.stdout.write(
                f'  [OK] Scope autopsy report seeded ({baseline_count} -> '
                f'{current_task_count} tasks, +{growth_pct}%, '
                f'{len(events_payload)} events)'
            )
        except Exception as e:
            self.stdout.write(self.style.WARNING(
                f'  [WARN] Could not seed scope autopsy: {e}'
            ))

    # ------------------------------------------------------------------
    # Retrospective
    # ------------------------------------------------------------------
    def _create_retrospective(self):
        # The dashboard, Lessons and Action Items pages read from the relational
        # LessonLearned / RetrospectiveActionItem / ImprovementMetric models, NOT
        # from the JSON snapshot fields on the retrospective. The real AI generator
        # (RetrospectiveGenerator.create_retrospective) stores the JSON snapshot AND
        # creates those relational records, so the demo seed mirrors that here.
        recommendations = [
            {'title': 'Adopt an ADR-first workflow for Phase 2',
             'description': 'Make "ADR drafted and approved" a Definition-of-Ready gate for any '
                            'task that introduces or changes architecture.',
             'priority': 'high', 'action_type': 'process_change',
             'expected_impact': 'Fewer mid-implementation architecture reversals and rework cycles.'},
            {'title': 'Add a security review gate to the phase-milestone checklist',
             'description': 'Schedule the security/penetration review at the start of the milestone, '
                            'not the end, so findings never threaten the phase deadline.',
             'priority': 'critical', 'action_type': 'process_change',
             'expected_impact': 'Security findings surface early with slack to remediate before milestone.'},
            {'title': 'Publish the Docker onboarding guide in the wiki',
             'description': 'Document the Docker-first dev environment setup so onboarding stays '
                            'self-service as the team grows.',
             'priority': 'medium', 'action_type': 'documentation',
             'expected_impact': 'New engineers productive in under 30 minutes without pairing.'},
            {'title': 'Introduce planning poker for Phase 2 estimation',
             'description': 'Use planning poker on tasks with hidden complexity (e.g. schema work) '
                            'to surface estimation disagreement before commitment.',
             'priority': 'high', 'action_type': 'process_change',
             'expected_impact': 'Tighter estimates and fewer overruns on complex tasks.'},
            {'title': 'Create an acceptance-criteria template for task creation',
             'description': 'A reusable acceptance-criteria checklist on the task form so tasks are '
                            'not started with thin criteria.',
             'priority': 'medium', 'action_type': 'documentation',
             'expected_impact': 'Fewer revision rounds caused by ambiguous requirements.'},
        ]

        # Reflect the configured AI provider rather than hard-coding a model name,
        # so the demo's "Model Used" matches whatever provider this instance runs.
        from ai_assistant.utils.ai_router import AIRouter
        from ai_assistant.models import OrganizationAISettings
        try:
            demo_provider = self.demo_org.ai_settings.provider or 'gemini'
        except (OrganizationAISettings.DoesNotExist, AttributeError):
            demo_provider = 'gemini'
        demo_ai_model = AIRouter.get_model_name(demo_provider, 'complex')

        retrospective = ProjectRetrospective.objects.create(
            board=self.board,
            title='Phase 1 Foundation Retrospective',
            retrospective_type='milestone',
            status='finalized',
            period_start=(self.NOW - timedelta(days=56)).date(),
            period_end=(self.NOW - timedelta(days=21)).date(),
            # Keys must match what RetrospectiveGenerator.collect_metrics produces
            # (total_tasks / completed_tasks / completion_rate / avg_completion_time),
            # otherwise retrospective_detail falls back to live board counts and shows
            # the current board state instead of this historical Phase-1 snapshot.
            metrics_snapshot={
                'total_tasks': 8, 'completed_tasks': 8, 'completion_rate': 100,
                'velocity': 52, 'avg_completion_time': 8.5,
                'quality_score': 9.1, 'budget_variance': -3.2,
            },
            what_went_well=(
                "Architecture decisions were well-documented with ADRs making future changes easier. "
                "Development environment setup was smooth - Elena's Docker configuration had new "
                "team members productive within 30 minutes. Security architecture was thorough - "
                "the penetration test passed with only two medium findings, both resolved before "
                "phase end. All 8 tasks delivered on time."
            ),
            what_needs_improvement=(
                'Database schema design took longer than estimated due to circular reference '
                'complexity. Some tasks had insufficiently detailed acceptance criteria leading '
                'to two rounds of revision. The security review for RBAC should have been '
                'scheduled earlier - it came close to blocking the phase milestone.'
            ),
            key_achievements=[
                'All 8 Phase 1 tasks delivered on time and within budget',
                'Security penetration test passed with zero critical findings',
                'Developer onboarding reduced to 30 minutes with Docker setup',
                'Architecture decision records (ADRs) written for all major choices',
            ],
            lessons_learned=[
                {'lesson': 'ADRs should be written before implementation begins, not during',
                 'priority': 'high', 'category': 'planning'},
                {'lesson': 'Security review should be a gate before any phase milestone, not an afterthought',
                 'priority': 'high', 'category': 'quality'},
                {'lesson': 'Docker-first dev environments eliminate "works on my machine" entirely',
                 'priority': 'medium', 'category': 'technical'},
                {'lesson': 'Tasks with hidden complexity need detailed acceptance criteria before estimation',
                 'priority': 'high', 'category': 'planning'},
            ],
            improvement_recommendations=recommendations,
            overall_sentiment_score=Decimal('0.88'),
            team_morale_indicator='high',
            performance_trend='improving',
            ai_generated_at=self.NOW - timedelta(days=20),
            ai_confidence_score=Decimal('0.91'),
            ai_model_used=demo_ai_model,
            created_by=self.priya,
            finalized_by=self.priya,
            finalized_at=self.NOW - timedelta(days=20),
        )

        # --- Lessons Learned (relational records the Lessons page & dashboard read) ---
        lesson_adr = LessonLearned.objects.create(
            retrospective=retrospective, board=self.board,
            title='Write ADRs before implementation, not during',
            description=('Several architecture decisions were revisited mid-implementation because '
                         'the ADRs were authored alongside the code rather than ahead of it.'),
            category='planning', priority='high',
            trigger_event='Two architecture choices were reversed after coding had already started.',
            impact_description='Roughly three days of rework across the data-model and auth layers.',
            recommended_action='Make "ADR approved" a Definition-of-Ready gate for architecture tasks.',
            action_owner=self.priya, status='implemented',
            implementation_date=(self.NOW - timedelta(days=15)).date(),
            expected_benefit='Fewer mid-implementation reversals.',
            actual_benefit='Phase 2 architecture tasks have had zero reversals so far.',
            ai_suggested=True, ai_confidence=Decimal('0.90'),
        )
        lesson_security = LessonLearned.objects.create(
            retrospective=retrospective, board=self.board,
            title='Schedule security review as a phase-milestone gate',
            description=('The RBAC security review was scheduled near the end of the phase and came '
                         'close to blocking the milestone when two medium findings surfaced.'),
            category='quality', priority='high',
            trigger_event='Penetration test ran in the final week of Phase 1.',
            impact_description='Milestone was at risk for ~48 hours while findings were remediated.',
            recommended_action='Move the security review to the start of each milestone window.',
            action_owner=self.elena, status='in_progress',
            expected_benefit='Security findings surface with time to remediate.',
            ai_suggested=True, ai_confidence=Decimal('0.88'),
        )
        lesson_docker = LessonLearned.objects.create(
            retrospective=retrospective, board=self.board,
            title='Standardise on Docker-first development environments',
            description=('Elena\'s Docker configuration eliminated "works on my machine" issues and '
                         'made onboarding effectively instant.'),
            category='technical', priority='medium',
            trigger_event='A new team member was productive within 30 minutes of joining.',
            impact_description='Onboarding time dropped from roughly half a day to under 30 minutes.',
            recommended_action='Keep the Docker setup as the single supported dev environment.',
            action_owner=self.elena, status='validated',
            implementation_date=(self.NOW - timedelta(days=44)).date(),
            validation_date=(self.NOW - timedelta(days=18)).date(),
            expected_benefit='Faster, consistent onboarding.',
            actual_benefit='A second engineer onboarded in 25 minutes during Phase 2 with no setup issues.',
            success_metrics=[{'metric': 'onboarding_time_minutes', 'before': 240, 'after': 25}],
            ai_suggested=True, ai_confidence=Decimal('0.85'),
        )
        lesson_estimation = LessonLearned.objects.create(
            retrospective=retrospective, board=self.board,
            title='Tasks with hidden complexity need detailed acceptance criteria before estimation',
            description=('Database schema work overran due to a circular reference between Board and '
                         'Organization, and two tasks needed re-work because their acceptance criteria '
                         'were too thin to estimate accurately.'),
            category='planning', priority='high',
            trigger_event='Schema task overran by two days; two tasks went through a second revision round.',
            impact_description='Estimation accuracy suffered on the most complex tasks of the phase.',
            recommended_action='Adopt planning poker and an acceptance-criteria template before estimating.',
            action_owner=self.priya, status='identified',
            is_recurring_issue=True, recurrence_count=2,
            expected_benefit='More reliable estimates on complex work.',
            ai_suggested=True, ai_confidence=Decimal('0.80'),
        )

        # --- Action Items (relational records the Action Items page & dashboard read) ---
        # Each row mirrors one improvement recommendation, with realistic mixed statuses
        # so the dashboard's completion rate and "Urgent Action Items" panel are populated.
        action_specs = [
            dict(rec=recommendations[0], owner=self.priya, related=lesson_adr,
                 status='completed', progress=100,
                 actual_completion_date=(self.NOW - timedelta(days=15)).date(),
                 actual_impact='ADR-first gate added to the Phase 2 Definition of Ready.'),
            dict(rec=recommendations[1], owner=self.elena, related=lesson_security,
                 status='in_progress', progress=60,
                 target_completion_date=(self.NOW + timedelta(days=10)).date()),
            dict(rec=recommendations[2], owner=self.elena, related=lesson_docker,
                 status='completed', progress=100,
                 actual_completion_date=(self.NOW - timedelta(days=18)).date(),
                 actual_impact='Docker onboarding guide published in the Engineering wiki.'),
            dict(rec=recommendations[3], owner=self.priya, related=lesson_estimation,
                 status='pending', progress=0,
                 target_completion_date=(self.NOW + timedelta(days=14)).date()),
            dict(rec=recommendations[4], owner=self.marcus, related=lesson_estimation,
                 status='in_progress', progress=30,
                 target_completion_date=(self.NOW + timedelta(days=20)).date()),
        ]
        for spec in action_specs:
            rec = spec['rec']
            RetrospectiveActionItem.objects.create(
                retrospective=retrospective, board=self.board,
                title=rec['title'], description=rec['description'],
                action_type=rec['action_type'], priority=rec['priority'],
                expected_impact=rec['expected_impact'],
                status=spec['status'], progress_percentage=spec['progress'],
                assigned_to=spec['owner'], related_lesson=spec['related'],
                target_completion_date=spec.get('target_completion_date'),
                actual_completion_date=spec.get('actual_completion_date'),
                actual_impact=spec.get('actual_impact', ''),
                ai_suggested=True, ai_confidence=Decimal('0.82'),
            )

        # --- Improvement Metrics (relational records the dashboard charts read) ---
        metric_specs = [
            ('velocity', 'Team Velocity', Decimal('8'), 'tasks', True),
            ('quality', 'Completion Rate', Decimal('100'), 'percentage', True),
            ('cycle_time', 'Average Completion Time', Decimal('8.5'), 'days', False),
        ]
        for mtype, mname, value, unit, higher_better in metric_specs:
            ImprovementMetric.objects.create(
                board=self.board, retrospective=retrospective,
                metric_type=mtype, metric_name=mname, metric_value=value,
                unit_of_measure=unit, higher_is_better=higher_better,
                measured_at=retrospective.period_end,
            )

        self.stdout.write(
            '  [OK] Phase 1 retrospective created '
            '(4 lessons, 5 action items, 3 improvement metrics)'
        )

    # ------------------------------------------------------------------
    # Chat rooms
    # ------------------------------------------------------------------
    def _create_chat_rooms(self):
        rooms = [
            ('#general', 'General team chat and announcements'),
            ('#engineering', 'Technical discussion, PR reviews, debugging'),
            ('#sprint-planning', 'Sprint goals, assignments, blockers'),
        ]
        msg_total = 0
        for name, desc in rooms:
            room, _ = ChatRoom.objects.get_or_create(
                board=self.board, name=name,
                defaults={'description': desc, 'created_by': self.priya},
            )
            room.members.add(self.priya, self.marcus, self.elena)
            msg_total += self._seed_messages(room, name)
        self.stdout.write(f'  [OK] Created 3 chat rooms with {msg_total} messages')

    def _seed_messages(self, room, name):
        if name == '#general':
            msgs = [
                (self.priya, 'Phase 1 retrospective is up in the Retros tab - please give it a read before standup tomorrow.', 9),
                (self.elena, 'Onboarding doc update merged. New devs should be productive in <30 min now.', 7),
                (self.marcus, 'Reminder: we are freezing scope changes until after the Phase 2 milestone.', 5),
                (self.priya, 'Stakeholder demo on Friday. Authentication and File Upload need to be demo-ready.', 3),
                (self.marcus, 'On it. R1 is in review, R2 is 88% complete.', 2),
                (self.elena, 'I will run a full smoke test on Thursday afternoon so we can fix anything that breaks.', 1),
            ]
        elif name == '#engineering':
            msgs = [
                (self.priya, 'The circular FK reference in the migration is driving me crazy. Going with a nullable field and a data migration to populate it post-hoc. Not ideal but it unblocks P2.', 4),
                (self.marcus, 'Pushed the R1 PR. The token rotation logic is mostly cribbed from the django-rest-knox docs.', 3),
                (self.elena, 'CI build is flaky on the auth test - same lockout test failing intermittently. Looking now.', 3),
                (self.priya, 'GitHub OAuth scope behaviour: confirmed undocumented. Filed a bug upstream but we need to work around it for P3.', 1),
                (self.marcus, 'Cool - I can pair on the workaround later today.', 1),
                (self.elena, 'CI fixed - the lockout test was racy. Bumped the timeout by 100ms.', 0),
            ]
        else:  # sprint-planning
            msgs = [
                (self.priya, 'Sprint goal for the week: get R1 merged, unblock P1, ship one OAuth provider end-to-end.', 6),
                (self.marcus, 'Capacity check: I am full. Can someone take Slack/Teams webhooks (B3)?', 5),
                (self.priya, 'It is in the backlog, no rush. Focus on P1 and finish R2.', 5),
                (self.elena, 'I will keep P4 moving in parallel with the smoke test prep.', 4),
                (self.priya, 'P3 is overdue. Marcus - can you pair with Priya on the GitHub OAuth scope issue?', 0),
                (self.marcus, 'Yes. Will block out the afternoon.', 0),
            ]

        n = 0
        for author, content, days_ago in msgs:
            m = ChatMessage.objects.create(chat_room=room, author=author, content=content)
            ChatMessage.objects.filter(pk=m.pk).update(
                created_at=self.NOW - timedelta(days=days_ago, hours=random.randint(0, 9)),
            )
            n += 1
        return n

    # ------------------------------------------------------------------
    # Coaching suggestions
    # ------------------------------------------------------------------
    def _create_coaching_suggestions(self, tasks_by_code):
        items = [
            dict(
                suggestion_type='resource_overload', severity='critical', status='active',
                title='Priya Sharma is critically overloaded — 3 overdue tasks',
                message=('Priya is the assignee on three overdue tasks simultaneously: '
                         'Social Login Integration (P3, 45%, 8 days past due), '
                         'Database Schema & Migrations (P2, 55%, 3 days past due), and '
                         'Authentication System (R1, 90%, 4 days past due in code review). '
                         'Immediate redistribution is recommended to unblock the phase milestone.'),
                recommended_actions=[
                    {'action': 'Reassign Social Login Integration (P3) to Marcus Chen'},
                    {'action': 'Pair Marcus with Priya on the GitHub OAuth scope workaround'},
                    {'action': 'Ask Elena to take the R1 code review to free up Priya'},
                ],
                task=tasks_by_code['P3'], days_ago=4,
            ),
            dict(
                suggestion_type='deadline_risk', severity='critical', status='active',
                title='Core Authentication Ready milestone at risk',
                message=('The "Core Authentication Ready" milestone is at risk because Social '
                         'Login Integration (P3) is overdue and User Registration Flow (P1) '
                         'depends on R1 (Authentication System) being merged.'),
                recommended_actions=[
                    {'action': 'Run a daily 15-min standup focused on P3 unblocking'},
                    {'action': 'Prioritise R1 code review (Marcus has the open PR)'},
                ],
                task=tasks_by_code['R1'], days_ago=3,
            ),
            dict(
                suggestion_type='scope_creep', severity='medium', status='acknowledged',
                title='Scope creep detected',
                message=('Two tasks were added after the baseline was set. Original scope was '
                         '26 tasks; current scope is 28 tasks (7.7% increase). Review timeline '
                         'impact.'),
                recommended_actions=[
                    {'action': 'Review whether the 2 new tasks are scope or scope-creep'},
                    {'action': 'Update Phase 4 timeline estimate if needed'},
                ],
                task=None, days_ago=5,
            ),
            dict(
                suggestion_type='best_practice', severity='low', status='acknowledged',
                title='Mid-Phase retrospective recommended',
                message=('Phase 2 work is ~60% complete but no mid-sprint retrospective is '
                         'scheduled. A 45-minute checkpoint now will catch issues before they '
                         'compound.'),
                recommended_actions=[
                    {'action': 'Schedule a 45-minute Phase 2 mid-sprint retrospective'},
                ],
                task=None, days_ago=4,
            ),
        ]
        for it in items:
            days_ago = it.pop('days_ago')
            ack_user = self.priya if it['status'] == 'acknowledged' else None
            ack_at = self.NOW - timedelta(days=days_ago - 1) if ack_user else None
            cs = CoachingSuggestion.objects.create(
                board=self.board,
                acknowledged_by=ack_user,
                acknowledged_at=ack_at,
                generation_method='hybrid',
                ai_model_used='gemini-2.5-flash',
                confidence_score=Decimal('0.82'),
                **it,
            )
            CoachingSuggestion.objects.filter(pk=cs.pk).update(
                created_at=self.NOW - timedelta(days=days_ago),
            )
        self.stdout.write('  [OK] 4 coaching suggestions created')

    # ------------------------------------------------------------------
    # Historical ML training data
    # ------------------------------------------------------------------
    def _create_historical_tasks_for_ml(self):
        """Create 25 completed tasks on a hidden archive board for ML predictions.

        These never appear on the Software Development board (separate board,
        is_archived=True). The ML prediction service queries
        column__board__organization=demo_org, so they still feed predictions.
        """
        archive, created = Board.objects.get_or_create(
            name=ARCHIVE_BOARD_NAME,
            organization=self.demo_org,
            defaults={
                'description': 'Hidden archive of historical completed tasks used only as ML training data. Not user-facing.',
                'is_official_demo_board': False,
                'is_seed_demo_data': True,
                'is_archived': True,
                'created_by': self.priya,
                'owner': self.priya,
            },
        )
        # Ensure flags stay correct on re-runs
        archive.is_archived = True
        archive.is_seed_demo_data = True
        archive.save(update_fields=['is_archived', 'is_seed_demo_data'])

        done, _ = Column.objects.get_or_create(
            board=archive, name='Archive', defaults={'position': 0},
        )

        rng = random.Random(42)  # deterministic so re-runs are stable
        # Include fourth_member (testuser1 when present) so history is spread
        # across all demo workspace members, giving the AI enough per-user
        # velocity and reliability data to generate reassignment suggestions.
        task_templates = [
            'Refactor user notification queue', 'Migrate legacy logging to structured JSON',
            'Add audit trail for permission changes', 'Improve search relevance scoring',
            'Fix flaky integration test for OAuth callback', 'Optimize dashboard query performance',
            'Add CSV export to time tracking', 'Build admin tool for stuck task recovery',
            'Implement project archiving flow', 'Add bulk task assignment endpoint',
            'Migrate cron jobs to Celery beat', 'Add health check for Redis connection',
            'Implement webhook retry with exponential backoff', 'Add SSO debug logging',
            'Build feature flag admin UI', 'Cache board summary on the dashboard',
            'Improve error messages for failed file uploads', 'Add task age tracking',
            'Implement seat-based licence enforcement', 'Add billing event audit log',
            'Build daily digest email job', 'Implement throttling for bulk operations',
            'Add concurrency tests for board permissions', 'Add export to PDF for retrospectives',
            'Implement password breach check on signup',
        ]
        priorities = ['low', 'medium', 'high', 'urgent']
        assignees = [self.priya, self.marcus, self.elena, self.fourth_member]

        for i, title in enumerate(task_templates):
            complexity = rng.randint(2, 9)
            duration_days = max(1.0, complexity * 1.5 * rng.uniform(0.7, 1.3))
            completed_offset = rng.randint(60, 180)
            start_offset = -int(completed_offset + duration_days)
            assignee = rng.choice(assignees)
            priority = rng.choices(priorities, weights=[1, 3, 3, 1])[0]

            Task.objects.create(
                title=title,
                description=f'Historical reference task #{i+1}. Used for ML prediction training.',
                column=done,
                phase=None,
                item_type='task',
                priority=priority,
                start_date=self.TODAY + timedelta(days=start_offset),
                due_date=_aware_due(self.TODAY + timedelta(days=start_offset + int(duration_days))),
                progress=100,
                complexity_score=complexity,
                completed_at=self._days_ago(completed_offset),
                actual_duration_days=duration_days,
                assigned_to=assignee,
                created_by=self.priya,
                is_seed_demo_data=True,
            )
        self.stdout.write('  [OK] 25 historical ML training tasks created (archive board)')

    # ------------------------------------------------------------------
    # Priority decisions
    # ------------------------------------------------------------------
    def _create_priority_decisions(self, tasks_by_code):
        rng = random.Random(7)
        all_tasks = list(tasks_by_code.values())
        priorities = ['low', 'medium', 'high', 'urgent']
        for i in range(30):
            task = rng.choice(all_tasks)
            accepted = rng.random() < 0.7
            suggested = rng.choice(priorities)
            actual = suggested if accepted else rng.choice(
                [p for p in priorities if p != suggested]
            )
            pd = PriorityDecision.objects.create(
                task=task, board=self.board,
                suggested_priority=suggested, actual_priority=actual,
                previous_priority=None,
                decision_type='ai_accepted' if accepted else 'ai_rejected',
                decided_by=rng.choice([self.priya, self.marcus, self.elena]),
                confidence_score=round(rng.uniform(0.55, 0.95), 2),
                was_correct=accepted,
            )
            PriorityDecision.objects.filter(pk=pd.pk).update(
                decided_at=self.NOW - timedelta(days=rng.randint(1, 90)),
            )
        self.stdout.write('  [OK] 30 priority decisions created')

    # ------------------------------------------------------------------
    # Wiki pages
    # ------------------------------------------------------------------
    def _create_wiki_pages(self):
        cat, _ = WikiCategory.objects.get_or_create(
            name='Engineering',
            organization=self.demo_org,
            defaults={
                'description': 'Engineering reference pages and standards.',
                'icon': 'code', 'color': '#6366f1', 'position': 1,
                'ai_assistant_type': 'documentation',
            },
        )

        pages = [
            ('API Design Standards', (
                "# API Design Standards\n\n"
                "All public endpoints live under `/api/v1/`. Versioning is path-based; "
                "breaking changes go to `/api/v2/` rather than mutating an existing endpoint.\n\n"
                "## Naming\n\n"
                "- Resources are plural nouns: `/tasks/`, `/boards/`, not `/getTask/`.\n"
                "- Sub-resources nest when ownership is hard (`/boards/{id}/columns/`).\n"
                "- Filters live in query params; never encode them into the path.\n\n"
                "## Response envelope\n\n"
                "Every successful response wraps the payload in `{data, meta}`. The "
                "`meta` block carries pagination cursors, request IDs, and timing. Errors "
                "return `{error: {code, message, details}}` with an HTTP status that matches.\n\n"
                "## Pagination\n\n"
                "Cursor-based by default. Page-based pagination is allowed only on "
                "endpoints that can guarantee a stable ordering.\n\n"
                "## Authentication\n\n"
                "Token authentication via the `Authorization: Bearer <token>` header. "
                "Tokens are short-lived (15 minutes) and refreshed via `/auth/refresh/`.\n"
            )),
            ('Security Guidelines', (
                "# Security Guidelines\n\n"
                "Security is non-negotiable. Every PR that touches authentication, "
                "permissions, file handling, or external integrations requires explicit "
                "sign-off from a second reviewer.\n\n"
                "## Auth patterns\n\n"
                "- All views use the `@permission_required` decorator with a "
                "django-rules predicate; no ad-hoc permission checks.\n"
                "- Session expiry: 60 minutes idle, 8 hours absolute.\n"
                "- Brute-force protection via django-axes (5 attempts, exponential backoff).\n\n"
                "## Secret management\n\n"
                "Secrets live in Google Secret Manager - never in source. Local dev uses "
                "`.env.local` (gitignored). Rotate every 90 days.\n\n"
                "## Vulnerability reporting\n\n"
                "Email `security@acme-corp.demo`. We acknowledge within 24 hours and "
                "patch critical issues within 7 days.\n\n"
                "## Required scans on every release\n\n"
                "- Dependency scan (pip-audit + npm audit)\n"
                "- OWASP ZAP baseline scan\n"
                "- SAST via Semgrep\n"
            )),
            ('Sprint Process & Definition of Done', (
                "# Sprint Process & Definition of Done\n\n"
                "We run two-week sprints. Ceremonies are kept short: 30-minute planning, "
                "15-minute daily standup, 45-minute retro at the end.\n\n"
                "## Definition of Done\n\n"
                "A task is Done only when ALL of the following are true:\n\n"
                "1. Code merged to `main` via PR with at least one review approval.\n"
                "2. Unit tests written and passing in CI.\n"
                "3. Integration tests cover the happy path and one error path.\n"
                "4. No new linter warnings; code coverage on the module is ≥ 80%.\n"
                "5. Documentation updated (README, ADRs, or wiki as appropriate).\n"
                "6. The PR description includes a manual test plan a reviewer can follow.\n\n"
                "## Velocity tracking\n\n"
                "We track velocity in completed-tasks per sprint, not story points. "
                "Trends matter more than absolute numbers - a sudden 30% drop is a flag "
                "for a retro conversation.\n\n"
                "## Sprint planning\n\n"
                "Each sprint starts with one over-arching goal. Tasks that do not "
                "contribute to the goal are deferred to the backlog unless they are "
                "blocking production issues.\n"
            )),
        ]
        for title, content in pages:
            WikiPage.objects.get_or_create(
                title=title, category=cat, organization=self.demo_org,
                defaults={
                    'content': content,
                    'created_by': self.priya, 'updated_by': self.priya,
                    'is_published': True,
                    'tags': ['engineering', 'standards'],
                },
            )
        self.stdout.write('  [OK] Wiki: 1 category + 3 pages created')

    # ------------------------------------------------------------------
    # Custom fields
    # ------------------------------------------------------------------
    def _create_custom_fields(self):
        """Seed custom field definitions and sample values for the demo workspace.

        Idempotent: uses get_or_create throughout so re-running is safe.
        """
        try:
            workspace = self.board.workspace
        except Workspace.DoesNotExist:
            workspace = None
        if workspace is None:
            workspace = Workspace.objects.filter(
                organization=self.demo_org, is_demo=True
            ).first()
            if workspace is not None:
                # Self-heal: repoint board to the real workspace
                self.board.workspace = workspace
                self.board.save(update_fields=['workspace'])
        if workspace is None:
            self.stdout.write(self.style.WARNING(
                '  [WARN] Custom fields: no demo workspace found — skipping.'
            ))
            return

        # ── Field definitions ─────────────────────────────────────────────
        sprint_field, _ = CustomFieldDefinition.objects.get_or_create(
            workspace=workspace, name='Sprint', is_active=True,
            defaults={
                'field_type': 'list',
                'is_required': False,
                'is_multi_select': False,
                'applies_to_tasks': True,
                'position': 1,
            },
        )
        sprint_opts = {}
        for pos, label in enumerate(
            ['Sprint 1', 'Sprint 2', 'Sprint 3', 'Sprint 4 (Current)'], start=1
        ):
            opt, _ = CustomFieldOption.objects.get_or_create(
                field=sprint_field, value=label,
                defaults={'position': pos, 'is_default': label == 'Sprint 4 (Current)'},
            )
            sprint_opts[label] = opt

        story_points_field, _ = CustomFieldDefinition.objects.get_or_create(
            workspace=workspace, name='Story Points', is_active=True,
            defaults={
                'field_type': 'integer',
                'is_required': False,
                'applies_to_tasks': True,
                'position': 2,
            },
        )

        env_field, _ = CustomFieldDefinition.objects.get_or_create(
            workspace=workspace, name='Environment', is_active=True,
            defaults={
                'field_type': 'list',
                'is_required': False,
                'is_multi_select': True,
                'applies_to_tasks': True,
                'position': 3,
            },
        )
        env_opts = {}
        for pos, label in enumerate(['Development', 'Staging', 'Production'], start=1):
            opt, _ = CustomFieldOption.objects.get_or_create(
                field=env_field, value=label,
                defaults={'position': pos, 'is_default': False},
            )
            env_opts[label] = opt

        category_field, _ = CustomFieldDefinition.objects.get_or_create(
            workspace=workspace, name='Feature Category', is_active=True,
            defaults={
                'field_type': 'list',
                'is_required': False,
                'is_multi_select': False,
                'applies_to_tasks': True,
                'position': 4,
            },
        )
        cat_opts = {}
        for pos, label in enumerate(
            ['Backend', 'Frontend', 'DevOps', 'QA', 'Documentation'], start=1
        ):
            opt, _ = CustomFieldOption.objects.get_or_create(
                field=category_field, value=label,
                defaults={'position': pos, 'is_default': False},
            )
            cat_opts[label] = opt

        # ── Task values ───────────────────────────────────────────────────
        # Map task title fragments → (sprint_label, story_pts, env_labels, category)
        task_data = {
            'Requirements Analysis':      ('Sprint 1', 3,  ['Development'],             'Documentation'),
            'System Architecture':        ('Sprint 1', 8,  ['Development'],             'Backend'),
            'CI/CD Pipeline':             ('Sprint 1', 5,  ['Development', 'Staging'],  'DevOps'),
            'Development Environment':    ('Sprint 1', 3,  ['Development'],             'DevOps'),
            'Database Schema':            ('Sprint 2', 8,  ['Development'],             'Backend'),
            'User Registration':          ('Sprint 2', 5,  ['Development', 'Staging'],  'Backend'),
            'OAuth Integration':          ('Sprint 2', 8,  ['Development', 'Staging'],  'Backend'),
            'JWT Token':                  ('Sprint 2', 5,  ['Development'],             'Backend'),
            'Role-Based Access':          ('Sprint 2', 8,  ['Development'],             'Backend'),
            'REST API':                   ('Sprint 3', 13, ['Development', 'Staging'],  'Backend'),
            'Unit Test Suite':            ('Sprint 3', 5,  ['Development'],             'QA'),
            'Integration Test':           ('Sprint 3', 8,  ['Staging'],                 'QA'),
            'Performance Optimisation':   ('Sprint 4 (Current)', 8,  ['Staging'],        'Backend'),
            'Social Login Integration':   ('Sprint 4 (Current)', 8,  ['Development'],   'Backend'),
            'Email Notification':         ('Sprint 4 (Current)', 5,  ['Development'],   'Backend'),
            'Push Notification':          ('Sprint 4 (Current)', 5,  ['Development'],   'Backend'),
            'Real-Time Dashboard':        ('Sprint 4 (Current)', 8,  ['Frontend'],       'Frontend'),
            'Webhook':                    ('Sprint 4 (Current)', 5,  ['Staging'],        'Backend'),
            'Mobile-Responsive':          ('Sprint 4 (Current)', 8,  ['Frontend'],       'Frontend'),
            'Accessibility':              ('Sprint 4 (Current)', 5,  ['Frontend'],       'Frontend'),
            'API Documentation':          ('Sprint 4 (Current)', 3,  ['Production'],     'Documentation'),
            'Security Audit':             ('Sprint 4 (Current)', 8,  ['Staging', 'Production'], 'QA'),
            'Load Testing':               ('Sprint 4 (Current)', 5,  ['Staging'],        'QA'),
            'Deployment Pipeline':        ('Sprint 4 (Current)', 8,  ['Staging', 'Production'], 'DevOps'),
            'Monitoring & Alerting':      ('Sprint 4 (Current)', 5,  ['Production'],     'DevOps'),
            'Feature Flag':               ('Sprint 4 (Current)', 3,  ['Development'],   'DevOps'),
            'User Onboarding Flow':       ('Sprint 4 (Current)', 8,  ['Frontend'],       'Frontend'),
            'Analytics Integration':      ('Sprint 4 (Current)', 5,  ['Staging'],        'Backend'),
        }

        tasks = Task.objects.filter(
            column__board=self.board,
            item_type='task',
            is_seed_demo_data=True,
        )

        updated = 0
        for task in tasks:
            matched_key = next(
                (k for k in task_data if k.lower() in task.title.lower()), None
            )
            if matched_key is None:
                continue
            sprint_label, pts, envs, category = task_data[matched_key]

            # Sprint
            sprint_val, _ = TaskCustomFieldValue.objects.get_or_create(
                task=task, field=sprint_field,
            )
            sprint_val.selected_options.set([sprint_opts[sprint_label]])

            # Story Points
            pts_val, _ = TaskCustomFieldValue.objects.get_or_create(
                task=task, field=story_points_field,
            )
            from decimal import Decimal as D
            pts_val.value_number = D(pts)
            pts_val.save(update_fields=['value_number', 'updated_at'])

            # Environment (multi-select)
            env_val, _ = TaskCustomFieldValue.objects.get_or_create(
                task=task, field=env_field,
            )
            env_val.selected_options.set(
                [env_opts[e] for e in envs if e in env_opts]
            )

            # Feature Category
            cat_val, _ = TaskCustomFieldValue.objects.get_or_create(
                task=task, field=category_field,
            )
            if category in cat_opts:
                cat_val.selected_options.set([cat_opts[category]])

            updated += 1

        self.stdout.write(
            f'  [OK] Custom fields: 4 definitions + values on {updated} tasks'
        )

    # ------------------------------------------------------------------
    # Velocity snapshots
    # ------------------------------------------------------------------
    def _create_velocity_snapshots(self):
        """Seed TeamVelocitySnapshot records by running the predictor's snapshot
        builder against the just-created tasks.  This ensures the Velocity History
        chart shows a realistic spread of bars immediately after demo reset instead
        of waiting for the first burndown page visit."""
        try:
            from kanban.utils.burndown_predictor import BurndownPredictor
            predictor = BurndownPredictor()
            predictor._ensure_velocity_snapshots(self.board)
            self.stdout.write('  [OK] Velocity snapshots seeded')
        except Exception as e:
            self.stdout.write(self.style.WARNING(f'  [WARN] Could not seed velocity snapshots: {e}'))

    # ------------------------------------------------------------------
    # Optional sub-seeders
    # ------------------------------------------------------------------
    def _call_optional_subseeders(self):
        """Best-effort calls to feature-specific sub-seeders. Failures are non-fatal."""
        subs = [
            'populate_commitment_demo_data',
            'populate_knowledge_demo_data',
            'populate_discovery_demo_data',
            'populate_automation_demo_data',
        ]
        for name in subs:
            try:
                call_command(name)
                self.stdout.write(f'  [OK] {name}')
            except Exception as e:
                self.stdout.write(self.style.WARNING(f'  [WARN] {name} skipped: {e}'))

        # NOTE: do NOT call refresh_demo_dates here - our seed already writes
        # dynamic dates relative to TODAY, and the refresh command resets
        # progress/checklists/dates in a way that wipes the carefully-tuned
        # narrative (intentional overdue task, mid-progress states, etc.).

        try:
            call_command('detect_conflicts', '--clear')
            self.stdout.write('  [OK] detect_conflicts')
        except Exception as e:
            self.stdout.write(self.style.WARNING(f'  [WARN] detect_conflicts skipped: {e}'))

    # ------------------------------------------------------------------
    # Verification
    # ------------------------------------------------------------------
    def _print_verification_report(self):
        b = self.board
        tasks = Task.objects.filter(column__board=b)
        children = tasks.exclude(item_type='milestone').exclude(item_type='epic')

        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS('=' * 80))
        self.stdout.write(self.style.SUCCESS('DEMO DATA VERIFICATION REPORT'))
        self.stdout.write(self.style.SUCCESS('=' * 80))
        self.stdout.write(f'Board: {b.name}')
        self.stdout.write(f'Total task rows: {tasks.count()}  (expected: 35 - 4 epics + 28 tasks + 3 milestones)')
        for c in b.columns.all().order_by('position'):
            self.stdout.write(
                f'  {c.name:<14} {tasks.filter(column=c).count():>3}'
                f'   (children only: {children.filter(column=c).count()})'
            )

        overdue = children.filter(due_date__lt=self.NOW, progress__lt=100)
        self.stdout.write(
            f'Overdue tasks: {overdue.count()}  '
            '(expected: 3 - Social Login Integration P3 + '
            'Authentication System R1 in review + Database Schema P2 slightly overdue)'
        )

        dep_count = sum(t.dependencies.count() for t in children)
        self.stdout.write(f'Total dependency links: {dep_count}  (expected: 21)')

        for username in PERSONA_USERNAMES:
            ok = User.objects.filter(username=username).exists()
            self.stdout.write(f'  Persona {username}: {"[OK]" if ok else "[FAIL] MISSING"}')

        archive = Board.objects.filter(
            name=ARCHIVE_BOARD_NAME, organization=self.demo_org,
        ).first()
        if archive:
            hist = Task.objects.filter(column__board=archive).count()
            self.stdout.write(f'Historical ML tasks: {hist}  (expected: 25, on hidden archive board)')

        self.stdout.write('')
        self.stdout.write(f' All dates relative to TODAY = {self.TODAY}')
        self.stdout.write(' Re-run anytime to slide the project forward.')
        self.stdout.write(self.style.SUCCESS('=' * 80))
