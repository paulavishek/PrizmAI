"""
Management Command: Populate Knowledge Base Demo Data
======================================================
Seeds the Software Development demo board's Knowledge Graph with realistic
demo entries — both manual (Decision Log & Lessons) and auto-captured
(system-detected events) — plus AI-discovered MemoryConnections that link
related nodes causally.

Usage:
    python manage.py populate_knowledge_demo_data
    python manage.py populate_knowledge_demo_data --reset  # Clear and recreate

This creates:
- 10 Decision entries (manual, is_auto_captured=False)
- 10 Lesson / General Note entries (manual, is_auto_captured=False)
- 8 Auto-captured system entries (risk events, milestones, scope changes, etc.)
- 6 AI-discovered MemoryConnections linking related nodes causally
"""
from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from django.utils import timezone
from datetime import timedelta
import random

from kanban.models import Board
from accounts.models import Organization
from knowledge_graph.models import MemoryNode, MemoryConnection


class Command(BaseCommand):
    help = 'Populate the Software Development demo board Knowledge Base with demo data'

    def add_arguments(self, parser):
        parser.add_argument(
            '--reset',
            action='store_true',
            help='Clear existing knowledge graph data for demo boards before creating new data',
        )

    def handle(self, *args, **options):
        self.stdout.write(self.style.NOTICE('=' * 80))
        self.stdout.write(self.style.NOTICE('POPULATING KNOWLEDGE BASE DEMO DATA'))
        self.stdout.write(self.style.NOTICE('=' * 80))

        # Get demo organization — look up by is_demo flag, not by hard-coded name
        self.demo_org = Organization.objects.filter(is_demo=True).first()
        if not self.demo_org:
            self.stdout.write(self.style.ERROR('❌ No demo organization found (is_demo=True)!'))
            self.stdout.write('   Please run: python manage.py create_demo_organization')
            return
        self.stdout.write(self.style.SUCCESS(f'✅ Found organization: {self.demo_org.name}'))

        # Get the Software Development board
        self.sd_board = Board.objects.filter(
            is_official_demo_board=True,
            name='Software Development',
        ).first()

        if not self.sd_board:
            self.stdout.write(self.style.ERROR('❌ Software Development demo board not found!'))
            return
        self.stdout.write(self.style.SUCCESS(f'✅ Found board: {self.sd_board.name} (ID: {self.sd_board.pk})'))

        # Get demo users
        self.alex = User.objects.filter(username='alex_chen_demo').first()
        self.sam = User.objects.filter(username='sam_rivera_demo').first()
        self.jordan = User.objects.filter(username='jordan_taylor_demo').first()

        if not self.alex:
            # Fallback to any demo user
            self.alex = User.objects.filter(username__endswith='_demo').first()
        if not self.sam:
            self.sam = self.alex
        if not self.jordan:
            self.jordan = self.alex

        self.stdout.write(f'   Demo users: {self.alex}, {self.sam}, {self.jordan}')

        # Optionally reset
        if options.get('reset'):
            deleted, _ = MemoryNode.objects.filter(board=self.sd_board).delete()
            self.stdout.write(self.style.WARNING(f'   🗑️  Deleted {deleted} existing knowledge nodes'))

        # Seed the data
        manual_nodes = self._seed_manual_entries()
        auto_nodes = self._seed_auto_captured_entries()
        self._seed_memory_connections(manual_nodes, auto_nodes)

        total_manual = len(manual_nodes)
        total_auto = len(auto_nodes)
        self.stdout.write(self.style.SUCCESS(
            f'\n✅ Knowledge Base seeded: {total_manual} manual entries, '
            f'{total_auto} auto-captured entries, 6 AI-discovered connections'
        ))

    # =========================================================================
    # MANUAL ENTRIES (Decision Log & Lessons — left panel)
    # =========================================================================

    def _seed_manual_entries(self):
        """Create 10 Decisions + 10 Lessons/Notes as manual (user-authored) entries."""
        self.stdout.write(self.style.NOTICE('\n📝 Seeding manual Decision & Lesson entries...'))

        # Spread created_at times realistically across the last 3 months
        def past(days):
            return timezone.now() - timedelta(days=days)

        decisions = [
            {
                'title': 'Switched from REST to GraphQL for client API',
                'content': (
                    'After evaluating both options during Sprint 2, the team decided to move '
                    'the client-facing API to GraphQL. REST was creating over-fetching problems '
                    'on the mobile PWA — screens were loading 4–5 endpoints just to render one '
                    'view. GraphQL lets the client request exactly what it needs. Trade-off: '
                    'steeper learning curve for two junior devs, but long-term performance gain '
                    'justified it.'
                ),
                'tags': ['architecture', 'api', 'graphql', 'performance'],
                'importance_score': 0.90,
                'created_by': self.alex,
                'created_at': past(85),
            },
            {
                'title': 'PostgreSQL chosen over MongoDB for primary database',
                'content': (
                    'During the Database Schema & Migrations task planning, we evaluated NoSQL '
                    'vs relational. The project has complex relationships between users, tasks, '
                    'boards, and permissions — a relational model fits this better. MongoDB was '
                    'considered for the activity log only, but we decided to keep everything in '
                    'one system to reduce operational complexity.'
                ),
                'tags': ['database', 'postgresql', 'architecture'],
                'importance_score': 0.88,
                'created_by': self.jordan,
                'created_at': past(80),
            },
            {
                'title': 'JWT chosen for authentication over session cookies',
                'content': (
                    'For the Authentication System, we debated JWT tokens vs traditional '
                    'server-side sessions. Chose JWT because the mobile PWA and REST API need '
                    'stateless auth. Acknowledged trade-off: token revocation is harder — '
                    'mitigated by keeping token expiry at 15 minutes with refresh tokens.'
                ),
                'tags': ['authentication', 'security', 'jwt'],
                'importance_score': 0.87,
                'created_by': self.jordan,
                'created_at': past(75),
            },
            {
                'title': 'Redis selected for real-time collaboration layer',
                'content': (
                    'The Real-time Collaboration feature requires fast pub/sub messaging between '
                    'users. Evaluated Redis, RabbitMQ, and Kafka. Redis Pub/Sub was chosen — it '
                    'already exists in the stack for caching, so no new infrastructure. For our '
                    'scale (under 10,000 concurrent users), Redis is more than sufficient. Kafka '
                    'would be overkill.'
                ),
                'tags': ['redis', 'real-time', 'architecture', 'websockets'],
                'importance_score': 0.83,
                'created_by': self.sam,
                'created_at': past(70),
            },
            {
                'title': 'API rate limiting set at 100 requests/minute per user',
                'content': (
                    'During API Rate Limiting implementation, we debated the threshold. Too low '
                    'frustrates power users; too high leaves us vulnerable to abuse. Settled on '
                    '100 req/min for authenticated users, 20 req/min for unauthenticated. Based '
                    'on real usage analysis from beta — 99th percentile user was at 67 req/min. '
                    'Will revisit at 10k users.'
                ),
                'tags': ['api', 'rate-limiting', 'security', 'performance'],
                'importance_score': 0.80,
                'created_by': self.alex,
                'created_at': past(60),
            },
            {
                'title': 'File uploads capped at 25 MB, stored on S3-compatible storage',
                'content': (
                    'The File Upload System task raised the question of local vs cloud storage. '
                    'Local storage does not scale and creates deployment complexity. Chose '
                    'S3-compatible object storage (works with AWS S3 and self-hosted MinIO). '
                    '25 MB cap based on typical document/image sizes — video uploads explicitly '
                    'out of scope for v1.'
                ),
                'tags': ['file-upload', 'storage', 's3', 'scope'],
                'importance_score': 0.78,
                'created_by': self.sam,
                'created_at': past(55),
            },
            {
                'title': 'Notification service built in-house instead of using a third-party',
                'content': (
                    'Evaluated SendGrid, Courier, and Novu for the Notification Service. Decided '
                    'to build a lightweight in-house solution for v1 — we only need email and '
                    'in-app notifications. Third-party adds cost and a dependency. Will revisit '
                    'if we need SMS, push notifications, or complex multi-channel routing in v2.'
                ),
                'tags': ['notifications', 'build-vs-buy', 'cost'],
                'importance_score': 0.75,
                'created_by': self.alex,
                'created_at': past(50),
            },
            {
                'title': 'Documentation site to use MkDocs over Confluence',
                'content': (
                    'For Project Documentation Setup, we needed a documentation platform. '
                    'Confluence requires per-seat licensing. MkDocs is free, stores docs as '
                    'Markdown in the same Git repo as the code, and auto-deploys on every '
                    'commit. Entire team already comfortable with Markdown. Decision was '
                    'unanimous.'
                ),
                'tags': ['documentation', 'mkdocs', 'tooling'],
                'importance_score': 0.72,
                'created_by': self.jordan,
                'created_at': past(45),
            },
            {
                'title': 'Integration tests to run in CI only, not on every local commit',
                'content': (
                    'During Integration Testing Suite planning, running the full test suite '
                    'locally was taking 4+ minutes and slowing developer flow. Decision: unit '
                    'tests run locally via pre-commit hook (fast, under 30 seconds), integration '
                    'tests run only in CI pipeline on push. Acceptable trade-off — integration '
                    'failures caught before merge.'
                ),
                'tags': ['testing', 'ci-cd', 'developer-experience'],
                'importance_score': 0.78,
                'created_by': self.sam,
                'created_at': past(40),
            },
            {
                'title': 'Data caching TTL standardised at 5 minutes across all endpoints',
                'content': (
                    'The Data Caching Layer had inconsistent TTL values — some endpoints had '
                    '30 seconds, others had 1 hour, set by different developers independently. '
                    'Standardised to 5-minute TTL as the default, with explicit overrides '
                    'required and documented for anything outside this. Reduces cache-related '
                    'bugs and makes behaviour predictable.'
                ),
                'tags': ['caching', 'redis', 'standards', 'performance'],
                'importance_score': 0.76,
                'created_by': self.alex,
                'created_at': past(35),
            },
        ]

        lessons = [
            {
                'title': 'Underestimated database migration complexity — always add buffer',
                'content': (
                    'The Database Schema & Migrations task was estimated at 3 days. Actual time: '
                    '6 days. Root cause: we did not account for migrating existing test data, '
                    'handling nullable vs non-nullable field changes, and writing rollback '
                    'scripts. Going forward, any migration task touching more than 3 tables '
                    'automatically gets a 2x time buffer in estimation.'
                ),
                'tags': ['estimation', 'migrations', 'lessons-learned'],
                'importance_score': 0.70,
                'created_by': self.jordan,
                'created_at': past(78),
            },
            {
                'title': 'Authentication edge cases always take longer than the happy path',
                'content': (
                    'The Authentication System happy path (sign up → log in → log out) was done '
                    'in 2 days. The edge cases — expired tokens, concurrent sessions, password '
                    'reset race conditions, OAuth failure handling — took 5 more days. Lesson: '
                    'when estimating auth work, multiply the happy-path estimate by 3 to account '
                    'for edge cases.'
                ),
                'tags': ['authentication', 'estimation', 'edge-cases'],
                'importance_score': 0.68,
                'created_by': self.sam,
                'created_at': past(73),
            },
            {
                'title': 'Real-time features need load testing before, not after, launch',
                'content': (
                    'During Real-time Collaboration development, we only load-tested after the '
                    'feature was code-complete. Discovered that the WebSocket server degraded '
                    'significantly above 200 concurrent connections — required an architecture '
                    'change at the last minute. New rule: any real-time or WebSocket feature '
                    'must have a load test milestone built into the task, not added at the end.'
                ),
                'tags': ['real-time', 'websockets', 'load-testing', 'process'],
                'importance_score': 0.72,
                'created_by': self.alex,
                'created_at': past(68),
            },
            {
                'title': 'Notification fatigue is real — users disabled emails within week 1',
                'content': (
                    'Initial Notification Service sent an email for every task update, comment, '
                    'and status change. After beta launch, 60% of users had turned off all email '
                    'notifications within the first week. The system was too noisy. Rebuilt '
                    'notification logic with digest emails (daily summary) and user-controlled '
                    'granularity. Open rates recovered to 38%. Lesson: default to less, let '
                    'users opt in to more.'
                ),
                'tags': ['notifications', 'ux', 'user-feedback'],
                'importance_score': 0.65,
                'created_by': self.alex,
                'created_at': past(48),
            },
            {
                'title': 'API documentation written alongside code, not after — saved the sprint',
                'content': (
                    'In a previous sprint, we wrote API docs after the feature was built — it '
                    'took an extra week and introduced inconsistencies. This sprint, every '
                    'endpoint in the API Rate Limiting feature had its documentation written in '
                    'the same PR as the code. Review was faster, the frontend team unblocked '
                    'themselves immediately using the docs, and we found two logic errors during '
                    'the doc-writing process itself.'
                ),
                'tags': ['documentation', 'api', 'process', 'best-practice'],
                'importance_score': 0.63,
                'created_by': self.sam,
                'created_at': past(58),
            },
            {
                'title': 'File upload MIME type validation must happen server-side, not just client-side',
                'content': (
                    'Initial File Upload System implementation only validated file types in the '
                    'browser (JavaScript). During security review, a tester bypassed client '
                    'validation and uploaded a disguised executable. Lesson: client-side '
                    'validation is for UX only (fast feedback). Server-side MIME validation is '
                    'mandatory for security. Added python-magic for server-side validation; '
                    'deployment caught 3 real abuse attempts in the first month.'
                ),
                'tags': ['security', 'file-upload', 'validation', 'lessons-learned'],
                'importance_score': 0.75,
                'created_by': self.jordan,
                'created_at': past(53),
            },
            {
                'title': 'Caching layer introduced a subtle bug in user permission checks',
                'content': (
                    'After deploying the Data Caching Layer, a user reported seeing tasks from a '
                    'board they had been removed from. Root cause: the user\'s board membership '
                    'was cached and the cache was not invalidated on role removal. Fixed by '
                    'adding cache invalidation hooks to all permission-change events. Lesson: '
                    'any caching of access-control data needs explicit invalidation logic — '
                    'never assume TTL expiry is sufficient for security-related data.'
                ),
                'tags': ['caching', 'security', 'permissions', 'bug'],
                'importance_score': 0.73,
                'created_by': self.sam,
                'created_at': past(33),
            },
            {
                'title': 'Waste/Eliminate tasks in the backlog were consistently deprioritised — schedule a cleanup sprint',
                'content': (
                    'Tasks labelled Waste/Eliminate (e.g., Notification Service refactor, legacy '
                    'endpoint cleanup) kept getting pushed to the next sprint. After 3 sprints, '
                    'technical debt had visibly slowed feature velocity. Introduced a rule: '
                    'every 4th sprint is a "hygiene sprint" dedicated entirely to '
                    'Waste/Eliminate tasks. Velocity in the sprint after a hygiene sprint was '
                    'consistently higher.'
                ),
                'tags': ['technical-debt', 'process', 'lean', 'sprint-planning'],
                'importance_score': 0.62,
                'created_by': self.alex,
                'created_at': past(28),
            },
            {
                'title': 'Integration tests caught a critical data loss bug before it reached production',
                'content': (
                    'During Integration Testing Suite execution, a test flagged that '
                    'bulk-deleting tasks was also silently deleting associated time entries — '
                    'a foreign key constraint issue not caught by unit tests. The bug would '
                    'have caused permanent data loss in production. This was a direct '
                    'justification for the investment in integration tests. Shared with the '
                    'team as an example of why integration testing has non-negotiable ROI.'
                ),
                'tags': ['testing', 'integration-tests', 'data-integrity', 'roi'],
                'importance_score': 0.74,
                'created_by': self.jordan,
                'created_at': past(38),
            },
            {
                'title': 'Stand-ups became more effective when anchored to the Kanban board',
                'content': (
                    'Early stand-ups were verbal-only, ran 20–30 minutes, and often went '
                    'off-topic. Switched to a format where the Kanban board is open on screen '
                    'and each person speaks only to cards they moved yesterday or are blocked '
                    'on. Stand-up duration dropped to 8 minutes on average. Blockers were '
                    'visible immediately rather than discovered at the end of the sprint. '
                    'Simple change, significant impact.'
                ),
                'tags': ['process', 'standup', 'kanban', 'team-efficiency'],
                'importance_score': 0.58,
                'created_by': self.sam,
                'created_at': past(20),
            },
        ]

        nodes = []

        for entry in decisions:
            created_at = entry.pop('created_at')
            node = MemoryNode(
                board=self.sd_board,
                node_type='decision',
                is_auto_captured=False,
                **entry,
            )
            node.save()
            # Back-date the timestamp after save
            MemoryNode.objects.filter(pk=node.pk).update(created_at=created_at)
            node.refresh_from_db()
            nodes.append(node)
            self.stdout.write(f'   ✅ Decision: {node.title[:60]}')

        for entry in lessons:
            created_at = entry.pop('created_at')
            node = MemoryNode(
                board=self.sd_board,
                node_type='manual_log',
                is_auto_captured=False,
                **entry,
            )
            node.save()
            MemoryNode.objects.filter(pk=node.pk).update(created_at=created_at)
            node.refresh_from_db()
            nodes.append(node)
            self.stdout.write(f'   ✅ Lesson: {node.title[:60]}')

        return nodes

    # =========================================================================
    # AUTO-CAPTURED ENTRIES (Auto-Captured Memories 🤖 — right panel)
    # =========================================================================

    def _seed_auto_captured_entries(self):
        """Create 8 system-generated auto-captured MemoryNode entries."""
        self.stdout.write(self.style.NOTICE('\n🤖 Seeding auto-captured memory entries...'))

        def past(days):
            return timezone.now() - timedelta(days=days)

        auto_entries = [
            # --- Risk Events ---
            {
                'node_type': 'risk_event',
                'title': 'Missed deadline: User Registration Flow',
                'content': (
                    'Task "User Registration Flow" (SD-10298) missed its target completion '
                    'date of Apr 17. The task moved from In Progress to overdue status. '
                    'Primary blocker: dependency on the Authentication System not yet merged. '
                    'Automatically captured as a risk signal.'
                ),
                'tags': ['missed-deadline', 'risk', 'user-registration'],
                'importance_score': 0.72,
                'context_data': {
                    'task_title': 'User Registration Flow',
                    'task_ref': 'SD-10298',
                    'due_date': 'Apr 17',
                    'blocker': 'Authentication System dependency',
                },
                'created_at': past(9),
            },
            {
                'node_type': 'risk_event',
                'title': 'Missed deadline: Notification Service',
                'content': (
                    'Task "Notification Service" (SD-10301) flagged as overdue on Jun 15. '
                    'The task was in Waste/Eliminate scope, which contributed to repeated '
                    'deprioritisation. Third consecutive sprint where this item slipped. '
                    'Automatically flagged as a recurring risk pattern.'
                ),
                'tags': ['missed-deadline', 'risk', 'notifications', 'recurring'],
                'importance_score': 0.68,
                'context_data': {
                    'task_title': 'Notification Service',
                    'task_ref': 'SD-10301',
                    'due_date': 'Jun 15',
                    'pattern': 'recurring_slip',
                    'slip_count': 3,
                },
                'created_at': past(14),
            },
            # --- Scope Changes ---
            {
                'node_type': 'scope_change',
                'title': 'Scope reduced: video uploads explicitly deferred to v2',
                'content': (
                    'During File Upload System planning, the team formally removed video file '
                    'support from the v1 scope. Maximum file size set at 25 MB. '
                    'Video uploads, streaming delivery, and transcoding pipeline moved to '
                    'a v2 backlog item. Scope reduction acknowledged and logged to prevent '
                    'future re-introduction without deliberate review.'
                ),
                'tags': ['scope-change', 'file-upload', 'v1', 'deferred'],
                'importance_score': 0.65,
                'context_data': {
                    'removed_feature': 'Video upload support',
                    'deferred_to': 'v2',
                    'reason': 'complexity and infrastructure cost',
                    'task_ref': 'SD-10284',
                },
                'created_at': past(54),
            },
            # --- Milestones ---
            {
                'node_type': 'milestone',
                'title': 'Milestone: Authentication System moved to Done',
                'content': (
                    'The Authentication System (SD-10304) was successfully completed and '
                    'moved to the Done column on Apr 10. This unblocked three downstream '
                    'tasks: User Registration Flow, File Upload System, and the '
                    'Notification Service. Milestone automatically captured as all '
                    'acceptance criteria were verified.'
                ),
                'tags': ['milestone', 'authentication', 'done', 'unblocked-tasks'],
                'importance_score': 0.80,
                'context_data': {
                    'task_title': 'Authentication System',
                    'task_ref': 'SD-10304',
                    'completed_date': 'Apr 10',
                    'unblocked': ['User Registration Flow', 'File Upload System', 'Notification Service'],
                },
                'created_at': past(16),
            },
            # --- Conflict Resolutions ---
            {
                'node_type': 'conflict_resolution',
                'title': 'Conflict resolved: ownership of Database Schema & Migrations task',
                'content': (
                    'A resource conflict was detected: both Sam Rivera and Jordan Taylor were '
                    'assigned as owners of the Database Schema & Migrations task (SD-10299). '
                    'Resolved by clarifying Jordan owns the schema design and migration scripts; '
                    'Sam owns the data migration pipeline and rollback procedures. '
                    'Resolution documented to prevent recurrence on future migration tasks.'
                ),
                'tags': ['conflict-resolution', 'resource-conflict', 'ownership', 'database'],
                'importance_score': 0.60,
                'context_data': {
                    'conflict_type': 'resource',
                    'task_ref': 'SD-10299',
                    'parties': ['Sam Rivera', 'Jordan Taylor'],
                    'resolution': 'split_ownership',
                },
                'created_at': past(79),
            },
            {
                'node_type': 'conflict_resolution',
                'title': 'Conflict resolved: schedule overlap between Integration Testing and API Rate Limiting',
                'content': (
                    'A schedule conflict was detected: Integration Testing Suite (SD-10280) '
                    'and API Rate Limiting (SD-10279) both had the same target window with '
                    'the same assignee (Jordan Taylor). Integration tests were moved 1 week '
                    'later; API Rate Limiting retained priority. Conflict auto-detected by '
                    'schedule analysis.'
                ),
                'tags': ['conflict-resolution', 'schedule-conflict', 'sprint-planning'],
                'importance_score': 0.58,
                'context_data': {
                    'conflict_type': 'schedule',
                    'tasks': ['SD-10280', 'SD-10279'],
                    'assignee': 'Jordan Taylor',
                    'resolution': 'reprioritised_timeline',
                },
                'created_at': past(41),
            },
            # --- AI Recommendation ---
            {
                'node_type': 'ai_recommendation',
                'title': 'AI: Test coverage gap detected in authentication module',
                'content': (
                    'AI analysis of completed tasks identified that the Authentication System '
                    'has significantly lower test coverage than comparable features (estimated '
                    '42% vs team average of 74%). The edge cases around token refresh and '
                    'concurrent session handling were flagged as untested. Recommendation: '
                    'add targeted unit tests before the next sprint begins, particularly for '
                    'the password reset race condition scenario.'
                ),
                'tags': ['ai-recommendation', 'test-coverage', 'authentication', 'quality'],
                'importance_score': 0.70,
                'context_data': {
                    'coverage_estimated': '42%',
                    'team_average': '74%',
                    'risk_areas': ['token refresh', 'concurrent sessions', 'password reset'],
                    'recommendation_type': 'quality_gap',
                },
                'created_at': past(12),
            },
            # --- Lesson (auto-detected pattern) ---
            {
                'node_type': 'lesson',
                'title': 'Pattern detected: Waste/Eliminate tasks slip 3× more often than Value-Added tasks',
                'content': (
                    'Velocity analysis across the last 8 sprints reveals a consistent pattern: '
                    'tasks labelled Waste/Eliminate have an on-time completion rate of 28% '
                    'compared to 81% for Value-Added tasks. The pattern correlates with '
                    'deprioritisation under sprint pressure. Automatically surfaced to support '
                    'the upcoming hygiene sprint proposal.'
                ),
                'tags': ['velocity', 'pattern', 'waste-eliminate', 'lean', 'auto-detected'],
                'importance_score': 0.66,
                'context_data': {
                    'waste_on_time_rate': '28%',
                    'value_added_on_time_rate': '81%',
                    'sprints_analysed': 8,
                    'pattern_type': 'velocity_disparity',
                },
                'created_at': past(7),
            },
        ]

        nodes = []
        for entry in auto_entries:
            created_at = entry.pop('created_at')
            node = MemoryNode(
                board=self.sd_board,
                created_by=None,
                is_auto_captured=True,
                **entry,
            )
            node.save()
            MemoryNode.objects.filter(pk=node.pk).update(created_at=created_at)
            node.refresh_from_db()
            nodes.append(node)
            self.stdout.write(f'   🤖 {node.get_node_type_display()}: {node.title[:60]}')

        return nodes

    # =========================================================================
    # MEMORY CONNECTIONS (AI-discovered causal links)
    # =========================================================================

    def _seed_memory_connections(self, manual_nodes, auto_nodes):
        """
        Create 6 AI-discovered MemoryConnections linking related nodes causally.

        Manual node index reference (manual_nodes list):
          Decisions [0–9]:
            0 = REST→GraphQL
            1 = PostgreSQL
            2 = JWT auth
            3 = Redis real-time
            4 = Rate limiting
            5 = File uploads / S3
            6 = In-house notifications
            7 = MkDocs
            8 = Integration tests in CI
            9 = Caching TTL standardisation

          Lessons [10–19]:
            10 = DB migration underestimated
            11 = Auth edge cases estimation
            12 = Real-time load testing
            13 = Notification fatigue
            14 = API docs alongside code
            15 = File upload MIME server-side
            16 = Caching bug → permissions
            17 = Waste/Eliminate cleanup sprint
            18 = Integration tests → data loss bug
            19 = Stand-ups on Kanban board

        Auto node index reference (auto_nodes list):
            0 = risk_event: User Registration Flow missed deadline
            1 = risk_event: Notification Service missed deadline
            2 = scope_change: Video uploads deferred
            3 = milestone: Auth System Done
            4 = conflict_resolution: DB migration ownership
            5 = conflict_resolution: Integration Testing schedule overlap
            6 = ai_recommendation: Test coverage gap
            7 = lesson: Waste/Eliminate velocity pattern
        """
        self.stdout.write(self.style.NOTICE('\n🔗 Seeding AI-discovered MemoryConnections...'))

        connections = [
            # 1. GraphQL decision → led to a measurable performance improvement referenced
            #    in caching TTL standardisation (they needed consistent TTL because GraphQL
            #    responses were being cached inconsistently after the switch)
            {
                'from_node': manual_nodes[0],   # REST→GraphQL decision
                'to_node': manual_nodes[9],     # Caching TTL standardisation
                'connection_type': 'led_to',
                'reason': (
                    'Switching to GraphQL introduced variable response shapes that exposed '
                    'inconsistent TTL values across endpoints. This directly motivated the '
                    'caching TTL standardisation decision.'
                ),
            },
            # 2. Caching TTL standardisation → caused → Caching security bug
            #    (standardising TTL revealed the permissions-caching flaw because it
            #    was now predictable when the stale permission data would be served)
            {
                'from_node': manual_nodes[9],   # Caching TTL standardisation
                'to_node': manual_nodes[16],    # Caching bug / permissions lesson
                'connection_type': 'caused',
                'reason': (
                    'Standardising to a 5-minute TTL made the timing of stale permission '
                    'reads predictable and repeatable, which is how the board-access '
                    'security bug was discovered and reproduced consistently.'
                ),
            },
            # 3. JWT decision → prevented → auth risk event
            #    (stateless JWT prevented a class of session-fixation attacks that
            #    server-side sessions would have been vulnerable to)
            {
                'from_node': manual_nodes[2],   # JWT decision
                'to_node': auto_nodes[6],       # AI recommendation: test coverage gap
                'connection_type': 'similar_to',
                'reason': (
                    'The JWT token refresh and concurrent session logic flagged in the '
                    'AI test-coverage recommendation maps directly to the edge cases '
                    'identified during the JWT decision trade-off analysis. Same risk '
                    'surface, now surfaced as an under-tested area.'
                ),
            },
            # 4. DB migration underestimated lesson → similar to → Auth edge cases lesson
            #    (both are examples of the same estimation anti-pattern: happy-path sizing)
            {
                'from_node': manual_nodes[10],  # DB migration underestimated
                'to_node': manual_nodes[11],    # Auth edge cases estimation
                'connection_type': 'similar_to',
                'reason': (
                    'Both cases reflect the same estimation failure: scoping only the '
                    'happy path. Database migrations and authentication both have '
                    'substantial hidden complexity in edge cases, rollbacks, and '
                    'failure modes that were not accounted for upfront.'
                ),
            },
            # 5. Notification fatigue lesson → prevented → future over-notification
            #    (the lesson directly informed the Notification Service decision to
            #    build in-house with digest support from day one)
            {
                'from_node': manual_nodes[13],  # Notification fatigue lesson
                'to_node': manual_nodes[6],     # In-house notification service decision
                'connection_type': 'prevented',
                'reason': (
                    'The notification fatigue lesson from the beta (60% opt-out rate) '
                    'directly informed the v1 notification service design: digest-first, '
                    'granular user controls from launch. Building in-house gave the team '
                    'full control over this behaviour without third-party constraints.'
                ),
            },
            # 6. File upload MIME lesson → led to → S3 file upload decision being revisited
            #    for security (the server-side validation finding reinforced the need to
            #    keep uploads in isolated cloud storage, not local)
            {
                'from_node': manual_nodes[15],  # File upload MIME security lesson
                'to_node': manual_nodes[5],     # File uploads / S3 decision
                'connection_type': 'led_to',
                'reason': (
                    'Discovering that client-side MIME validation could be bypassed '
                    'reinforced the decision to use S3-compatible isolated storage: '
                    'if a malicious file does slip through validation, cloud object '
                    'storage prevents it from executing on the application server.'
                ),
            },
        ]

        for conn_data in connections:
            conn, created = MemoryConnection.objects.get_or_create(
                from_node=conn_data['from_node'],
                to_node=conn_data['to_node'],
                connection_type=conn_data['connection_type'],
                defaults={
                    'reason': conn_data['reason'],
                    'ai_generated': True,
                },
            )
            status = 'created' if created else 'already exists'
            self.stdout.write(
                f'   🔗 [{conn.connection_type.upper()}] '
                f'"{conn.from_node.title[:35]}..." → "{conn.to_node.title[:35]}..." '
                f'({status})'
            )
