"""
Backfill stakeholder data into existing sandbox boards that predate the
populate_missing_demo_data stakeholder seed.

Any sandbox board (is_sandbox_copy=True) that has zero ProjectStakeholder
records but whose template board has stakeholders will be backfilled with:
  - ProjectStakeholder records (copied from template)
  - StakeholderTaskInvolvement records (matched by task title)
  - StakeholderEngagementRecord records (fresh, dates relative to today)

This is a one-time migration for sandboxes created before the stakeholder
demo data was added.  It is safe to re-run — boards that already have
stakeholders are skipped.

Usage:
    python manage.py backfill_sandbox_stakeholders
    python manage.py backfill_sandbox_stakeholders --board-id 100
"""
from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import date, timedelta


class Command(BaseCommand):
    help = 'Backfill stakeholder demo data into existing sandbox boards'

    def add_arguments(self, parser):
        parser.add_argument(
            '--board-id',
            type=int,
            default=None,
            help='Only backfill a specific sandbox board ID (default: all)',
        )

    def handle(self, *args, **options):
        from kanban.models import Board, Task
        from kanban.stakeholder_models import (
            ProjectStakeholder, StakeholderTaskInvolvement, StakeholderEngagementRecord,
        )

        today = date.today()

        # ----------------------------------------------------------------
        # Find sandboxes to process
        # ----------------------------------------------------------------
        qs = Board.objects.filter(is_sandbox_copy=True).select_related('cloned_from', 'owner')
        if options['board_id']:
            qs = qs.filter(pk=options['board_id'])

        sandboxes = list(qs)
        if not sandboxes:
            self.stdout.write(self.style.WARNING('No sandbox boards found.'))
            return

        total_boards = 0
        total_sh = 0
        total_inv = 0
        total_eng = 0

        for sandbox in sandboxes:
            # Skip if already has stakeholders
            if ProjectStakeholder.objects.filter(board=sandbox).exists():
                self.stdout.write(
                    f'  ⏭️  Board {sandbox.id} ({sandbox.name}) — already has stakeholders, skipping'
                )
                continue

            template = sandbox.cloned_from
            if not template:
                self.stdout.write(
                    self.style.WARNING(f'  ⚠️  Board {sandbox.id} has no cloned_from template, skipping')
                )
                continue

            template_stakeholders = list(ProjectStakeholder.objects.filter(board=template))
            if not template_stakeholders:
                self.stdout.write(
                    self.style.WARNING(
                        f'  ⚠️  Template board {template.id} has no stakeholders yet, skipping'
                    )
                )
                continue

            # Build title → sandbox task map (case-insensitive prefix match)
            sandbox_tasks = {
                t.title.lower(): t
                for t in Task.objects.filter(column__board=sandbox)
            }

            # ----------------------------------------------------------------
            # Copy stakeholders
            # ----------------------------------------------------------------
            stakeholder_map = {}  # template pk → new sandbox stakeholder
            for sh in template_stakeholders:
                new_sh = ProjectStakeholder.objects.create(
                    board=sandbox,
                    name=sh.name,
                    role=sh.role,
                    organization=sh.organization,
                    email=sh.email,
                    phone=sh.phone,
                    influence_level=sh.influence_level,
                    interest_level=sh.interest_level,
                    current_engagement=sh.current_engagement,
                    desired_engagement=sh.desired_engagement,
                    notes=sh.notes,
                    is_active=sh.is_active,
                    created_by=sh.created_by,
                )
                stakeholder_map[sh.pk] = new_sh
                total_sh += 1

            # ----------------------------------------------------------------
            # Copy task involvements (match by task title)
            # ----------------------------------------------------------------
            template_involvements = StakeholderTaskInvolvement.objects.filter(
                stakeholder__board=template
            ).select_related('stakeholder', 'task')

            for inv in template_involvements:
                new_sh = stakeholder_map.get(inv.stakeholder_id)
                if not new_sh:
                    continue
                # Match sandbox task by title (case-insensitive)
                new_task = sandbox_tasks.get(inv.task.title.lower())
                if not new_task:
                    continue
                StakeholderTaskInvolvement.objects.get_or_create(
                    stakeholder=new_sh,
                    task=new_task,
                    defaults={
                        'involvement_type': inv.involvement_type,
                        'engagement_status': inv.engagement_status,
                        'engagement_count': inv.engagement_count,
                        'satisfaction_rating': inv.satisfaction_rating,
                        'feedback': inv.feedback,
                        'concerns': inv.concerns,
                        'metadata': inv.metadata,
                    },
                )
                total_inv += 1

            # ----------------------------------------------------------------
            # Seed fresh engagement records (dates relative to today)
            # ----------------------------------------------------------------
            owner = sandbox.owner  # real user — used as created_by
            sh_by_name = {sh.name: sh for sh in stakeholder_map.values()}

            # (name, days_ago, channel, description, outcome, sentiment, rating)
            seed_records = [
                ('Dr. Priya Sharma',   7, 'meeting',
                 'Weekly project status review.',
                 'Budget confirmed. Authentication System escalated to P1.', 'positive', 5),
                ('Dr. Priya Sharma',  28, 'video',
                 'Architecture milestone check-in.',
                 'Signed off on system design.', 'positive', 5),
                ('Marcus Johnson',     5, 'video',
                 'Sprint planning — feature prioritisation.',
                 'User Registration elevated to P1 for current sprint.', 'positive', 5),
                ('Marcus Johnson',    21, 'chat',
                 'Shared wireframe prototypes for review.',
                 'Minor UX revisions requested. Go-ahead given.', 'positive', 4),
                ('Lisa Chen',         10, 'meeting',
                 'Security requirements workshop.',
                 'Session token policy agreed: 30 min idle, 8 hr absolute.', 'positive', 4),
                ('Lisa Chen',         32, 'email',
                 'API Rate Limiting spec sent for compliance review.',
                 'Approved with minor notes on logging granularity.', 'neutral', 3),
                ('David Park',         8, 'video',
                 'User Registration Flow UX review.',
                 'Prototypes approved. A11y improvements incorporated.', 'positive', 5),
                ('David Park',        30, 'meeting',
                 'Design system handoff.',
                 'Component library transferred. Two open items on mobile breakpoints.', 'positive', 4),
                ('Rachel Torres',     12, 'email',
                 'Feature preview summary and beta guide sent.',
                 'Positive response; staging access requested.', 'positive', 4),
                ('James Wilson',      14, 'video',
                 'CI/CD pipeline architecture review.',
                 'Container registry confirmed. 2-week prod prep runway noted.', 'positive', 4),
                ('James Wilson',      40, 'chat',
                 'Notification Service queue encryption discussion.',
                 'At-rest encryption flagged as requirement.', 'neutral', 3),
                ('Tom Bradley',       60, 'email',
                 'Quarterly compliance status report.',
                 'Acknowledged. No compliance blockers raised.', 'neutral', 4),
            ]

            for sh_name, days_ago, channel, desc, outcome, sentiment, rating in seed_records:
                new_sh = sh_by_name.get(sh_name)
                if not new_sh:
                    continue
                StakeholderEngagementRecord.objects.create(
                    stakeholder=new_sh,
                    date=today - timedelta(days=days_ago),
                    description=desc,
                    communication_channel=channel,
                    outcome=outcome,
                    engagement_sentiment=sentiment,
                    satisfaction_rating=rating,
                    follow_up_required=False,
                    created_by=owner,
                )
                total_eng += 1

            self.stdout.write(
                self.style.SUCCESS(
                    f'  ✅ Board {sandbox.id} ({sandbox.name} — owner: {owner.username}): '
                    f'{len(template_stakeholders)} stakeholders, '
                    f'{total_inv} involvements, '
                    f'{len(seed_records)} engagement records'
                )
            )
            total_boards += 1

        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS(
            f'Done. Backfilled {total_boards} sandbox board(s): '
            f'{total_sh} stakeholders, {total_inv} involvements, {total_eng} engagement records.'
        ))
