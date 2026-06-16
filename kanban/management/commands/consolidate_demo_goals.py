"""
Consolidate the demo workspace's strategic hierarchy into a single Goal.

⚠️ SUPERSEDED — DO NOT RE-RUN. This was a one-shot migration for the historical
5-Goals → 1-Goal merge and has already been applied. The demo hierarchy was
later collapsed further to a single Goal → single Mission → single Strategy,
which `populate_demo_requirements` (the authoritative seeder) now produces
directly. Re-running THIS command would re-introduce the 3-Mission layout below
and undo that collapse. Kept only as a historical record.

The demo seed (`populate_demo_requirements`) historically produced 5 Goals →
10 Missions → 13 Strategies, which sprawls the dashboard Hierarchy Navigator.
This one-shot, idempotent migration collapses that into a single clean story:

    Deliver PrizmAI v1.0 — Enterprise-Ready Launch
      ├─ Core Product & Feature Delivery
      ├─ Platform Reliability, Security & Performance
      └─ Market Readiness & User Experience

The 13 existing Strategies are RE-PARENTED (their `mission` FK is moved), never
deleted-and-recreated, so any board links (`Board.strategy`) and Requirement
links (`linked_strategies`) survive untouched. Template-board Requirements are
re-linked to the single new Goal.

Safety:
- Everything runs inside one `transaction.atomic()` — any failure rolls back.
- Scoped strictly to the "Demo - Acme Corporation" organization. Never touches
  Boards or Tasks.
- Cascade-aware ordering: Mission→Goal is SET_NULL (Missions orphan, they do NOT
  cascade-delete), so old Missions are deleted EXPLICITLY — but only AFTER their
  Strategies have been moved off them (Strategy→Mission is CASCADE).
- Idempotent: a second run adopts the existing Goal/Missions, finds no old Goals
  to delete, and re-adds already-present links — a net no-op.
"""
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.db import transaction

from accounts.demo_personas import DEMO_PERSONAS

User = get_user_model()

DEMO_ORG_NAME = 'Demo - Acme Corporation'

NEW_GOAL_NAME = 'Deliver PrizmAI v1.0 — Enterprise-Ready Launch'
NEW_GOAL_DESCRIPTION = (
    'Bring PrizmAI to an enterprise-ready v1.0 launch: a complete, secure, and '
    'reliable product that customers can adopt with confidence. Success means the '
    'core feature set is delivered, the platform meets enterprise bars for '
    'security, performance and accessibility, and the product is polished and '
    'localized for go-to-market across regions.'
)

# Mission name -> ordered list of Strategy names that belong under it.
# These are the 13 Strategy names the demo seed creates; the split is 5/4/4.
MISSION_SPEC = [
    ('Core Product & Feature Delivery', [
        'Authentication & Data Layer',
        'Communication & Storage',
        'Onboarding & Adoption',
        'Interface Excellence',
        'Integration Ecosystem Growth',
    ]),
    ('Platform Reliability, Security & Performance', [
        'Data Protection Implementation',
        'Accessibility & Audit Readiness',
        'Backend Speed & Reliability',
        'Cloud Readiness & Reliability',
    ]),
    ('Market Readiness & User Experience', [
        'Language & Locale Support',
        'Regional Campaign Execution',
        'Competitive Positioning',
        'Channel Partner Onboarding',
    ]),
]

# The original seeded Goals this command supersedes (see populate_demo_requirements).
OLD_GOAL_NAMES = [
    'Deliver a Secure, High-Performance MVP by Q3',
    'Achieve Enterprise-Grade Security and Compliance',
    'Deliver a Fast, Reliable User Experience',
    'Scale Platform for Global Adoption',
    'Increase Market Share in Asia by 15%',
]


class Command(BaseCommand):
    help = 'Consolidate the demo workspace Goals/Missions/Strategies into one Goal.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Run the full migration then roll back, printing the summary only.',
        )

    def handle(self, *args, **options):
        from kanban.models import (
            Organization, OrganizationGoal, Mission, Strategy, Board,
        )
        from requirements.models import Requirement

        dry_run = options['dry_run']

        # ── 1. Find the demo org ─────────────────────────────────────────
        demo_org = Organization.objects.filter(name=DEMO_ORG_NAME).first()
        if not demo_org:
            self.stdout.write(self.style.ERROR(
                f'Organization "{DEMO_ORG_NAME}" not found. Nothing to do.'
            ))
            return

        # Resolve the demo lead the same way the seeder does (stable persona key).
        lead = User.objects.filter(
            username=DEMO_PERSONAS['lead']['username']
        ).first()
        if not lead:
            self.stdout.write(self.style.ERROR(
                'Demo lead persona not found. Aborting.'
            ))
            return

        try:
            with transaction.atomic():
                summary = self._consolidate(
                    demo_org, lead,
                    OrganizationGoal, Mission, Strategy, Board, Requirement,
                )
                if dry_run:
                    transaction.set_rollback(True)
        except Exception as exc:
            self.stdout.write(self.style.ERROR(
                f'Consolidation failed and was rolled back: {exc}'
            ))
            raise

        # ── 9. Summary ───────────────────────────────────────────────────
        prefix = '[DRY RUN — rolled back] ' if dry_run else ''
        self.stdout.write(self.style.SUCCESS(
            f'{prefix}Consolidation complete:\n'
            f'  Goals deleted:        {summary["goals_deleted"]}\n'
            f'  Missions deleted:     {summary["missions_deleted"]}\n'
            f'  Strategies reassigned:{summary["strategies_reassigned"]:>4}\n'
            f'  Requirements relinked:{summary["requirements_relinked"]:>4}'
        ))

    def _consolidate(self, demo_org, lead,
                     OrganizationGoal, Mission, Strategy, Board, Requirement):
        # ── 2. Create / adopt the single new Goal ────────────────────────
        new_goal, created = OrganizationGoal.objects.get_or_create(
            name=NEW_GOAL_NAME,
            organization=demo_org,
            defaults={
                'status': 'active',
                'is_demo': True,
                'is_seed_demo_data': True,
                'created_by': lead,
                'description': NEW_GOAL_DESCRIPTION,
            },
        )
        self.stdout.write(
            f'{"Created" if created else "Adopted existing"} Goal '
            f'#{new_goal.pk}: {new_goal.name}'
        )

        # ── 3. Create / adopt the 3 Missions + build strategy→mission map ─
        strategy_to_mission = {}
        missions = []
        for mission_name, strategy_names in MISSION_SPEC:
            mission, _ = Mission.objects.get_or_create(
                name=mission_name,
                organization_goal=new_goal,
                defaults={
                    'status': 'active',
                    'created_by': lead,
                    'is_demo': True,
                    'is_seed_demo_data': True,
                },
            )
            missions.append(mission)
            for s_name in strategy_names:
                strategy_to_mission[s_name] = mission
        # Fallback target for any unexpected/extra strategy, so nothing ever
        # cascade-deletes when we remove the old Missions.
        default_mission = missions[0]

        # ── 4. Identify the old Goals (scoped, excluding the new one) ─────
        old_goals = list(
            OrganizationGoal.objects
            .filter(organization=demo_org, name__in=OLD_GOAL_NAMES)
            .exclude(pk=new_goal.pk)
        )
        old_missions = list(
            Mission.objects.filter(organization_goal__in=old_goals)
        )

        # ── 5. Re-parent ALL Strategies under the old Missions ───────────
        strategies_reassigned = 0
        for strat in Strategy.objects.filter(mission__in=old_missions):
            target = strategy_to_mission.get(strat.name, default_mission)
            if strat.mission_id != target.pk:
                strat.mission = target
                strat.save(update_fields=['mission'])
                strategies_reassigned += 1

        # ── 6. Re-link template-board Requirements to the new Goal ───────
        # Only the canonical official demo board — sandbox copies are left
        # unlinked on purpose (linking them inflates the Goal's requirement
        # count, the prior 5→60 bug).
        requirements_relinked = 0
        template_board = Board.objects.filter(
            name='Software Development', is_official_demo_board=True,
        ).first()
        if template_board:
            for req in Requirement.objects.filter(board=template_board):
                if not req.linked_goals.filter(pk=new_goal.pk).exists():
                    req.linked_goals.add(new_goal)
                    requirements_relinked += 1
        else:
            self.stdout.write(self.style.WARNING(
                'Official demo board not found — skipped requirement re-linking.'
            ))

        # ── 7. Delete the now strategy-free old Missions explicitly ──────
        # (Mission→Goal is SET_NULL, so these would otherwise orphan, not
        # cascade away. Their Strategies were moved in step 5, so this delete
        # cannot take any Strategy with it.)
        missions_deleted = len(old_missions)
        Mission.objects.filter(pk__in=[m.pk for m in old_missions]).delete()

        # ── 8. Delete the old Goals ──────────────────────────────────────
        goals_deleted = len(old_goals)
        OrganizationGoal.objects.filter(
            pk__in=[g.pk for g in old_goals]
        ).delete()

        return {
            'goals_deleted': goals_deleted,
            'missions_deleted': missions_deleted,
            'strategies_reassigned': strategies_reassigned,
            'requirements_relinked': requirements_relinked,
        }
