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

import re

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

# Legacy persona *names* baked into the seeded scenario/vaccine TEXT (not FKs).
# The seeded Stress Test / Pre-Mortem records were authored while the legacy
# personas (Sam Rivera / Jordan Taylor / Alex Chen) were the demo team, so their
# names appear inside attack_description, cascade_effect, dimension rationales
# and vaccine hints. The FK re-keying above only fixes "Run by"; this map fixes
# the prose so the demo team page (Priya / Marcus / Elena) matches the story.
#
# The "single backend point-of-failure" narrative is deliberately pointed at
# Priya Sharma — on the current board she owns the critical-path backend/auth
# work (Authentication System, Database Schema, Social Login, all urgent/overdue)
# and is the person AI Coach flags as overloaded, so the three features finally
# agree on who the bus-factor risk is. Longest names first so "Sam Rivera" is
# replaced before a bare "Sam".
LEGACY_NAME_REPLACEMENTS = [
    ('Sam Rivera', 'Priya Sharma'),
    ('Jordan Taylor', 'Marcus Chen'),
    ('Alex Chen', 'Elena Vasquez'),
    ('Sam', 'Priya'),
    ('Jordan', 'Marcus'),
    ('Alex', 'Elena'),
]

# Text fields on each model that may embed a persona name.
_STRESS_SCENARIO_TEXT_FIELDS = (
    'title', 'attack_description', 'cascade_effect', 'early_warning_sign',
)
_STRESS_VACCINE_TEXT_FIELDS = (
    'name', 'description', 'effort_rationale', 'implementation_hint',
)
_IMMUNITY_TEXT_FIELDS = (
    'schedule_rationale', 'budget_rationale', 'team_rationale',
    'dependencies_rationale', 'scope_stability_rationale',
)
_PREMORTEM_SCENARIO_KEYS = (
    'title', 'description', 'early_warning_sign', 'prevention_action',
)


# Stale numeric/content phrases from the frozen April seed that no longer match
# the live, date-refreshed board. Applied verbatim (case-sensitive) after the
# name swap. Kept small and specific so the pass stays idempotent and never
# touches user-generated sessions. On the current board Priya Sharma owns 9 of
# 33 tasks; her real critical-path items are Authentication System, Database
# Schema, Social Login and Google OAuth.
LEGACY_PHRASE_REPLACEMENTS = [
    (
        'owns 12 of 30 tasks including critical-path backend work '
        '(Base API, Authentication, Search Engine, API Rate Limiting)',
        'owns 9 of 33 tasks including critical-path backend work '
        '(Authentication System, Database Schema, Social Login, Google OAuth)',
    ),
    (
        'Heavy single-developer dependency on Priya Sharma (12 tasks)',
        'Heavy single-developer dependency on Priya Sharma (9 backend/auth tasks)',
    ),
]


def _replace_legacy_names(text):
    """Swap legacy persona names (and known stale seed phrases) for current
    ones. Names use word-boundary matches so we never mangle unrelated
    substrings; phrases are applied after the name swap. Returns
    (new_text, changed)."""
    if not text:
        return text, False
    new_text = text
    for old, new in LEGACY_NAME_REPLACEMENTS:
        new_text = re.sub(rf'\b{re.escape(old)}\b', new, new_text)
    for old, new in LEGACY_PHRASE_REPLACEMENTS:
        new_text = new_text.replace(old, new)
    return new_text, (new_text != text)


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

        # Repair legacy persona names embedded in the seeded TEXT (separate from
        # the FK attribution above). Without this the demo shows "Sam Rivera"
        # inside attack descriptions and vaccine hints even though no such team
        # member exists.
        text_counts = self._fix_legacy_names_in_text(board_ids, dry_run)
        counts.update(text_counts)

        prefix = "[DRY RUN] would fix" if dry_run else "Fixed"
        total = sum(counts.values())
        for label, n in counts.items():
            if n:
                self.stdout.write(f"  {label}: {n}")
        self.stdout.write(self.style.SUCCESS(f"{prefix} {total} row(s) total."))

    # ──────────────────────────────────────────────────────────────
    def _fix_legacy_names_in_text(self, board_ids, dry_run):
        """Rewrite legacy persona names embedded in seeded Stress Test and
        Pre-Mortem text (attack descriptions, cascade effects, dimension
        rationales, vaccine hints, pre-mortem scenarios). Idempotent — once the
        names are current, the word-boundary regex matches nothing."""
        counts = {
            'StressTestScenario text': 0,
            'ImmunityScore rationale text': 0,
            'Vaccine text': 0,
            'PreMortemAnalysis scenario text': 0,
        }

        # Stress Test scenarios
        for sc in StressTestScenario.objects.filter(session__board_id__in=board_ids):
            changed_fields = []
            for f in _STRESS_SCENARIO_TEXT_FIELDS:
                new_val, changed = _replace_legacy_names(getattr(sc, f))
                if changed:
                    setattr(sc, f, new_val)
                    changed_fields.append(f)
            if changed_fields:
                counts['StressTestScenario text'] += 1
                self.stdout.write(f"  StressTestScenario#{sc.pk}: {', '.join(changed_fields)}")
                if not dry_run:
                    sc.save(update_fields=changed_fields)

        # Immunity score rationales
        from kanban.stress_test_models import ImmunityScore
        for im in ImmunityScore.objects.filter(session__board_id__in=board_ids):
            changed_fields = []
            for f in _IMMUNITY_TEXT_FIELDS:
                new_val, changed = _replace_legacy_names(getattr(im, f))
                if changed:
                    setattr(im, f, new_val)
                    changed_fields.append(f)
            if changed_fields:
                counts['ImmunityScore rationale text'] += 1
                self.stdout.write(f"  ImmunityScore#{im.pk}: {', '.join(changed_fields)}")
                if not dry_run:
                    im.save(update_fields=changed_fields)

        # Vaccines
        for vac in Vaccine.objects.filter(board_id__in=board_ids):
            changed_fields = []
            for f in _STRESS_VACCINE_TEXT_FIELDS:
                new_val, changed = _replace_legacy_names(getattr(vac, f))
                if changed:
                    setattr(vac, f, new_val)
                    changed_fields.append(f)
            if changed_fields:
                counts['Vaccine text'] += 1
                self.stdout.write(f"  Vaccine#{vac.pk}: {', '.join(changed_fields)}")
                if not dry_run:
                    vac.save(update_fields=changed_fields)

        # Pre-Mortem scenarios live inside analysis_json (a JSONField).
        for pm in PreMortemAnalysis.objects.filter(board_id__in=board_ids):
            aj = pm.analysis_json or {}
            scenarios = aj.get('failure_scenarios')
            if not scenarios:
                continue
            pm_changed = False
            for scn in scenarios:
                for key in _PREMORTEM_SCENARIO_KEYS:
                    new_val, changed = _replace_legacy_names(scn.get(key))
                    if changed:
                        scn[key] = new_val
                        pm_changed = True
            if pm_changed:
                counts['PreMortemAnalysis scenario text'] += 1
                self.stdout.write(f"  PreMortemAnalysis#{pm.pk}: failure_scenarios")
                if not dry_run:
                    pm.analysis_json = aj
                    pm.save(update_fields=['analysis_json'])

        return counts

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
