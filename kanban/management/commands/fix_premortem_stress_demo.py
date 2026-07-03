"""
Repairs Pre-Mortem Analysis and Stress Test demo data on the official demo
board and its sandbox copies.

Both features' "Run by" / "Addressed by" / "Applied by" attributions are user
FKs, not hardcoded strings. The seeded records on the official template board
were generated once while the *legacy* demo personas (Alex Chen / Sam Rivera /
Jordan Taylor) were the active demo users. The subsequent persona swap to
Priya Sharma / Marcus Chen / Elena Vasquez deactivated the legacy accounts but
never re-keyed these FKs, and ``sandbox_views.py`` copies them verbatim into
every per-user sandbox. This mirrors the bug already fixed for Exit Protocol
memos in ``exit_protocol.management.commands.fix_exit_protocol_demo`` — this
command applies the same repair to Pre-Mortem / Stress Test.

Mapping (kept consistent with the Exit Protocol re-keying so the same person
is attributed across features):

    alex_chen_demo     -> priya.sharma  (lead)
    sam_rivera_demo    -> elena.vasquez (devops)
    jordan_taylor_demo -> marcus.chen   (frontend)

Idempotent: safe to run repeatedly. Fixing the official template board means
future sandbox copies inherit the corrected data automatically.

    python manage.py fix_premortem_stress_demo [--dry-run]
"""

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction

from accounts.demo_personas import DEMO_PERSONAS, LEGACY_DEMO_USERNAMES
from kanban.models import Board
from kanban.premortem_models import PreMortemAnalysis, PreMortemScenarioAcknowledgment
from kanban.stress_test_models import StressTestScenario, StressTestSession, Vaccine

User = get_user_model()

# legacy username -> current persona key, matching the re-keying already live
# in exit_protocol.management.commands.fix_exit_protocol_demo.
LEGACY_TO_PERSONA_KEY = {
    'alex_chen_demo': 'lead',
    'sam_rivera_demo': 'devops',
    'jordan_taylor_demo': 'frontend',
}


class Command(BaseCommand):
    help = "Repair Pre-Mortem Analysis and Stress Test demo attributions (legacy persona FKs)."

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run', action='store_true',
            help="Report what would change without writing to the database.",
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']

        legacy_to_current = self._build_legacy_map()
        if not legacy_to_current:
            self.stdout.write(self.style.WARNING(
                "No legacy demo accounts found — nothing to re-key."
            ))
            return

        target_boards = list(
            Board.objects.filter(is_official_demo_board=True)
            | Board.objects.filter(is_sandbox_copy=True)
        )
        board_ids = {b.id for b in target_boards}
        self.stdout.write(f"Target boards: {len(board_ids)}")

        counts = {
            'PreMortemAnalysis.created_by': self._fix_fk(
                PreMortemAnalysis.objects.filter(board_id__in=board_ids),
                'created_by', legacy_to_current, dry_run,
            ),
            'PreMortemScenarioAcknowledgment.acknowledged_by': self._fix_fk(
                PreMortemScenarioAcknowledgment.objects.filter(pre_mortem__board_id__in=board_ids),
                'acknowledged_by', legacy_to_current, dry_run,
            ),
            'StressTestSession.run_by': self._fix_fk(
                StressTestSession.objects.filter(board_id__in=board_ids),
                'run_by', legacy_to_current, dry_run,
            ),
            'StressTestScenario.addressed_by': self._fix_fk(
                StressTestScenario.objects.filter(session__board_id__in=board_ids),
                'addressed_by', legacy_to_current, dry_run,
            ),
            'Vaccine.applied_by': self._fix_fk(
                Vaccine.objects.filter(board_id__in=board_ids),
                'applied_by', legacy_to_current, dry_run,
            ),
        }

        prefix = "[DRY RUN] would fix" if dry_run else "Fixed"
        total = sum(counts.values())
        for label, n in counts.items():
            if n:
                self.stdout.write(f"  {label}: {n}")
        self.stdout.write(self.style.SUCCESS(f"{prefix} {total} row(s) total."))

    # ──────────────────────────────────────────────────────────────
    def _build_legacy_map(self):
        """Map legacy User instances to their current-persona replacement."""
        legacy_users = User.objects.filter(username__in=LEGACY_DEMO_USERNAMES)
        mapping = {}
        for legacy_user in legacy_users:
            persona_key = LEGACY_TO_PERSONA_KEY.get(legacy_user.username)
            if not persona_key:
                continue
            current_username = DEMO_PERSONAS[persona_key]['username']
            current_user = User.objects.filter(username=current_username).first()
            if current_user:
                mapping[legacy_user.id] = current_user
        return mapping

    def _fix_fk(self, queryset, field_name, legacy_to_current, dry_run):
        """Re-point ``field_name`` FK from a legacy demo user to its current
        replacement for every row in ``queryset`` whose FK is currently legacy."""
        fk_id_field = f'{field_name}_id'
        fixed = 0
        for obj in queryset.filter(**{f'{fk_id_field}__in': legacy_to_current.keys()}):
            legacy_id = getattr(obj, fk_id_field)
            new_user = legacy_to_current[legacy_id]
            self.stdout.write(
                f"  {queryset.model.__name__}#{obj.pk}.{field_name}: "
                f"{legacy_id} -> {new_user.username}"
            )
            if not dry_run:
                with transaction.atomic():
                    setattr(obj, field_name, new_user)
                    obj.save(update_fields=[field_name])
            fixed += 1
        return fixed
