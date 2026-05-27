"""
Repairs Exit Protocol demo data on the official demo board and its sandbox copies.

Two long-standing data problems are corrected:

1. Transition memos were keyed to the *legacy* demo personas (Alex Chen /
   Sam Rivera / Jordan Taylor, user ids 2/3/4) and copied verbatim into every
   sandbox, even though the boards' actual members are the current personas
   (Priya Sharma / Marcus Chen / Elena Vasquez). The memo text also contained
   corrupted em-dash characters. We re-key the memos to the current members and
   rewrite the prose with correct names, roles, and pronouns.

2. Seeded ``ProjectHealthSignal`` rows stored a hard-coded ``hospice_risk_score``
   that did not match their own component fields (e.g. a stored 0.30 whose
   velocity/budget/deadline/activity factors only add up to 0.17). This made a
   manual "Recalculate" appear to move the score in the wrong direction. We
   recompute every stored score from its components using the canonical formula
   in ``exit_protocol.scoring``.

Idempotent: safe to run repeatedly. Fixing the official template board means
future sandbox copies inherit the corrected data automatically.

    python manage.py fix_exit_protocol_demo [--dry-run]
"""

from django.core.management.base import BaseCommand
from django.db import transaction

from accounts.demo_personas import DEMO_PERSONAS
from exit_protocol.models import HospiceSession, ProjectHealthSignal
from exit_protocol.scoring import score_and_breakdown
from kanban.models import Board, BoardMembership


# Memo content keyed by the *current* persona username. The narrative (Legacy
# Bug Tracker wound down by scope creep) is preserved; only the people change.
MEMO_BY_USERNAME = {
    # Backend Lead — formerly "Alex Chen, Lead Developer"
    DEMO_PERSONAS['lead']['username']: (
        "**Role:** Backend Lead\n\n"
        "**Contributions:** Priya architected the core bug ingestion pipeline and "
        "built the severity classification engine from scratch. She led the database "
        "optimisation effort during the project's final quarter, though the underlying "
        "schema limitations ultimately proved insurmountable.\n\n"
        "**Open Tasks:** Three unresolved critical bugs in the query optimiser remain "
        "open. The duplicate-detection algorithm was mid-refactor and should be reviewed "
        "before being adopted into the new system.\n\n"
        "**Handover Notes:** All schema migration scripts are documented in "
        "/docs/migrations. The bug severity taxonomy (P0–P3 definitions) has been "
        "extracted as an organ and is ready for transplant into any future project."
    ),
    # DevOps / QA — formerly "Sam Rivera, QA Engineer"
    DEMO_PERSONAS['devops']['username']: (
        "**Role:** DevOps / QA\n\n"
        "**Contributions:** Elena built and maintained the full manual regression suite "
        "and authored the pre-release QA checklist that became the team's quality gate. "
        "She identified the database performance degradation two sprints before it caused "
        "the critical outage.\n\n"
        "**Open Tasks:** The cross-browser compatibility test matrix was not completed for "
        "Safari 16. Accessibility audit findings (WCAG 2.1 AA) were documented but never "
        "actioned — these should be carried into the replacement project from day one.\n\n"
        "**Handover Notes:** The pre-release QA checklist has been extracted as a reusable "
        "organ. Elena recommends prioritising automated regression coverage in any "
        "successor project — manual QA at this scale was a bottleneck."
    ),
    # Frontend / UX — formerly "Jordan Taylor, Product Manager"
    DEMO_PERSONAS['frontend']['username']: (
        "**Role:** Frontend / UX\n\n"
        "**Contributions:** Marcus owned the frontend of the bug tracker — the triage "
        "dashboards, reporting views, and severity visualisations the whole team relied "
        "on. He ran the usability sessions that surfaced the scope-creep pattern now "
        "preserved as a knowledge organ.\n\n"
        "**Open Tasks:** Two enterprise stakeholders are awaiting the redesigned "
        "closure-report view. The Q3 dashboard improvements that were de-prioritised have "
        "not yet been triaged for inclusion in the replacement project backlog.\n\n"
        "**Handover Notes:** Marcus has prepared the final UI component inventory and "
        "design tokens in the shared drive under /legacy-bug-tracker. He recommends a "
        "scope freeze gate be built into the new project's governance process before the "
        "first sprint begins."
    ),
}

CURRENT_USERNAMES = set(MEMO_BY_USERNAME.keys())


class Command(BaseCommand):
    help = "Repair Exit Protocol demo memos and health-signal scores."

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run', action='store_true',
            help="Report what would change without writing to the database.",
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']

        # Official demo template + every sandbox copy derived from it.
        target_boards = list(
            Board.objects.filter(is_official_demo_board=True)
            | Board.objects.filter(is_sandbox_copy=True)
        )
        board_ids = {b.id for b in target_boards}
        self.stdout.write(f"Target boards: {len(board_ids)}")

        memos_fixed = self._fix_memos(board_ids, dry_run)
        scores_fixed = self._fix_scores(board_ids, dry_run)

        prefix = "[DRY RUN] would fix" if dry_run else "Fixed"
        self.stdout.write(self.style.SUCCESS(
            f"{prefix}: {memos_fixed} hospice session(s) memos, "
            f"{scores_fixed} health signal score(s)."
        ))

    # ──────────────────────────────────────────────────────────────
    def _fix_memos(self, board_ids, dry_run):
        fixed = 0
        sessions = HospiceSession.objects.filter(board_id__in=board_ids).select_related('board')

        for session in sessions:
            members = {
                m.user.username: m.user
                for m in BoardMembership.objects.filter(board=session.board).select_related('user')
            }
            # Only repair boards staffed by the current personas.
            present = CURRENT_USERNAMES & set(members)
            if not present:
                continue

            new_memos = {
                str(members[uname].id): MEMO_BY_USERNAME[uname]
                for uname in present
            }

            # Re-point "Initiated by" to a current persona (prefer the lead) when
            # it still references a legacy / non-member account such as Alex Chen.
            lead_username = DEMO_PERSONAS['lead']['username']
            preferred = members.get(lead_username) or members[sorted(present)[0]]
            initiator = session.initiated_by
            fix_initiator = initiator is None or initiator.username not in members

            update_fields = []
            if session.team_transition_memos != new_memos:
                update_fields.append('team_transition_memos')
            if fix_initiator:
                update_fields.append('initiated_by')
            if not update_fields:
                continue  # already correct

            self.stdout.write(
                f"  board {session.board_id} ({session.board.name}): "
                f"memos {sorted((session.team_transition_memos or {}).keys())} -> "
                f"{sorted(new_memos.keys())}"
                + (f"; initiated_by {initiator.username if initiator else None} -> "
                   f"{preferred.username}" if fix_initiator else "")
            )
            if not dry_run:
                with transaction.atomic():
                    session.team_transition_memos = new_memos
                    if fix_initiator:
                        session.initiated_by = preferred
                    session.save(update_fields=update_fields)
            fixed += 1
        return fixed

    # ──────────────────────────────────────────────────────────────
    def _fix_scores(self, board_ids, dry_run):
        fixed = 0
        signals = ProjectHealthSignal.objects.filter(
            board_id__in=board_ids, score_is_valid=True,
        )
        for sig in signals:
            recomputed, _ = score_and_breakdown(sig)
            recomputed = round(recomputed, 4)
            if abs(recomputed - sig.hospice_risk_score) < 0.0005:
                continue
            self.stdout.write(
                f"  board {sig.board_id} signal {sig.recorded_at:%Y-%m-%d}: "
                f"score {sig.hospice_risk_score:.3f} -> {recomputed:.3f}"
            )
            if not dry_run:
                ProjectHealthSignal.objects.filter(pk=sig.pk).update(
                    hospice_risk_score=recomputed
                )
            fixed += 1
        return fixed
