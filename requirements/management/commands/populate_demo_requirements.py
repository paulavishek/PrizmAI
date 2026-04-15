"""
Management command to populate demo requirements data.
Creates categories, objectives, and requirements linked to existing demo board tasks.
"""
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.utils import timezone

User = get_user_model()


class Command(BaseCommand):
    help = 'Populate demo board with requirement analysis data'

    def handle(self, *args, **options):
        from kanban.models import Board, Task
        from requirements.models import (
            RequirementCategory, ProjectObjective, Requirement,
        )

        # Find demo board (template board with is_official_demo_board=True)
        demo_board = Board.objects.filter(
            name='Software Development',
            is_official_demo_board=True,
        ).first()

        if not demo_board:
            self.stdout.write(self.style.WARNING('Demo board not found. Skipping requirements demo data.'))
            return

        # Get demo users
        alex = User.objects.filter(username='alex_chen_demo').first()
        sam = User.objects.filter(username='sam_rivera_demo').first()
        jordan = User.objects.filter(username='jordan_taylor_demo').first()
        if not alex:
            self.stdout.write(self.style.WARNING('Demo users not found. Skipping.'))
            return

        creator = alex
        reviewer = sam or alex

        # Clean existing demo requirements
        Requirement.objects.filter(board=demo_board).delete()
        ProjectObjective.objects.filter(board=demo_board).delete()
        RequirementCategory.objects.filter(board=demo_board).delete()

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

        # ── Objectives ───────────────────────────────────────────────────
        obj_mvp = ProjectObjective.objects.create(
            board=demo_board,
            title='Deliver MVP by Q3',
            description='Ship a minimum viable product with core features by end of Q3.',
            created_by=creator,
        )
        obj_quality = ProjectObjective.objects.create(
            board=demo_board,
            title='Maintain 95% test coverage',
            description='Ensure all critical paths have automated test coverage.',
            created_by=creator,
        )
        obj_perf = ProjectObjective.objects.create(
            board=demo_board,
            title='Sub-2s page load times',
            description='All primary user flows must complete within 2 seconds.',
            created_by=creator,
        )
        obj_security = ProjectObjective.objects.create(
            board=demo_board,
            title='Pass security audit',
            description='Application must pass OWASP Top 10 security audit before launch.',
            created_by=creator,
        )
        obj_ux = ProjectObjective.objects.create(
            board=demo_board,
            title='Achieve SUS score > 80',
            description='System Usability Scale score above 80 in user testing.',
            created_by=creator,
        )

        # ── Grab existing demo tasks for linking ─────────────────────────
        demo_tasks = list(Task.objects.filter(column__board=demo_board).order_by('id')[:20])

        # ── Requirements ─────────────────────────────────────────────────
        requirements_data = [
            {
                'title': 'User Authentication & Authorization',
                'description': 'System must support SSO, OAuth2, and role-based access control with configurable permissions.',
                'type': 'functional', 'priority': 'critical', 'status': 'implemented',
                'category': cat_functional, 'acceptance_criteria': '- SSO login works with Google/GitHub\n- RBAC enforces permissions\n- Session timeout after 30min inactivity',
                'objectives': [obj_mvp, obj_security], 'task_indices': [0, 1],
            },
            {
                'title': 'Real-time Dashboard Updates',
                'description': 'Dashboard must reflect changes within 2 seconds via WebSocket connections.',
                'type': 'functional', 'priority': 'high', 'status': 'approved',
                'category': cat_functional, 'acceptance_criteria': '- WebSocket connection established on page load\n- Updates propagate within 2s\n- Graceful fallback to polling',
                'objectives': [obj_mvp, obj_perf], 'task_indices': [2, 3],
            },
            {
                'title': 'API Response Time < 200ms',
                'description': 'All API endpoints must respond within 200ms at P95 under normal load.',
                'type': 'non_functional', 'priority': 'high', 'status': 'approved',
                'category': cat_nonfunc, 'acceptance_criteria': '- P95 latency < 200ms\n- P99 latency < 500ms\n- Load tested at 100 concurrent users',
                'objectives': [obj_perf], 'task_indices': [4],
            },
            {
                'title': 'Task CRUD Operations',
                'description': 'Users must be able to create, read, update, and delete tasks with full audit trail.',
                'type': 'functional', 'priority': 'critical', 'status': 'verified',
                'category': cat_functional, 'acceptance_criteria': '- All CRUD operations working\n- Audit log captures all changes\n- Soft delete with recovery option',
                'objectives': [obj_mvp], 'task_indices': [5, 6, 7],
            },
            {
                'title': 'Mobile Responsive Design',
                'description': 'Application must be fully functional on mobile devices (320px+).',
                'type': 'non_functional', 'priority': 'medium', 'status': 'in_review',
                'category': cat_ux, 'acceptance_criteria': '- All primary flows work on mobile\n- Touch-friendly controls\n- No horizontal scrolling',
                'objectives': [obj_ux], 'task_indices': [8],
            },
            {
                'title': 'Data Export (CSV/PDF)',
                'description': 'Users must be able to export reports as CSV and PDF formats.',
                'type': 'functional', 'priority': 'medium', 'status': 'approved',
                'category': cat_functional, 'acceptance_criteria': '- CSV export for tabular data\n- PDF export for reports\n- Export includes all visible columns',
                'objectives': [obj_mvp], 'task_indices': [9, 10],
            },
            {
                'title': 'WCAG 2.1 AA Compliance',
                'description': 'Application must meet WCAG 2.1 Level AA accessibility standards.',
                'type': 'non_functional', 'priority': 'medium', 'status': 'draft',
                'category': cat_ux, 'acceptance_criteria': '- All images have alt text\n- Keyboard navigation works\n- Color contrast meets AA ratios\n- Screen reader compatible',
                'objectives': [obj_ux], 'task_indices': [],
            },
            {
                'title': 'Email Notification System',
                'description': 'System must send email notifications for task assignments, due dates, and mentions.',
                'type': 'functional', 'priority': 'high', 'status': 'implemented',
                'category': cat_functional, 'acceptance_criteria': '- Notifications sent within 60s\n- User can configure preferences\n- Includes unsubscribe link',
                'objectives': [obj_mvp], 'task_indices': [11, 12],
            },
            {
                'title': 'Data Encryption at Rest',
                'description': 'All sensitive data must be encrypted at rest using AES-256.',
                'type': 'technical', 'priority': 'critical', 'status': 'approved',
                'category': cat_nonfunc, 'acceptance_criteria': '- AES-256 encryption for PII\n- Key rotation every 90 days\n- Encrypted backups',
                'objectives': [obj_security], 'task_indices': [13],
            },
            {
                'title': 'Search Functionality',
                'description': 'Global search across tasks, boards, and wiki content with filters.',
                'type': 'functional', 'priority': 'medium', 'status': 'draft',
                'category': cat_functional, 'acceptance_criteria': '- Full-text search\n- Filter by board/type/date\n- Results within 500ms',
                'objectives': [obj_mvp, obj_ux], 'task_indices': [],
            },
            {
                'title': 'Automated Testing Pipeline',
                'description': 'CI/CD pipeline must run all tests on every commit with coverage reporting.',
                'type': 'technical', 'priority': 'high', 'status': 'implemented',
                'category': cat_nonfunc, 'acceptance_criteria': '- Tests run on every PR\n- Coverage report generated\n- Build fails below 90% coverage',
                'objectives': [obj_quality], 'task_indices': [14, 15],
            },
            {
                'title': 'Drag-and-Drop Board Interface',
                'description': 'Kanban board must support drag-and-drop for task management.',
                'type': 'user', 'priority': 'high', 'status': 'verified',
                'category': cat_ux, 'acceptance_criteria': '- Smooth drag-and-drop on desktop\n- Touch support on tablets\n- Undo last move option',
                'objectives': [obj_ux, obj_mvp], 'task_indices': [16, 17],
            },
            {
                'title': 'Rate Limiting & DDoS Protection',
                'description': 'API must implement rate limiting and basic DDoS protection.',
                'type': 'non_functional', 'priority': 'high', 'status': 'in_review',
                'category': cat_nonfunc, 'acceptance_criteria': '- 100 req/min per user\n- 429 response for exceeded limits\n- IP-based throttling for anonymous',
                'objectives': [obj_security], 'task_indices': [],
            },
            {
                'title': 'File Upload Support',
                'description': 'Users can attach files to tasks (images, documents up to 25MB).',
                'type': 'functional', 'priority': 'low', 'status': 'draft',
                'category': cat_functional, 'acceptance_criteria': '- Max 25MB per file\n- Image preview in-line\n- Virus scanning on upload',
                'objectives': [obj_mvp], 'task_indices': [],
            },
            {
                'title': 'Multi-language Support (i18n)',
                'description': 'Application must support English, Spanish, and French localization.',
                'type': 'business', 'priority': 'low', 'status': 'draft',
                'category': cat_ux, 'acceptance_criteria': '- All UI strings externalized\n- Right-to-left text support\n- Date/number format localization',
                'objectives': [], 'task_indices': [],
            },
        ]

        created_count = 0
        for i, data in enumerate(requirements_data):
            req = Requirement.objects.create(
                board=demo_board,
                title=data['title'],
                description=data['description'],
                type=data['type'],
                priority=data['priority'],
                status=data['status'],
                category=data['category'],
                acceptance_criteria=data['acceptance_criteria'],
                created_by=creator,
                assigned_reviewer=reviewer if data['status'] != 'draft' else None,
            )
            # Link objectives
            for obj in data.get('objectives', []):
                req.objectives.add(obj)
            # Link tasks
            for idx in data.get('task_indices', []):
                if idx < len(demo_tasks):
                    req.linked_tasks.add(demo_tasks[idx])
            created_count += 1

        self.stdout.write(self.style.SUCCESS(
            f'Created {created_count} requirements, 3 categories, 5 objectives for demo board.'
        ))

        # ── Populate sandbox copies of this board ────────────────────────
        sandbox_boards = Board.objects.filter(
            is_sandbox_copy=True,
            name='Software Development',
        )
        for sb in sandbox_boards:
            self._populate_sandbox(sb, demo_board, creator, reviewer)

    def _populate_sandbox(self, sandbox_board, template_board, creator, reviewer):
        """Copy requirements data from template board to a sandbox copy."""
        from kanban.models import Task
        from requirements.models import (
            RequirementCategory, ProjectObjective, Requirement,
        )

        # Clean existing
        Requirement.objects.filter(board=sandbox_board).delete()
        ProjectObjective.objects.filter(board=sandbox_board).delete()
        RequirementCategory.objects.filter(board=sandbox_board).delete()

        # Build task mapping: template task title → sandbox task
        sandbox_tasks = {t.title: t for t in Task.objects.filter(column__board=sandbox_board)}

        # Copy categories
        cat_map = {}
        for cat in RequirementCategory.objects.filter(board=template_board):
            new_cat = RequirementCategory.objects.create(
                board=sandbox_board,
                name=cat.name,
                description=cat.description,
            )
            cat_map[cat.pk] = new_cat

        # Copy objectives
        obj_map = {}
        for obj in ProjectObjective.objects.filter(board=template_board):
            new_obj = ProjectObjective.objects.create(
                board=sandbox_board,
                title=obj.title,
                description=obj.description,
                created_by=creator,
            )
            obj_map[obj.pk] = new_obj

        # Copy requirements with relationships
        for req in Requirement.objects.filter(board=template_board).prefetch_related(
            'objectives', 'linked_tasks',
        ):
            new_req = Requirement.objects.create(
                board=sandbox_board,
                title=req.title,
                description=req.description,
                type=req.type,
                priority=req.priority,
                status=req.status,
                category=cat_map.get(req.category_id),
                acceptance_criteria=req.acceptance_criteria,
                created_by=creator,
                assigned_reviewer=reviewer if req.status != 'draft' else None,
            )
            # Map objectives
            for old_obj in req.objectives.all():
                new_obj = obj_map.get(old_obj.pk)
                if new_obj:
                    new_req.objectives.add(new_obj)
            # Map tasks by title
            for old_task in req.linked_tasks.all():
                sb_task = sandbox_tasks.get(old_task.title)
                if sb_task:
                    new_req.linked_tasks.add(sb_task)

        count = Requirement.objects.filter(board=sandbox_board).count()
        self.stdout.write(self.style.SUCCESS(
            f'  Copied {count} requirements to sandbox board #{sandbox_board.pk}.'
        ))
