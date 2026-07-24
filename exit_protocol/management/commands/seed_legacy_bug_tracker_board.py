"""
Seeds "Legacy Bug Tracker v1" as its OWN archived demo board — the single most
important structural fix for Exit Protocol's demo narrative.

## The problem this fixes

Historically the demo reused the one *active* "Software Development" board to
*also* play the *archived* "Legacy Bug Tracker v1" project. Its buried
``HospiceSession``, its ``CemeteryEntry``, its five reusable ``ProjectOrgan``s,
and its transition memos were all pinned to the live Software Development board.
The result was visible within two scrolls:

  * The Exit Protocol dashboard showed an *active, healthy* board (18% risk)
    that simultaneously had a *buried* hospice session and an AI assessment
    describing a different project's wind-down.
  * Transition Memos / Organ Bank / Organ Library were stamped "Software
    Development" but described the bug tracker.
  * The autopsy's "Knowledge Preserved" listed Software Development's 29 live
    memories (auth, GraphQL, PostgreSQL…) as the bug tracker's legacy.

A band-aid (``exit_protocol.views._align_project_name``) rewrote the board's
name to the cemetery entry's ``project_name`` on the autopsy page, but the two
projects were still one board everywhere else.

## What this command does

Creates a *separate*, *archived* official-demo template board named
"Legacy Bug Tracker v1" and gives it its **own** data:

  * a small but coherent set of columns + representative tasks,
  * its **own** preserved MemoryNodes (bug-tracker-specific: scope creep, the
    10K-record scaling ceiling, manual-QA-does-not-scale) — distinct from
    Software Development's live memories,
  * the buried ``HospiceSession`` + five reusable organs (moved off Software
    Development),
  * the ``CemeteryEntry`` autopsy (moved off Software Development),
  * seeded ``ProjectHealthSignal`` history that *rises* to the hospice band
    (this board really did die), unlike the active board's flat-healthy series.

It then **detaches** the Exit-Protocol wind-down artifacts from the Software
Development template + every sandbox copy, so the live board reads as a healthy
*active* project with no hospice session — exactly what its 18% score says.

Because the new board is a normal ``is_official_demo_board=True`` board, the
per-user sandbox provisioner (``kanban.tasks.sandbox_provisioning``) clones it
automatically via ``_duplicate_board`` — no extra clone wiring required. It is
``is_archived=True`` so it never appears in the active board grid; users reach
it only through the Cemetery / Organ Library, which is the intended entry point.

Idempotent: re-running updates the template board's data in place and re-detaches
any hospice/organs/cemetery that drifted back onto Software Development boards.

    python manage.py seed_legacy_bug_tracker_board [--dry-run]
"""

from datetime import timedelta

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from accounts.demo_personas import DEMO_PERSONAS
from exit_protocol.models import (
    HospiceSession, ProjectOrgan, CemeteryEntry, ProjectHealthSignal,
)
from kanban.models import Board, BoardMembership, Column, Task

# Reuse the exact organ specs + memo prose already curated for the demo so the
# archived board and any repair path stay identical.
from exit_protocol.management.commands.seed_exit_protocol_demo import (
    ORGANS, AI_ASSESSMENT,
)
from exit_protocol.management.commands.fix_exit_protocol_demo import (
    MEMO_BY_USERNAME, CURRENT_USERNAMES,
)

LEGACY_BOARD_NAME = "Legacy Bug Tracker v1"

# Relative ages (days before "now") so the board keeps reading "buried ~2.5
# months ago" instead of a frozen calendar date. Mirrors seed_exit_protocol_demo.
INITIATED_DAYS_AGO = 90
BURIED_DAYS_AGO = 75
EXTRACTED_DAYS_AGO = 77
STARTED_DAYS_AGO = 248   # ~Nov 2025 relative to a late-Jul "now"
ENDED_DAYS_AGO = 83      # ~early-May 2026

# ── Cemetery autopsy content (curated; em-dashes clean, AVOID phrased as
# negatives per review feedback) ─────────────────────────────────────────────
CAUSE_OF_DEATH = "scope_creep_spiral"

AI_CAUSE_RATIONALE = (
    "The Legacy Bug Tracker project experienced a classic scope creep spiral. "
    "What began as a simple defect tracking tool grew to include feature "
    "requests, sprint planning, and reporting capabilities — each addition "
    "stretching the monolithic architecture beyond its design limits. The final "
    "trigger was a database performance collapse when the bug count exceeded "
    "10,000 records, revealing fundamental scaling limitations that could not be "
    "fixed without a complete rewrite."
)

CONTRIBUTING_FACTORS = [
    "Monolithic architecture hit scaling ceiling at 10K records",
    "Scope expanded 3x from original requirements without architecture review",
    "Budget overrun of 9.3% ($7,000) with diminishing returns on new features",
    "Team morale declined as technical debt accumulated",
    "No automated testing — manual QA could not keep pace with changes",
]

# severity is on a 0..100 scale (the autopsy chart's Y axis). ``date`` values are
# filled in at seed time relative to "now" so the timeline stays current. The
# final point (``is_winddown``) marks when the structured wind-down was initiated.
DECLINE_TIMELINE_STEPS = [
    (230, 5,  "Project launched with strong momentum", False),
    (200, 10, "First signs of scope creep — sprint planning feature requested", False),
    (170, 18, "Reporting features added, architecture strain visible", False),
    (140, 30, "Database queries slowing, team spending 40% on hotfixes", False),
    (110, 45, "Performance collapse at 10K records, budget overrun begins", False),
    (95,  65, "Team morale plummets, velocity drops to 1.2 tasks/week", False),
    (ENDED_DAYS_AGO, 85, "Decision to rebuild on microservices — wind-down initiated", True),
]

LESSONS_TO_REPEAT = [
    "Strong initial requirements gathering and team alignment",
    "Regular sprint retrospectives caught issues early (even if not always acted upon)",
    "Comprehensive bug categorization taxonomy proved valuable and was carried forward",
]

# All four are phrased as things to STOP doing, so the AVOID bucket contains no
# prescriptions (review feedback). The corresponding "do this instead" guidance
# lives in the knowledge organs.
LESSONS_TO_AVOID = [
    "Never expand scope 3x without an architecture review checkpoint",
    "Never let performance benchmarking slip past sprint 2 — unbudgeted load testing hides the scaling ceiling",
    "Never defer automated testing — manual QA does not scale",
    "Never grow the backlog without a budget gate that forces a scope review",
]

OPEN_QUESTIONS = [
    "Should we have pivoted to microservices earlier, or was the monolith the right choice for the MVP phase?",
    "Could the project have been saved with a dedicated performance engineer?",
]

TAGS = ['monolith', 'scope-creep', 'scaling', 'technical-debt', 'performance']

PROJECT_DESCRIPTION = (
    "The original bug tracking system built on a monolithic architecture. "
    "Wound down deliberately through Exit Protocol after persistent scalability "
    "issues; reusable parts were preserved for successor projects."
)

# ── Columns + representative tasks for the archived board ─────────────────────
# The cemetery numbers (38/45) come from the CemeteryEntry snapshot, not a live
# count, so we only need a coherent handful of tasks for anyone who opens the
# archived board directly.
COLUMNS = ["Backlog", "In Progress", "Done"]

TASKS = [
    ("Bug ingestion pipeline", "Done"),
    ("Severity classification engine", "Done"),
    ("Pre-release QA checklist", "Done"),
    ("Reporting dashboards", "Done"),
    ("Sprint planning module (scope creep)", "In Progress"),
    ("Query optimiser — critical bugs", "In Progress"),
    ("Duplicate-detection refactor", "In Progress"),
    ("Database schema migration to sharded store", "Backlog"),
    ("Automated regression suite", "Backlog"),
    ("Microservices rebuild spike", "Backlog"),
]

# ── The archived board's OWN preserved memories ──────────────────────────────
# Distinct from Software Development's 29 live memories. These are the records
# the autopsy's "Knowledge Preserved" section surfaces, and they demonstrate the
# cross-project claim (two projects, each with its own memory) the whole feature
# rests on.
MEMORIES = [
    ('decision', 0.9,
     "Monolithic architecture chosen for v1 MVP",
     "For the initial defect tracker we chose a single Django monolith over a "
     "service split — faster to ship for a small internal tool. The assumption "
     "was that the tool would stay small; that assumption was never revisited."),
    ('decision', 0.8,
     "Manual QA over automated regression for v1",
     "To hit the launch date the team deferred an automated regression suite and "
     "relied on a manual pre-release checklist. Accepted as temporary; it became "
     "permanent and could not keep pace once scope tripled."),
    ('decision', 0.75,
     "Bug severity taxonomy standardised at P0–P3",
     "Four-tier severity with response-time SLAs and escalation paths. This "
     "framework outlived the project and was extracted as a reusable organ."),
    ('lesson', 0.95,
     "Monolith scaling ceiling appears suddenly at ~10K records",
     "Query latency was fine until the bug table crossed ~10,000 rows, then "
     "collapsed. Root cause: unindexed joins the monolith never load-tested. "
     "Lesson: load-test the data model at 10x expected volume before launch."),
    ('lesson', 0.9,
     "Scope creep compounds silently without an architecture gate",
     "Each feature request was individually reasonable; together they tripled "
     "scope with no architecture review. A scope gate after every 2x growth from "
     "baseline would have surfaced the strain far earlier."),
    ('lesson', 0.85,
     "Manual QA does not scale with scope",
     "Manual regression that covered v1 comfortably became the release bottleneck "
     "by v1.4. On-time completion for QA tasks fell below 30%."),
    ('risk_event', 0.9,
     "Database performance collapse at 10K bug records",
     "In March the primary bug query began timing out under production load once "
     "the table exceeded 10K rows — the trigger event for the wind-down decision."),
    ('risk_event', 0.7,
     "Budget overrun of 9.3% with diminishing feature returns",
     "Spend reached $82,000 against a $75,000 allocation while each new feature "
     "returned less usable value — a signal the project had passed its useful ceiling."),
    ('scope_change', 0.6,
     "Scope expanded 3x: from defect tracker to full product",
     "Sprint planning, reporting dashboards, and a notification system were all "
     "added on top of a tool scoped only to track defects, with no corresponding "
     "architecture review."),
    ('milestone', 0.5,
     "Severity classification engine shipped",
     "The P0–P3 classification engine went live and became the team's quality "
     "backbone — later preserved as the Bug Severity Classification Framework organ."),
    ('outcome', 0.8,
     "Project wound down after 38/45 tasks completed (84%)",
     "38/45 tasks completed (84%). Despite high completion the project was "
     "deliberately archived rather than finished, because the scaling ceiling "
     "could not be resolved without a full rewrite."),
    ('conflict_resolution', 0.6,
     "Ownership of the schema-migration task resolved",
     "Two leads were assigned the database schema & migration task; ownership was "
     "consolidated to the backend lead to avoid duplicated migration scripts."),
    ('ai_recommendation', 0.7,
     "AI flagged the scaling risk two sprints before collapse",
     "Predictive analysis warned that query latency growth was super-linear with "
     "record count and would breach SLA within two sprints. The warning was noted "
     "but not actioned before the collapse."),
]


class Command(BaseCommand):
    help = "Seed the archived 'Legacy Bug Tracker v1' demo board with its own Exit Protocol data."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run", action="store_true",
            help="Report what would change without writing to the database.",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]

        template_sd = Board.objects.filter(
            name="Software Development", is_official_demo_board=True,
        ).first()
        if template_sd is None:
            self.stdout.write(self.style.WARNING(
                "No official Software Development template board found — nothing to seed."
            ))
            return

        if dry_run:
            existing = Board.objects.filter(
                name=LEGACY_BOARD_NAME, is_official_demo_board=True,
            ).first()
            self.stdout.write(
                f"[DRY RUN] would {'update' if existing else 'create'} archived "
                f"'{LEGACY_BOARD_NAME}' template board with "
                f"{len(TASKS)} tasks, {len(MEMORIES)} memories, {len(ORGANS)} organs, "
                f"a buried hospice session and a cemetery entry."
            )
            detachable = self._count_detachable(template_sd)
            self.stdout.write(
                f"[DRY RUN] would detach Exit Protocol wind-down data from "
                f"{detachable} Software Development board(s)."
            )
            return

        with transaction.atomic():
            legacy = self._upsert_legacy_board(template_sd)
            self._detach_from_software_development()

        backfilled = self._backfill_existing_sandboxes(legacy)

        self.stdout.write(self.style.SUCCESS(
            f"Seeded archived '{LEGACY_BOARD_NAME}' (board #{legacy.id}), detached "
            f"Exit Protocol wind-down data from Software Development boards, and "
            f"cloned the archived board into {backfilled} existing sandbox(es)."
        ))

    # ──────────────────────────────────────────────────────────────
    def _count_detachable(self, template_sd):
        from django.db.models import Q
        sd_ids = list(
            Board.objects.filter(
                Q(is_official_demo_board=True) | Q(is_sandbox_copy=True),
                name="Software Development",
            ).values_list("id", flat=True)
        )
        return HospiceSession.objects.filter(board_id__in=sd_ids).count()

    # ──────────────────────────────────────────────────────────────
    def _upsert_legacy_board(self, template_sd):
        now = timezone.now()

        legacy, created = Board.objects.get_or_create(
            name=LEGACY_BOARD_NAME,
            is_official_demo_board=True,
            defaults={
                "description": PROJECT_DESCRIPTION,
                "is_seed_demo_data": True,
                "is_archived": True,
                "workspace": template_sd.workspace,
                "organization": template_sd.organization,
                "owner": template_sd.owner,
                "created_by": template_sd.created_by,
                "task_prefix": "LBT",
                "project_type": template_sd.project_type,
            },
        )
        if not created:
            # Keep the description/flags fresh; wipe children so this stays a
            # clean re-seed rather than accumulating duplicates.
            legacy.description = PROJECT_DESCRIPTION
            legacy.is_archived = True
            legacy.is_seed_demo_data = True
            legacy.workspace = template_sd.workspace
            legacy.save(update_fields=[
                "description", "is_archived", "is_seed_demo_data", "workspace",
            ])
            Task.objects.filter(column__board=legacy).delete()
            Column.objects.filter(board=legacy).delete()
            HospiceSession.objects.filter(board=legacy).delete()  # cascades organs + cemetery
            ProjectHealthSignal.objects.filter(board=legacy).delete()
            CemeteryEntry.objects.filter(board=legacy).delete()
            from knowledge_graph.models import MemoryNode
            MemoryNode.objects.filter(board=legacy).delete()

        # Mirror the demo personas as members so transition memos + assignees
        # resolve. These are the same shared persona accounts on Software Dev.
        member_by_username = {}
        for m in BoardMembership.objects.filter(board=template_sd).select_related("user"):
            BoardMembership.objects.get_or_create(
                board=legacy, user=m.user, defaults={"role": m.role},
            )
            member_by_username[m.user.username] = m.user

        self._seed_columns_and_tasks(legacy)
        self._seed_memories(legacy, now)
        session = self._seed_hospice(legacy, member_by_username, now)
        self._seed_cemetery(legacy, session, now)
        self._seed_health_signals(legacy, now)
        return legacy

    def _seed_columns_and_tasks(self, legacy):
        now = timezone.now()
        cols = {}
        for pos, name in enumerate(COLUMNS):
            cols[name] = Column.objects.create(
                board=legacy, name=name, position=pos,
                column_type="done" if name == "Done" else "",
            )
        creator = legacy.created_by or legacy.owner
        for title, col_name in TASKS:
            is_done = col_name == "Done"
            Task.objects.create(
                column=cols[col_name],
                title=title,
                item_type="task",
                progress=100 if is_done else 0,
                completed_at=now - timedelta(days=ENDED_DAYS_AGO) if is_done else None,
                created_by=creator,
                is_seed_demo_data=True,
            )

    def _seed_memories(self, legacy, now):
        from knowledge_graph.models import MemoryNode
        for i, (node_type, importance, title, content) in enumerate(MEMORIES):
            node = MemoryNode.objects.create(
                board=legacy,
                node_type=node_type,
                title=title,
                content=content,
                importance_score=importance,
            )
            # Space them across the project's active window so they read as
            # captured while the project ran.
            MemoryNode.objects.filter(pk=node.pk).update(
                created_at=now - timedelta(days=ENDED_DAYS_AGO + (len(MEMORIES) - i) * 6),
            )

    def _seed_hospice(self, legacy, member_by_username, now):
        present = CURRENT_USERNAMES & set(member_by_username)
        memos = {
            str(member_by_username[uname].id): MEMO_BY_USERNAME[uname]
            for uname in present
        }
        lead_username = DEMO_PERSONAS["lead"]["username"]
        initiator = (
            member_by_username.get(lead_username)
            or (member_by_username[sorted(present)[0]] if present else legacy.created_by)
        )

        session = HospiceSession.objects.create(
            board=legacy,
            initiated_by=initiator,
            trigger_type="manager_initiated",
            status="buried",
            ai_assessment=AI_ASSESSMENT,
            knowledge_checklist={},
            team_transition_memos=memos,
            checklist_completed_items=[],
        )
        HospiceSession.objects.filter(pk=session.pk).update(
            initiated_at=now - timedelta(days=INITIATED_DAYS_AGO),
            buried_at=now - timedelta(days=BURIED_DAYS_AGO),
        )

        for spec in ORGANS:
            organ = ProjectOrgan.objects.create(
                source_board=legacy,
                hospice_session=session,
                organ_type=spec["organ_type"],
                name=spec["name"],
                description=spec["description"],
                payload=spec["payload"],
                reusability_score=spec["reusability_score"],
                status="available",
            )
            ProjectOrgan.objects.filter(pk=organ.pk).update(
                extracted_at=now - timedelta(days=EXTRACTED_DAYS_AGO),
            )
        return session

    def _seed_cemetery(self, legacy, session, now):
        decline_timeline = [
            {
                "date": (now - timedelta(days=days_ago)).date().isoformat(),
                "severity": severity,
                "event": event,
                "is_winddown": is_winddown,
            }
            for days_ago, severity, event, is_winddown in DECLINE_TIMELINE_STEPS
        ]
        entry = CemeteryEntry.objects.create(
            board=legacy,
            hospice_session=session,
            project_name=LEGACY_BOARD_NAME,
            project_description=PROJECT_DESCRIPTION,
            board_id_snapshot=legacy.id,
            team_size=4,
            total_tasks=45,
            completed_tasks=38,
            budget_allocated=75000,
            budget_spent=82000,
            start_date=(now - timedelta(days=STARTED_DAYS_AGO)).date(),
            end_date=(now - timedelta(days=ENDED_DAYS_AGO)).date(),
            cause_of_death=CAUSE_OF_DEATH,
            ai_cause_rationale=AI_CAUSE_RATIONALE,
            contributing_factors=CONTRIBUTING_FACTORS,
            autopsy_summary=(
                "The Legacy Bug Tracker v1 project achieved 84% task completion but "
                "was ultimately wound down due to architectural scaling limits."
            ),
            lessons_to_repeat=LESSONS_TO_REPEAT,
            lessons_to_avoid=LESSONS_TO_AVOID,
            open_questions=OPEN_QUESTIONS,
            decline_timeline=decline_timeline,
            tags=TAGS,
        )
        CemeteryEntry.objects.filter(pk=entry.pk).update(
            buried_at=now - timedelta(days=BURIED_DAYS_AGO),
        )

    def _seed_health_signals(self, legacy, now):
        """A rising health-signal history that actually reaches the hospice band —
        this board really did die, unlike the active Software Development board
        whose series stays flat-healthy. Scores are stored pre-computed; the
        component fields reconstruct the same score via exit_protocol.scoring."""
        from exit_protocol.scoring import score_and_breakdown

        # (days_ago, velocity_decline_pct, budget_spent_pct, tasks_complete_pct,
        #  deadlines_missed_30d, days_idle). Tuned so the score rises
        # monotonically and the final (burial) point clears the 75% hospice band —
        # this board really did die, unlike the active board's flat-healthy series.
        # NB: days_ago DECREASES down the list so the burial point (highest score)
        # is the MOST RECENT signal. It sits at BURIED_DAYS_AGO — the health series
        # ends when the project was buried.
        series = [
            (BURIED_DAYS_AGO + 120, 5,   20, 80, 0,  1),   # ~0.03
            (BURIED_DAYS_AGO + 90,  20,  40, 70, 1,  3),   # ~0.14
            (BURIED_DAYS_AGO + 60,  45,  60, 55, 3,  6),   # ~0.32
            (BURIED_DAYS_AGO + 30,  70,  80, 45, 5,  10),  # ~0.51
            (BURIED_DAYS_AGO,       100, 98, 38, 10, 25),  # ~0.87 → hospice
        ]
        for days_ago, vel, budget, tasks, dl, idle in series:
            sig = ProjectHealthSignal(
                board=legacy,
                velocity_decline_pct=vel,
                budget_spent_pct=budget,
                tasks_complete_pct=tasks,
                deadlines_missed_30d=dl,
                days_since_last_activity=idle,
                dimensions_available=4,
                score_is_valid=True,
            )
            score, _ = score_and_breakdown(sig)
            sig.hospice_risk_score = round(score, 4)
            sig.triggered_hospice = score >= 0.75
            sig.save()
            ProjectHealthSignal.objects.filter(pk=sig.pk).update(
                recorded_at=now - timedelta(days=days_ago),
            )

    # ──────────────────────────────────────────────────────────────
    def _backfill_existing_sandboxes(self, legacy):
        """Clone the archived Legacy board into every existing sandbox that was
        provisioned before this board existed, so users who already have a
        sandbox see the Cemetery / Organ Library populated without a Reset Demo.

        Future sandboxes get it for free: the per-user provisioner clones every
        ``is_official_demo_board=True`` board, and this one now qualifies."""
        from kanban.sandbox_views import _duplicate_board
        from kanban.utils.demo_protection import allow_demo_writes

        # Owners who already have an SD sandbox copy but no Legacy copy yet.
        owners_with_sd = set(
            Board.objects.filter(
                name="Software Development", is_sandbox_copy=True,
            ).exclude(owner__isnull=True).values_list("owner_id", flat=True)
        )
        owners_with_legacy = set(
            Board.objects.filter(
                name=LEGACY_BOARD_NAME, is_sandbox_copy=True,
            ).values_list("owner_id", flat=True)
        )
        todo = owners_with_sd - owners_with_legacy
        if not todo:
            return 0

        from django.contrib.auth import get_user_model
        User = get_user_model()
        done = 0
        for user in User.objects.filter(id__in=todo):
            try:
                with allow_demo_writes():
                    _duplicate_board(legacy, user)
                done += 1
            except Exception as e:
                self.stdout.write(self.style.WARNING(
                    f"  Could not clone Legacy board for {user.username}: {e}"
                ))
        return done

    # ──────────────────────────────────────────────────────────────
    def _detach_from_software_development(self):
        """Remove the Exit-Protocol wind-down artifacts from the Software
        Development template board AND every sandbox copy, so the live board
        reads as a healthy active project (no buried hospice session, no organs,
        no cemetery entry). The archived Legacy Bug Tracker board now owns them.

        Software Development's 29 live MemoryNodes are LEFT IN PLACE — they are
        that project's legitimate Organizational Memory."""
        from django.db.models import Q

        sd_ids = list(
            Board.objects.filter(
                Q(is_official_demo_board=True) | Q(is_sandbox_copy=True),
                name="Software Development",
            ).values_list("id", flat=True)
        )
        if not sd_ids:
            return

        # Cemetery + organs cascade from HospiceSession, but organs are keyed by
        # source_board and cemetery by board too — delete explicitly to be safe.
        ProjectOrgan.objects.filter(source_board_id__in=sd_ids).delete()
        CemeteryEntry.objects.filter(board_id__in=sd_ids).delete()
        HospiceSession.objects.filter(board_id__in=sd_ids).delete()
