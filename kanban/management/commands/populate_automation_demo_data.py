"""
Management command to seed Automation Hierarchy demo data.
===========================================================
Adds the data needed to test the "Hierarchy & Dependencies" automation
triggers (T-22 through T-29) described in the Spectra test plan:

  - Checklist items on every existing demo task (2–4 per task)
  - 4 parent tasks, each with 2–3 subtasks (for subtask triggers)
  - 1 dedicated blocking-dependency pair with Task B pre-seeded as overdue

Usage:
    python manage.py populate_automation_demo_data
    python manage.py populate_automation_demo_data --reset
"""
from django.core.management.base import BaseCommand
from django.utils import timezone
from django.db import transaction
from datetime import timedelta, datetime, time


CHECKLIST_MAP = {
    # ── Sprint 0 ───────────────────────────────────────────────────────────────
    'Project Kickoff & Team Onboarding': [
        'Confirm team roles and responsibilities',
        'Share project charter with all stakeholders',
        'Schedule recurring standups and retrospectives',
    ],
    'Stakeholder Communication Plan': [
        'Identify all stakeholders and communication preferences',
        'Define escalation path and RACI matrix',
        'Schedule first stakeholder status meeting',
    ],
    'Initial Risk Register': [
        'Identify top 5 project risks',
        'Assign risk owner to each item',
        'Define mitigation strategy per risk',
    ],
    'Development Toolchain Configuration': [
        'Install and verify all IDE plugins',
        'Configure linter and formatter rules',
        'Test CI pipeline with a sample commit',
    ],
    'Code Style & Contribution Guidelines': [
        'Draft CONTRIBUTING.md with PR review checklist',
        'Define branch naming convention',
        'Review and get team sign-off',
    ],
    'Sprint 1 Planning Session': [
        'Prioritise backlog for Sprint 1',
        'Confirm team capacity and velocity estimate',
        'Agree on Definition of Done',
    ],
    # ── Phase 1 ───────────────────────────────────────────────────────────────
    'Requirements Analysis & Planning': [
        'Conduct stakeholder interviews',
        'Document functional and non-functional requirements',
        'Get sign-off on project scope',
    ],
    'Development Environment Setup': [
        'Configure Docker containers and docker-compose',
        'Set up CI/CD pipeline triggers',
        'Verify all developers can run the app locally',
    ],
    'System Architecture Design': [
        'Draft component diagram and service boundaries',
        'Define API contract between services',
        'Review with senior engineer',
    ],
    'Security Architecture Patterns': [
        'Define encryption standards for data at rest and in transit',
        'Document access control model (RBAC/ABAC)',
        'Review design against OWASP Top 10',
    ],
    'Base API Structure': [
        'Set up REST framework with versioning (v1)',
        'Auto-generate Swagger/OpenAPI docs from serialiser',
        'Add health check endpoint',
    ],
    'Authentication System': [
        'Implement JWT access and refresh token rotation',
        'Add rate limiting on login endpoint (5 attempts/min)',
        'Test CSRF and session fixation scenarios',
    ],
    'User Registration Flow': [
        'Add email verification with single-use link',
        'Implement input sanitisation on signup form',
        'Test onboarding resumption after tab close',
    ],
    'Database Schema & Migrations': [
        'Normalise schema to 3NF',
        'Add composite indexes for high-traffic queries',
        'Write rollback migration for every forward migration',
    ],
    'Authentication Testing Suite': [
        'Write unit tests for token generation and expiry',
        'Add integration tests for OAuth flows',
        'Achieve >90% coverage on auth module',
    ],
    'Project Documentation Setup': [
        'Set up documentation framework (MkDocs/Docusaurus)',
        'Write Getting Started guide',
        'Add API reference index page',
    ],
    # ── Phase 2 ───────────────────────────────────────────────────────────────
    'Dashboard UI Development': [
        'Implement skeleton loaders for all data panels',
        'Add lazy loading for analytics chart',
        'Verify all widgets are responsive on mobile',
    ],
    'File Upload System': [
        'Implement presigned S3 URL upload flow',
        'Add virus scan via ClamAV on upload',
        'Enforce 50 MB size limit and file type whitelist',
    ],
    'Notification Service': [
        'Fan out WebSocket messages to per-user channel groups',
        'Implement email digest batching (every 4 hours)',
        'Add unsubscribe one-click link',
    ],
    'User Management API': [
        'Implement CRUD endpoints with RBAC',
        'Add cursor-based pagination',
        'Write OpenAPI spec for all endpoints',
    ],
    'Search & Indexing Engine': [
        'Set up Elasticsearch index with edge-ngram analyser',
        'Add faceted filtering by label, assignee, and date range',
        'Benchmark p95 response time under 50 ms',
    ],
    'Real-time Collaboration': [
        'Implement Operational Transform for concurrent edits',
        'Add user presence indicators (heartbeat every 30 s)',
        'Test conflict resolution under simulated network latency',
    ],
    'Data Caching Layer': [
        'Set up Redis cache with appropriate TTLs',
        'Cache the top 10 most expensive queries',
        'Write cache invalidation logic on task update',
    ],
    'API Rate Limiting': [
        'Write custom throttle class (100 req/min auth, 20 anon)',
        'Log rate-limit hits to monitoring dashboard',
        'Load-test endpoint behaviour at limit boundary',
    ],
    'Integration Testing Suite': [
        'Cover all happy-path API flows end-to-end',
        'Add test for each error response code',
        'Confirm suite runs green in CI on every PR',
    ],
    'Core Features Code Review': [
        'Review authentication and data-access layers',
        'Check all SQL queries for injection risk',
        'Sign off on code coverage report',
    ],
    # ── Phase 3 ───────────────────────────────────────────────────────────────
    'Performance Optimization': [
        'Profile and fix top 5 slow database queries',
        'Reduce API p95 latency to under 200 ms',
        'Add database connection pooling',
    ],
    'Security Audit & Fixes': [
        'Run automated SAST scan and fix critical findings',
        'Conduct manual pen test on auth flows',
        'Verify all third-party dependencies are up to date',
    ],
    'UI/UX Polish': [
        'Apply design system tokens consistently across all pages',
        'Fix all mobile viewport layout issues',
        'Pass Lighthouse accessibility audit (score ≥ 90)',
    ],
    'Load Testing & Optimization': [
        'Define target load (e.g. 500 concurrent users)',
        'Run load test scenarios with k6 or Locust',
        'Fix bottlenecks found under peak load',
    ],
    'User Onboarding Flow': [
        'Implement step-by-step interactive tutorial',
        'Add skip and resume functionality',
        'Test onboarding completion rate with 5 internal users',
    ],
    'Error Tracking & Monitoring': [
        'Configure Sentry with environment tags',
        'Set up APM dashboard for p95 latency',
        'Create alerting rules for error rate spike',
    ],
    'Accessibility Compliance': [
        'Run axe-core scan on all pages',
        'Fix all WCAG 2.1 AA failures',
        'Get sign-off from QA on keyboard navigation',
    ],
    'Final Documentation': [
        'Complete API reference with all endpoints',
        'Write user guide with screenshots',
        'Publish final docs to documentation site',
    ],
    'Deployment Automation': [
        'Set up one-click deployment pipeline',
        'Implement automated smoke tests post-deploy',
        'Document rollback procedure',
    ],
    'Launch & Go-Live': [
        'Run full regression test suite',
        'Verify security headers (HSTS, CSP, X-Frame-Options)',
        'Confirm DNS cutover and SSL certificate validity',
    ],
    # ── New parent tasks ───────────────────────────────────────────────────────
    'Social Login Integration': [
        'Register OAuth apps on Google and GitHub developer consoles',
        'Implement PKCE flow for both providers',
        'Test token exchange and user profile retrieval',
    ],
    'Google OAuth 2.0 Integration': [
        'Configure Google OAuth 2.0 credentials in developer console',
        'Implement PKCE authorisation flow',
        'Map Google profile fields to internal user model',
    ],
    'GitHub OAuth 2.0 Integration': [
        'Register GitHub OAuth app and obtain client credentials',
        'Implement GitHub authorisation callback handler',
        'Map GitHub profile fields to internal user model',
    ],
    'Mobile Push Notifications': [
        'Register app on Apple Developer and Google Firebase consoles',
        'Implement device token registration endpoint',
        'Test push delivery on physical devices',
    ],
    'iOS APNs Integration': [
        'Configure APNs certificates and keys',
        'Implement device token registration on app launch',
        'Trim push payload to under 4 KB APNs limit',
    ],
    'Android FCM Integration': [
        'Configure Firebase project and google-services.json',
        'Implement FCM token registration on app launch',
        'Test notification delivery with Firebase console',
    ],
    'Analytics Data Pipeline': [
        'Define event schema and data contracts',
        'Set up ingestion queue (Kafka or SQS)',
        'End-to-end test from event emission to dashboard display',
    ],
    'Event Collection Service': [
        'Implement client-side event emitter SDK',
        'Set up server-side event ingestion endpoint',
        'Validate event schema on ingestion',
    ],
    'Aggregation & Reporting Engine': [
        'Define aggregation windows (hourly, daily, weekly)',
        'Implement batch aggregation job',
        'Unit test edge cases (empty window, timezone boundaries)',
    ],
    'Dashboard Metrics Integration': [
        'Wire aggregated metrics to dashboard API endpoints',
        'Add real-time metric refresh via WebSocket',
        'Verify chart rendering under large dataset',
    ],
    'Release Quality Gate': [
        'Confirm all automated test suites are green',
        'Obtain security, regression, and UAT sign-offs',
        'Run final smoke test on staging environment',
    ],
    'Automated Regression Suite Sign-off': [
        'Run full regression suite and confirm 0 failures',
        'Review flaky tests and resolve or quarantine',
        'Document final coverage report',
    ],
    'Security Penetration Test Sign-off': [
        'Run internal SAST/DAST scans on staging',
        'Review pen test report and close all critical findings',
        'Get sign-off from Security Officer',
    ],
    'Stakeholder UAT Sign-off': [
        'Prepare UAT test scenarios document',
        'Facilitate UAT session with product stakeholders',
        'Collect formal sign-off and record outcome',
    ],
    # ── Blocking dependency pair ───────────────────────────────────────────────
    'API Gateway Configuration': [
        'Define API contract (OpenAPI spec)',
        'Implement request routing and load-balancing rules',
        'Load-test gateway under 1 k req/s',
    ],
    'End-to-End Integration Tests': [
        'Cover all API endpoints in happy-path tests',
        'Add negative test cases for each endpoint',
        'Run suite in CI and confirm green',
    ],
}


class Command(BaseCommand):
    help = 'Seed automation hierarchy demo data: checklist items, parent/subtask groups, and blocking dependency pair'

    def add_arguments(self, parser):
        parser.add_argument(
            '--reset',
            action='store_true',
            help='Delete existing automation demo data before re-seeding',
        )

    def handle(self, *args, **options):
        from kanban.models import Board, Column, Task, ChecklistItem

        self.stdout.write(self.style.SUCCESS('\n' + '=' * 70))
        self.stdout.write(self.style.SUCCESS('  Populating Automation Hierarchy Demo Data'))
        self.stdout.write(self.style.SUCCESS('=' * 70))

        board = Board.objects.filter(
            name__icontains='software',
            is_official_demo_board=True,
        ).first()
        if not board:
            self.stdout.write(self.style.ERROR('❌ Official demo board not found.'))
            return

        from django.contrib.auth import get_user_model
        User = get_user_model()
        alex = User.objects.filter(username='alex_chen_demo').first()
        sam = User.objects.filter(username='sam_rivera_demo').first()
        jordan = User.objects.filter(username='jordan_taylor_demo').first()
        if not all([alex, sam, jordan]):
            self.stdout.write(self.style.ERROR('❌ Demo users not found.'))
            return

        self.board = board
        self.alex = alex
        self.sam = sam
        self.jordan = jordan
        self.now = timezone.now()
        self.today = self.now.date()

        self.stdout.write(f'  Board : {board.name} (id={board.id})')

        with transaction.atomic():
            if options['reset']:
                self._reset_data()

            checklist_count = self._seed_checklist_items()
            parent_count, subtask_count = self._seed_parent_subtask_groups()
            dep_count = self._seed_blocking_dependency_pair()

        self.stdout.write(self.style.SUCCESS('\n' + '=' * 70))
        self.stdout.write(self.style.SUCCESS('  Summary'))
        self.stdout.write(self.style.SUCCESS('=' * 70))
        self.stdout.write(f'  ✅ Checklist items created : {checklist_count}')
        self.stdout.write(f'  ✅ Parent tasks created    : {parent_count}')
        self.stdout.write(f'  ✅ Subtasks created        : {subtask_count}')
        self.stdout.write(f'  ✅ Dependency tasks added  : {dep_count}')
        self.stdout.write('')

    # ─────────────────────────────────────────────────────────────────────────
    #  Reset
    # ─────────────────────────────────────────────────────────────────────────

    def _reset_data(self):
        from kanban.models import Task, ChecklistItem

        # Remove checklist items on seed tasks
        ChecklistItem.objects.filter(
            task__column__board=self.board,
            task__is_seed_demo_data=True,
        ).delete()

        # Remove the new tasks seeded by this command (identified by title)
        new_task_titles = [
            'Social Login Integration',
            'Google OAuth 2.0 Integration',
            'GitHub OAuth 2.0 Integration',
            'Mobile Push Notifications',
            'iOS APNs Integration',
            'Android FCM Integration',
            'Analytics Data Pipeline',
            'Event Collection Service',
            'Aggregation & Reporting Engine',
            'Dashboard Metrics Integration',
            'Release Quality Gate',
            'Automated Regression Suite Sign-off',
            'Security Penetration Test Sign-off',
            'Stakeholder UAT Sign-off',
            'API Gateway Configuration',
            'End-to-End Integration Tests',
        ]
        Task.objects.filter(
            column__board=self.board,
            title__in=new_task_titles,
        ).delete()

        self.stdout.write('   ✓ Cleared existing automation demo data')

    # ─────────────────────────────────────────────────────────────────────────
    #  1. Checklist items on all existing demo tasks
    # ─────────────────────────────────────────────────────────────────────────

    def _seed_checklist_items(self):
        from kanban.models import Task, ChecklistItem

        self.stdout.write(self.style.NOTICE('\n📋 Seeding checklist items on existing tasks...'))

        # Skip if already seeded (idempotent check)
        already = ChecklistItem.objects.filter(
            task__column__board=self.board,
            task__is_seed_demo_data=True,
        ).count()
        if already > 0:
            self.stdout.write(f'   ⏭️  {already} checklist items already exist, skipping')
            return 0

        tasks_qs = Task.objects.filter(
            column__board=self.board,
            is_seed_demo_data=True,
            parent_task__isnull=True,   # only top-level tasks at this stage
        )

        total = 0
        for task in tasks_qs:
            items = CHECKLIST_MAP.get(task.title)
            if not items:
                continue
            for pos, title in enumerate(items, start=1):
                ChecklistItem.objects.create(
                    task=task,
                    title=title,
                    is_completed=False,
                    position=pos,
                    source='manual',
                )
            total += len(items)

        self.stdout.write(f'   ✅ Created {total} checklist items across existing tasks')
        return total

    # ─────────────────────────────────────────────────────────────────────────
    #  2. Parent task + subtask groups
    # ─────────────────────────────────────────────────────────────────────────

    def _seed_parent_subtask_groups(self):
        from kanban.models import Task, ChecklistItem, Column

        self.stdout.write(self.style.NOTICE('\n🗂️  Seeding parent/subtask groups...'))

        if Task.objects.filter(
            column__board=self.board,
            title='Social Login Integration',
        ).exists():
            self.stdout.write('   ⏭️  Parent/subtask groups already exist, skipping')
            return 0, 0

        columns = {col.name: col for col in Column.objects.filter(board=self.board)}
        todo = (
            columns.get('To Do')
            or columns.get('Backlog')
            or Column.objects.filter(board=self.board).order_by('position').first()
        )
        in_progress = columns.get('In Progress') or todo

        # future due date used for parents (no urgency)
        future_due = timezone.make_aware(
            datetime.combine(self.today + timedelta(days=21), time(12, 0))
        )

        def _make_task(title, column, assignee, priority='medium', phase='Phase 1',
                       progress=0, parent=None, due_date=None):
            return Task.objects.create(
                column=column,
                title=title,
                description=CHECKLIST_MAP.get(title, [''])[0],
                priority=priority,
                assigned_to=assignee,
                created_by=self.alex,
                progress=progress,
                start_date=self.today,
                due_date=due_date or future_due,
                phase=phase,
                parent_task=parent,
                is_seed_demo_data=True,
            )

        def _add_checklist(task):
            items = CHECKLIST_MAP.get(task.title, [])
            for pos, title in enumerate(items, start=1):
                ChecklistItem.objects.create(
                    task=task,
                    title=title,
                    is_completed=False,
                    position=pos,
                    source='manual',
                )

        parent_count = 0
        subtask_count = 0

        # ── Group 1: Social Login Integration (Phase 1) ────────────────────
        p1 = _make_task('Social Login Integration', in_progress, self.sam,
                        priority='high', phase='Phase 1')
        _add_checklist(p1)
        parent_count += 1

        for title, assignee in [
            ('Google OAuth 2.0 Integration', self.alex),
            ('GitHub OAuth 2.0 Integration', self.jordan),
        ]:
            sub = _make_task(title, todo, assignee, phase='Phase 1', parent=p1)
            _add_checklist(sub)
            subtask_count += 1

        # ── Group 2: Mobile Push Notifications (Phase 2) ───────────────────
        p2 = _make_task('Mobile Push Notifications', todo, self.jordan,
                        priority='medium', phase='Phase 2')
        _add_checklist(p2)
        parent_count += 1

        for title, assignee in [
            ('iOS APNs Integration', self.alex),
            ('Android FCM Integration', self.jordan),
        ]:
            sub = _make_task(title, todo, assignee, phase='Phase 2', parent=p2)
            _add_checklist(sub)
            subtask_count += 1

        # ── Group 3: Analytics Data Pipeline (Phase 2) ─────────────────────
        p3 = _make_task('Analytics Data Pipeline', todo, self.sam,
                        priority='high', phase='Phase 2')
        _add_checklist(p3)
        parent_count += 1

        for title, assignee in [
            ('Event Collection Service', self.sam),
            ('Aggregation & Reporting Engine', self.jordan),
            ('Dashboard Metrics Integration', self.alex),
        ]:
            sub = _make_task(title, todo, assignee, phase='Phase 2', parent=p3)
            _add_checklist(sub)
            subtask_count += 1

        # ── Group 4: Release Quality Gate (Phase 3) ────────────────────────
        p4 = _make_task('Release Quality Gate', todo, self.alex,
                        priority='urgent', phase='Phase 3')
        _add_checklist(p4)
        parent_count += 1

        for title, assignee in [
            ('Automated Regression Suite Sign-off', self.jordan),
            ('Security Penetration Test Sign-off', self.sam),
            ('Stakeholder UAT Sign-off', self.alex),
        ]:
            sub = _make_task(title, todo, assignee, phase='Phase 3', parent=p4)
            _add_checklist(sub)
            subtask_count += 1

        self.stdout.write(
            f'   ✅ Created {parent_count} parent tasks with {subtask_count} subtasks'
        )
        return parent_count, subtask_count

    # ─────────────────────────────────────────────────────────────────────────
    #  3. Dedicated blocking dependency pair (T-24 / T-25)
    # ─────────────────────────────────────────────────────────────────────────

    def _seed_blocking_dependency_pair(self):
        from kanban.models import Task, ChecklistItem, Column

        self.stdout.write(self.style.NOTICE('\n🔗 Seeding blocking dependency pair...'))

        if Task.objects.filter(
            column__board=self.board,
            title='API Gateway Configuration',
        ).exists():
            self.stdout.write('   ⏭️  Blocking dependency pair already exists, skipping')
            return 0

        columns = {col.name: col for col in Column.objects.filter(board=self.board)}
        todo = (
            columns.get('To Do')
            or columns.get('Backlog')
            or Column.objects.filter(board=self.board).order_by('position').first()
        )
        in_progress = columns.get('In Progress') or todo

        # Task B — already overdue (due 2 days ago, 40% progress)
        task_b_due = timezone.make_aware(
            datetime.combine(self.today - timedelta(days=2), time(12, 0))
        )
        task_b = Task.objects.create(
            column=in_progress,
            title='API Gateway Configuration',
            description='Define API contract, configure routing rules, and load-test the gateway.',
            priority='high',
            assigned_to=self.sam,
            created_by=self.alex,
            progress=40,
            start_date=self.today - timedelta(days=7),
            due_date=task_b_due,
            phase='Phase 2',
            is_seed_demo_data=True,
        )
        for pos, title in enumerate(CHECKLIST_MAP['API Gateway Configuration'], start=1):
            ChecklistItem.objects.create(
                task=task_b, title=title, is_completed=False, position=pos, source='manual',
            )

        # Task A — depends on Task B
        task_a_due = timezone.make_aware(
            datetime.combine(self.today + timedelta(days=14), time(12, 0))
        )
        task_a = Task.objects.create(
            column=todo,
            title='End-to-End Integration Tests',
            description='Full end-to-end test suite covering all API endpoints and integration points.',
            priority='high',
            assigned_to=self.jordan,
            created_by=self.alex,
            progress=0,
            start_date=self.today,
            due_date=task_a_due,
            phase='Phase 2',
            is_seed_demo_data=True,
        )
        task_a.dependencies.add(task_b)

        for pos, title in enumerate(CHECKLIST_MAP['End-to-End Integration Tests'], start=1):
            ChecklistItem.objects.create(
                task=task_a, title=title, is_completed=False, position=pos, source='manual',
            )

        self.stdout.write(
            f'   ✅ Created "API Gateway Configuration" (overdue, 40%) and '
            f'"End-to-End Integration Tests" (depends on it)'
        )
        return 2
