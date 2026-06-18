"""
Management command to populate demo requirements data.
Creates categories and requirements linked to existing demo board tasks and org goals.
"""
from datetime import date

from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.db.models import Q
from django.utils import timezone

from accounts.demo_personas import DEMO_PERSONAS, LEGACY_DEMO_USERNAMES

User = get_user_model()


class Command(BaseCommand):
    help = 'Populate demo board with requirement analysis data'

    def handle(self, *args, **options):
        from kanban.models import Board, Task, OrganizationGoal, Mission, Strategy
        from requirements.models import (
            RequirementCategory, Requirement,
        )

        # Find demo board (template board with is_official_demo_board=True)
        demo_board = Board.objects.filter(
            name='Software Development',
            is_official_demo_board=True,
        ).first()

        if not demo_board:
            self.stdout.write(self.style.WARNING('Demo board not found. Skipping requirements demo data.'))
            return

        # Get demo users (resolved via stable persona keys, not hard-coded
        # usernames — the actual people behind these keys change on swaps).
        lead = User.objects.filter(username=DEMO_PERSONAS['lead']['username']).first()
        frontend = User.objects.filter(username=DEMO_PERSONAS['frontend']['username']).first()
        devops = User.objects.filter(username=DEMO_PERSONAS['devops']['username']).first()
        if not lead:
            self.stdout.write(self.style.WARNING('Demo users not found. Skipping.'))
            return

        creator = lead
        reviewer = frontend or lead

        # NOTE: requirements/categories are upserted (get_or_create keyed on
        # board+title / board+name) rather than deleted-and-recreated, so the
        # command is safely re-runnable and never spawns duplicate records.
        self.stdout.write('Creating demo requirements data...')

        # ── Categories ───────────────────────────────────────────────────
        cat_functional, _ = RequirementCategory.objects.get_or_create(
            board=demo_board, name='Functional Requirements',
            defaults={'description': 'Core functional capabilities of the system'},
        )
        cat_nonfunc, _ = RequirementCategory.objects.get_or_create(
            board=demo_board, name='Non-Functional Requirements',
            defaults={'description': 'Performance, security, and quality attributes'},
        )
        cat_ux, _ = RequirementCategory.objects.get_or_create(
            board=demo_board, name='User Experience',
            defaults={'description': 'UX/UI and usability requirements'},
        )

        # ── Goals (org-scoped, reusable across boards) ───────────────────
        # Keyed on name only so the command is safely re-runnable and so it
        # adopts any pre-existing (manually created) Goal of the same name
        # instead of creating a duplicate. On adoption we also update the
        # seed fields so an existing record (e.g. a manually created Asia
        # goal) gets the correct demo flags / metric rather than staying stale.
        demo_org = demo_board.organization

        def _upsert_goal(name, *, create_only=None, **fields):
            """Create or adopt a Goal keyed on name.

            ``fields`` are kept in sync on every run. ``create_only`` fields are
            written only when the record is first created, so a pre-existing
            record's manually-edited values (e.g. the Asia goal's description and
            target date) are preserved on re-runs.

            ``created_by`` is set on creation and is re-assigned to the current
            demo lead ONLY when the existing owner is missing or a legacy /
            inactive demo persona (e.g. the retired ``alex_chen_demo``) — a live
            user's ownership is never overwritten.
            """
            create_only = create_only or {}
            goal, created = OrganizationGoal.objects.get_or_create(
                name=name,
                defaults={**fields, **create_only, 'created_by': creator},
            )
            if created:
                return goal

            for attr, value in fields.items():
                setattr(goal, attr, value)
            update = list(fields.keys())
            owner = goal.created_by
            if (owner is None or not owner.is_active
                    or owner.username in LEGACY_DEMO_USERNAMES):
                goal.created_by = creator
                update.append('created_by')
            if update:
                goal.save(update_fields=update)
            return goal

        # Single consolidated Goal — one clean strategic story for the demo
        # dashboard (replaces the former 5-goal sprawl). Keyed on name so the
        # command adopts any pre-existing record instead of duplicating it.
        goal_v1 = _upsert_goal(
            'Deliver PrizmAI v1.0 — Enterprise-Ready Launch',
            organization=demo_org, status='active', is_demo=True, is_seed_demo_data=True,
            target_metric='Feature-complete, secure, performant, launch-ready',
            target_date=date(2026, 12, 31),
            description=(
                'Bring PrizmAI to an enterprise-ready v1.0 launch: a complete, '
                'secure, and reliable product that customers can adopt with '
                'confidence. Success means the core feature set is delivered, the '
                'platform meets enterprise bars for security, performance and '
                'accessibility, and the product is polished and localized for '
                'go-to-market across regions.'
            ),
        )

        # ── Mission & Strategy (Goal → Mission → Strategy hierarchy) ─────
        # A deliberate 1-Goal → 1-Mission → 1-Strategy → 1-Board spine: with a
        # single richly-seeded board, this is the only shape where the dashboard
        # rollup charts ("Mission Completion & Risk", "Strategy Progress") have
        # zero empty bars. Richness lives in the board's depth, not hierarchy
        # breadth. Adding boards later is what would justify more strategies.
        all_goals = [goal_v1]
        missions_spec = [
            ('Core Product & Feature Delivery', ['Authentication & Data Layer']),
        ]
        mission_names = [name for name, _ in missions_spec]

        # Every demo mission name we have ever seeded — used so a re-run from a
        # DB built by an earlier (3-mission / 13-strategy) version of this
        # command cleanly removes the now-dropped missions during the collapse.
        KNOWN_DEMO_MISSION_NAMES = mission_names + [
            'Platform Reliability, Security & Performance',
            'Market Readiness & User Experience',
        ]

        # Clean any existing seeded strategic hierarchy so re-runs don't
        # accumulate duplicates. Strategies cascade-delete with their Mission.
        # We delete EVERY seeded Mission under this Goal, plus any seeded Mission
        # we recognise by name that has DRIFTED off the demo goal — whether it
        # was detached (organization_goal=NULL via the "Change Goal → None" UI
        # action, since the FK is on_delete=SET_NULL) OR re-pointed at a
        # different, non-seed goal (e.g. a user-created goal in the sandbox).
        # The earlier NULL-only variant missed that re-pointed case, leaving a
        # seeded mission stranded on the wrong goal so the real demo goal showed
        # 0 missions and a re-seed produced a duplicate.
        Mission.objects.filter(is_seed_demo_data=True).filter(
            Q(organization_goal__in=all_goals)
            | Q(name__in=KNOWN_DEMO_MISSION_NAMES)
        ).delete()

        # name -> Strategy, used later to attach requirements.
        strategies = {}

        def _build(goal, spec):
            for mission_name, strategy_names in spec:
                mission = Mission.objects.create(
                    name=mission_name,
                    status='active',
                    organization_goal=goal,
                    created_by=creator,
                    is_demo=True,
                    is_seed_demo_data=True,
                )
                for strategy_name in strategy_names:
                    strategies[strategy_name] = Strategy.objects.create(
                        name=strategy_name,
                        status='active',
                        mission=mission,
                        created_by=creator,
                        is_seed_demo_data=True,
                    )

        _build(goal_v1, missions_spec)
        self.stdout.write(self.style.SUCCESS(
            f'Created {Mission.objects.filter(organization_goal__in=all_goals, is_seed_demo_data=True).count()} missions '
            f'and {len(strategies)} strategies under 1 goal.'
        ))

        # ── Complete the hierarchy: link the demo board to one Strategy ───
        # Board.strategy is a single FK, so a board belongs to exactly ONE
        # strategy. We link only the TEMPLATE board (#1); the dashboard
        # Hierarchy Navigator maps it to each demo user's sandbox copy via
        # `cloned_from`, so sandbox boards must NOT be linked (doing so would
        # inflate the strategy's board count by one per sandbox).
        #
        # The "Software Development" board's tasks (auth, OAuth, file upload,
        # dashboard) map to Core Feature Delivery → Deliver a Secure,
        # High-Performance MVP by Q3, so that Goal gets the fully-realised
        # Goal → Mission → Strategy → Board → Task hierarchy.
        board_strategy = strategies.get('Authentication & Data Layer')
        if board_strategy and demo_board.strategy_id != board_strategy.id:
            demo_board.strategy = board_strategy
            demo_board.save(update_fields=['strategy'])
        self.stdout.write(self.style.SUCCESS(
            f'Linked demo board #{demo_board.pk} to strategy "{board_strategy.name}".'
        ))

        # ── Grab existing demo tasks for linking ─────────────────────────
        demo_tasks = list(Task.objects.filter(column__board=demo_board).order_by('id')[:20])

        # ── Requirements ─────────────────────────────────────────────────
        requirements_data = [
            {
                'title': 'User Authentication & Authorization',
                'description': 'System must support SSO, OAuth2, and role-based access control with configurable permissions.',
                'type': 'functional', 'priority': 'critical', 'status': 'implemented',
                'category': cat_functional, 'acceptance_criteria': '- SSO login works with Google/GitHub\n- RBAC enforces permissions\n- Session timeout after 30min inactivity',
                'task_indices': [0, 1],
            },
            {
                'title': 'Real-time Dashboard Updates',
                'description': 'Dashboard must reflect changes within 2 seconds via WebSocket connections.',
                'type': 'functional', 'priority': 'high', 'status': 'approved',
                'category': cat_functional, 'acceptance_criteria': '- WebSocket connection established on page load\n- Updates propagate within 2s\n- Graceful fallback to polling',
                'task_indices': [2, 3],
            },
            {
                'title': 'API Response Time < 200ms',
                'description': 'All API endpoints must respond within 200ms at P95 under normal load.',
                'type': 'non_functional', 'priority': 'high', 'status': 'approved',
                'category': cat_nonfunc, 'acceptance_criteria': '- P95 latency < 200ms\n- P99 latency < 500ms\n- Load tested at 100 concurrent users',
                'task_indices': [4],
            },
            {
                'title': 'Task CRUD Operations',
                'description': 'Users must be able to create, read, update, and delete tasks with full audit trail.',
                'type': 'functional', 'priority': 'critical', 'status': 'verified',
                'category': cat_functional, 'acceptance_criteria': '- All CRUD operations working\n- Audit log captures all changes\n- Soft delete with recovery option',
                'task_indices': [5, 6, 7],
            },
            {
                'title': 'Mobile Responsive Design',
                'description': 'Application must be fully functional on mobile devices (320px+).',
                'type': 'non_functional', 'priority': 'medium', 'status': 'in_review',
                'category': cat_ux, 'acceptance_criteria': '- All primary flows work on mobile\n- Touch-friendly controls\n- No horizontal scrolling',
                'task_indices': [8],
            },
            {
                'title': 'Data Export (CSV/PDF)',
                'description': 'Users must be able to export reports as CSV and PDF formats.',
                'type': 'functional', 'priority': 'medium', 'status': 'approved',
                'category': cat_functional, 'acceptance_criteria': '- CSV export for tabular data\n- PDF export for reports\n- Export includes all visible columns',
                'task_indices': [9, 10],
            },
            {
                'title': 'WCAG 2.1 AA Compliance',
                'description': 'Application must meet WCAG 2.1 Level AA accessibility standards.',
                'type': 'non_functional', 'priority': 'medium', 'status': 'draft',
                'category': cat_ux, 'acceptance_criteria': '- All images have alt text\n- Keyboard navigation works\n- Color contrast meets AA ratios\n- Screen reader compatible',
                'task_indices': [],
            },
            {
                'title': 'Email Notification System',
                'description': 'System must send email notifications for task assignments, due dates, and mentions.',
                'type': 'functional', 'priority': 'high', 'status': 'implemented',
                'category': cat_functional, 'acceptance_criteria': '- Notifications sent within 60s\n- User can configure preferences\n- Includes unsubscribe link',
                'task_indices': [11, 12],
            },
            {
                'title': 'Data Encryption at Rest',
                'description': 'All sensitive data must be encrypted at rest using AES-256.',
                'type': 'technical', 'priority': 'critical', 'status': 'approved',
                'category': cat_nonfunc, 'acceptance_criteria': '- AES-256 encryption for PII\n- Key rotation every 90 days\n- Encrypted backups',
                'task_indices': [13],
            },
            {
                'title': 'Search Functionality',
                'description': 'Global search across tasks, boards, and wiki content with filters.',
                'type': 'functional', 'priority': 'medium', 'status': 'draft',
                'category': cat_functional, 'acceptance_criteria': '- Full-text search\n- Filter by board/type/date\n- Results within 500ms',
                'task_indices': [],
            },
            {
                'title': 'Automated Testing Pipeline',
                'description': 'CI/CD pipeline must run all tests on every commit with coverage reporting.',
                'type': 'technical', 'priority': 'high', 'status': 'implemented',
                'category': cat_nonfunc, 'acceptance_criteria': '- Tests run on every PR\n- Coverage report generated\n- Build fails below 90% coverage',
                'task_indices': [14, 15],
            },
            {
                'title': 'Drag-and-Drop Board Interface',
                'description': 'Kanban board must support drag-and-drop for task management.',
                'type': 'user', 'priority': 'high', 'status': 'verified',
                'category': cat_ux, 'acceptance_criteria': '- Smooth drag-and-drop on desktop\n- Touch support on tablets\n- Undo last move option',
                'task_indices': [16, 17],
            },
            {
                'title': 'Rate Limiting & DDoS Protection',
                'description': 'API must implement rate limiting and basic DDoS protection.',
                'type': 'non_functional', 'priority': 'high', 'status': 'in_review',
                'category': cat_nonfunc, 'acceptance_criteria': '- 100 req/min per user\n- 429 response for exceeded limits\n- IP-based throttling for anonymous',
                'task_indices': [],
            },
            {
                'title': 'File Upload Support',
                'description': 'Users can attach files to tasks (images, documents up to 25MB).',
                'type': 'functional', 'priority': 'low', 'status': 'draft',
                'category': cat_functional, 'acceptance_criteria': '- Max 25MB per file\n- Image preview in-line\n- Virus scanning on upload',
                'task_indices': [],
            },
            {
                'title': 'Multi-language Support (i18n)',
                'description': 'Application must support English, Spanish, and French localization.',
                'type': 'business', 'priority': 'low', 'status': 'draft',
                'category': cat_ux, 'acceptance_criteria': '- All UI strings externalized\n- Right-to-left text support\n- Date/number format localization',
                'task_indices': [],
            },
        ]

        created_count = 0
        for data in requirements_data:
            # Keyed on board+title so re-runs reuse the existing record.
            req, _ = Requirement.objects.get_or_create(
                board=demo_board,
                title=data['title'],
                defaults=dict(
                    description=data['description'],
                    type=data['type'],
                    priority=data['priority'],
                    status=data['status'],
                    category=data['category'],
                    acceptance_criteria=data['acceptance_criteria'],
                    created_by=creator,
                    assigned_reviewer=reviewer if data['status'] != 'draft' else None,
                ),
            )
            # Keep mutable fields in sync on re-runs (created_by is preserved).
            req.description = data['description']
            req.type = data['type']
            req.priority = data['priority']
            req.status = data['status']
            req.category = data['category']
            req.acceptance_criteria = data['acceptance_criteria']
            req.assigned_reviewer = reviewer if data['status'] != 'draft' else None
            req.save()
            # Link tasks (idempotent)
            req.linked_tasks.set([
                demo_tasks[idx] for idx in data.get('task_indices', [])
                if idx < len(demo_tasks)
            ])
            created_count += 1

        self.stdout.write(self.style.SUCCESS(
            f'Created {created_count} requirements, 3 categories for demo board.'
        ))

        # ── Link the single consolidated Goal to every demo requirement ──
        # Template-board requirements only — sandbox copies are deliberately
        # left unlinked (see _populate_sandbox) to avoid inflating the Goal's
        # requirement count.
        created_reqs = {req.title: req for req in Requirement.objects.filter(board=demo_board)}
        for req in created_reqs.values():
            req.linked_goals.add(goal_v1)
        self.stdout.write(self.style.SUCCESS(
            f'Linked {len(created_reqs)} demo requirements to the consolidated goal.'
        ))

        # ── Link every requirement to the single Strategy ────────────────
        # With one Strategy in the hierarchy, all template-board requirements
        # roll up under it (no requirement is left strategy-less, and the
        # Strategy detail page shows the full set). `.set(...)` makes this
        # idempotent and self-heals rows that pointed at now-deleted strategies.
        the_strategy = strategies.get('Authentication & Data Layer')
        if the_strategy:
            for req in created_reqs.values():
                req.linked_strategies.set([the_strategy])
        self.stdout.write(self.style.SUCCESS(
            f'Linked {len(created_reqs)} demo requirements to the single strategy.'
        ))

        # ── Populate sandbox copies of this board ────────────────────────
        sandbox_boards = Board.objects.filter(
            is_sandbox_copy=True,
            name='Software Development',
        )
        for sb in sandbox_boards:
            self._populate_sandbox(sb, demo_board, creator, reviewer)

    def _populate_sandbox(self, sandbox_board, template_board, creator, reviewer):
        """Copy requirements data from template board to a sandbox copy.

        IMPORTANT: sandbox-copy requirements are deliberately NOT linked to the
        shared org-scoped Goals / Strategies. Those objects are singletons
        shared across every demo user's sandbox, and the Goal/Strategy detail
        views aggregate ``linked_requirements`` across all boards with no
        workspace filter — so linking each sandbox copy would inflate a Goal's
        requirement count by Nx (one extra per sandbox board). Only the
        canonical template-board requirements carry goal/strategy links.
        """
        from kanban.models import Task
        from requirements.models import (
            RequirementCategory, Requirement,
        )

        # Build task mapping: template task title -> sandbox task
        sandbox_tasks = {t.title: t for t in Task.objects.filter(column__board=sandbox_board)}

        # Copy categories (idempotent, keyed on board+name)
        cat_map = {}
        for cat in RequirementCategory.objects.filter(board=template_board):
            new_cat, _ = RequirementCategory.objects.get_or_create(
                board=sandbox_board,
                name=cat.name,
                defaults={'description': cat.description},
            )
            cat_map[cat.pk] = new_cat

        # Copy requirements (idempotent, keyed on board+title)
        for req in Requirement.objects.filter(board=template_board).prefetch_related(
            'linked_tasks',
        ):
            new_req, _ = Requirement.objects.get_or_create(
                board=sandbox_board,
                title=req.title,
                defaults=dict(
                    description=req.description,
                    type=req.type,
                    priority=req.priority,
                    status=req.status,
                    category=cat_map.get(req.category_id),
                    acceptance_criteria=req.acceptance_criteria,
                    created_by=creator,
                    assigned_reviewer=reviewer if req.status != 'draft' else None,
                ),
            )
            # Keep mutable fields in sync on re-runs.
            new_req.description = req.description
            new_req.type = req.type
            new_req.priority = req.priority
            new_req.status = req.status
            new_req.category = cat_map.get(req.category_id)
            new_req.acceptance_criteria = req.acceptance_criteria
            new_req.assigned_reviewer = reviewer if req.status != 'draft' else None
            new_req.save()
            # Sandbox copies must NOT roll up into the shared goals/strategies.
            # Clear so re-running self-heals rows linked by older command versions.
            new_req.linked_goals.clear()
            new_req.linked_strategies.clear()
            # Map tasks by title (idempotent)
            new_req.linked_tasks.set([
                sb_task for old_task in req.linked_tasks.all()
                if (sb_task := sandbox_tasks.get(old_task.title))
            ])

        count = Requirement.objects.filter(board=sandbox_board).count()
        self.stdout.write(self.style.SUCCESS(
            f'  Copied {count} requirements to sandbox board #{sandbox_board.pk}.'
        ))
