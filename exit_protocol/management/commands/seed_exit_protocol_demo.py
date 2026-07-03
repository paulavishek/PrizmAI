"""
Seeds the buried ``HospiceSession`` + reusable ``ProjectOrgan`` set for the
Exit Protocol demo.

Exit Protocol demo data is *clone-only*: per-user sandbox boards copy whatever the
official template board holds (``kanban.sandbox_views._duplicate_board`` already
deep-copies ``HospiceSession`` and its ``ProjectOrgan`` children). At some point
the template board lost its hospice session and organs, so the Transition Memos,
Organ Bank, and Organ Library tabs render empty on every sandbox cloned since —
even though the cemetery entry ("Legacy Bug Tracker v1") is still present.

This command restores that data. It creates a *buried* hospice session (consistent
with the cemetery entry) plus the five reusable organs, keyed to the current demo
personas (Priya / Marcus / Elena). It targets the official template board **and**
existing sandbox copies, so the tabs populate immediately without a Reset Demo;
future clones inherit it automatically from the template.

Idempotent: boards that already have a ``HospiceSession`` are skipped, so it is
safe to run repeatedly and safe to wire into the demo seed pipeline.

    python manage.py seed_exit_protocol_demo [--dry-run]
"""

from datetime import timedelta

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from accounts.demo_personas import DEMO_PERSONAS
from exit_protocol.models import HospiceSession, ProjectOrgan
from kanban.models import Board, BoardMembership

# Reuse the exact memo prose from the repair command so the seeded and repaired
# paths stay identical.
from exit_protocol.management.commands.fix_exit_protocol_demo import (
    MEMO_BY_USERNAME,
    CURRENT_USERNAMES,
)


# Compassionate wind-down summary shown at the top of the hospice dashboard.
AI_ASSESSMENT = (
    "The Legacy Bug Tracker v1 project was wound down because scope kept expanding "
    "beyond the original brief. What started as a simple internal bug tracker "
    "accumulated feature requests until it resembled a full product — sprint "
    "planning, reporting dashboards, and notification systems were all added without "
    "a corresponding architecture review. Velocity dropped sharply as team members "
    "were pulled onto higher-priority projects, and after three consecutive sprints "
    "below 40% completion the decision was made to archive it and extract reusable "
    "components for future use."
)

# The five reusable organs, transcribed verbatim from the intact reference board.
# ``payload`` is deliberately self-contained (no FK ids) because the source board
# gets archived — organs must survive on their own.
ORGANS = [
    {
        "organ_type": "checklist",
        "name": "Pre-Release QA Checklist",
        "description": "A 7-item checklist covering all critical quality gates before any production release.",
        "reusability_score": 92,
        "payload": {
            "items": [
                "Regression test suite passed",
                "Cross-browser compatibility verified",
                "Performance benchmarks within threshold",
                "Accessibility scan completed",
                "Stakeholder sign-off received",
                "Rollback plan confirmed",
                "Monitoring alerts configured",
            ]
        },
    },
    {
        "organ_type": "task_template",
        "name": "Bug Triage & Reproduction Template",
        "description": "A structured task template for reproducing and categorizing bugs with all essential diagnostic fields.",
        "reusability_score": 88,
        "payload": {
            "fields": [
                "steps_to_reproduce",
                "expected_behavior",
                "actual_behavior",
                "severity",
                "affected_version",
                "browser_environment",
                "assigned_qa",
            ],
            "default_priority": "High",
            "estimated_hours": 2,
        },
    },
    {
        "organ_type": "knowledge_entry",
        "name": "Root Cause: Scope Creep Pattern",
        "description": "Documents the scope creep pattern observed in this project and the recommended mitigation approach.",
        "reusability_score": 85,
        "payload": {
            "pattern": (
                "Incremental feature additions, each individually reasonable, compound into a "
                "scope 3x the original brief when accepted without a corresponding architecture "
                "review. The system's load-bearing assumptions are never revisited until a hard "
                "failure forces the issue."
            ),
            "early_warning_signs": [
                "Sprint scope increasing by more than 15% without a formal change request",
                "Team velocity declining for two consecutive sprints",
                "Hotfix tasks exceeding 30% of total sprint work",
            ],
            "recommended_mitigation": (
                "Introduce a scope gate after every 2x growth from baseline: mandatory "
                "architecture review, performance benchmark, and stakeholder re-sign-off before "
                "any further features are accepted into the backlog."
            ),
            "source_project": "Legacy Bug Tracker v1",
        },
    },
    {
        "organ_type": "goal_framework",
        "name": "Bug Severity Classification Framework",
        "description": "Four-tier severity classification with response time SLAs and escalation paths.",
        "reusability_score": 79,
        "payload": {
            "tiers": [
                {
                    "level": "P0 — Critical",
                    "response_time_sla": "2 hours",
                    "escalation_path": "Immediate page to on-call lead and VP Engineering",
                },
                {
                    "level": "P1 — High",
                    "response_time_sla": "8 hours",
                    "escalation_path": "Assigned to QA lead, flagged in daily standup",
                },
                {
                    "level": "P2 — Medium",
                    "response_time_sla": "3 business days",
                    "escalation_path": "Added to current sprint backlog",
                },
                {
                    "level": "P3 — Low",
                    "response_time_sla": "2 weeks",
                    "escalation_path": "Triaged into next sprint planning session",
                },
            ]
        },
    },
    {
        "organ_type": "automation_rule",
        "name": "Auto-assign Critical Bugs",
        "description": "Automation rule that triggers on Critical label and routes the task to the QA lead instantly.",
        "reusability_score": 75,
        "payload": {
            "trigger": "label_added",
            "condition": "label == Critical",
            "actions": [
                "assign_to_qa_lead",
                "move_to_in_progress",
                "notify_team_channel",
            ],
        },
    },
]

# How long ago (relative to "now") the demo project was wound down. Keeps the
# dashboard reading "buried ~2.5 months ago" instead of a frozen calendar date.
INITIATED_DAYS_AGO = 90
BURIED_DAYS_AGO = 75
EXTRACTED_DAYS_AGO = 77


class Command(BaseCommand):
    help = "Seed the Exit Protocol hospice session + reusable organs for the demo."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run", action="store_true",
            help="Report what would change without writing to the database.",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]

        # Official demo template + every sandbox copy derived from it. Seeding the
        # template means future clones inherit; backfilling sandboxes populates the
        # tabs for users who cloned before this data existed.
        target_boards = list(
            Board.objects.filter(is_official_demo_board=True)
            | Board.objects.filter(is_sandbox_copy=True)
        )
        self.stdout.write(f"Target boards: {len(target_boards)}")

        seeded = 0
        for board in target_boards:
            if HospiceSession.objects.filter(board=board).exists():
                continue  # already has a session — idempotent skip

            members = {
                m.user.username: m.user
                for m in BoardMembership.objects.filter(board=board).select_related("user")
            }
            present = CURRENT_USERNAMES & set(members)
            if not present:
                # Not staffed by the current personas — nothing sensible to key
                # memos to. Skip rather than seed an orphaned session.
                continue

            memos = {
                str(members[uname].id): MEMO_BY_USERNAME[uname]
                for uname in present
            }
            lead_username = DEMO_PERSONAS["lead"]["username"]
            initiator = members.get(lead_username) or members[sorted(present)[0]]

            self.stdout.write(
                f"  board {board.id} ({board.name}): seed buried session "
                f"(initiated_by={initiator.username}, memos={sorted(memos.keys())}) "
                f"+ {len(ORGANS)} organs"
            )
            if not dry_run:
                self._seed_board(board, initiator, memos)
            seeded += 1

        prefix = "[DRY RUN] would seed" if dry_run else "Seeded"
        self.stdout.write(self.style.SUCCESS(
            f"{prefix}: {seeded} board(s) with a hospice session + {len(ORGANS)} organs each."
        ))

    # ──────────────────────────────────────────────────────────────
    def _seed_board(self, board, initiator, memos):
        now = timezone.now()
        with transaction.atomic():
            session = HospiceSession.objects.create(
                board=board,
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
                    source_board=board,
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
