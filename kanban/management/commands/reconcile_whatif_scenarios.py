"""
Reconcile seeded What-If scenarios with the real engine.

Three demo scenarios ("Extend Deadline by 3 Weeks + Add QA Tasks", "Reduce
Team by 1 Member", "Add Mobile App Module (+8 tasks)") were seeded with
hand-written `impact_results` that:

  * used a schema the engine never produces (`before`/`after`/`delta` instead
    of `baseline`/`projected`/`deltas`), so every downstream reader that looks
    for `projected.utilization_pct` etc. silently got nothing;
  * carried invented feasibility scores (0.78 / 0.40 / 0.55) that don't match
    what WhatIfEngine actually computes for those slider values.  "Reduce Team
    by 1" was stored at 40% while the engine scores it in the 80s, which made
    the saved-scenario list look internally incoherent — a scenario that only
    drops a member appeared to score 34 points WORSE than one that drops a
    member AND adds 8 tasks;
  * shared one identical `created_at` timestamp to the second, which reads as
    bulk-seeded rather than as a scenario history.

This command re-runs each scenario's own stored `input_parameters` through the
real WhatIfEngine and overwrites `impact_results` with the genuine output, then
staggers the seeded timestamps across separate days.

Idempotent: re-running recomputes against whatever the board looks like now.

    python manage.py reconcile_whatif_scenarios              # all boards
    python manage.py reconcile_whatif_scenarios --board 612
    python manage.py reconcile_whatif_scenarios --dry-run
"""
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.db import transaction

from kanban.models import Board
from kanban.whatif_models import WhatIfScenario
from kanban.utils.whatif_engine import WhatIfEngine

# The seeded scenarios, oldest-first.  Used to stagger the identical
# bulk-seed timestamps so the list reads as a real scenario history.
SEEDED_ORDER = [
    'Add Mobile App Module (+8 tasks)',
    'Reduce Team by 1 Member',
    'Extend Deadline by 3 Weeks + Add QA Tasks',
]
# Days to subtract from the existing timestamp, per position in SEEDED_ORDER.
SEEDED_DAY_OFFSETS = [6, 3, 0]


class Command(BaseCommand):
    help = 'Recompute seeded What-If scenario impact_results with the real engine.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--board', type=int, default=None,
            help='Restrict to a single board ID.',
        )
        parser.add_argument(
            '--dry-run', action='store_true',
            help='Report what would change without writing.',
        )

    def handle(self, *args, **options):
        board_id = options['board']
        dry_run = options['dry_run']

        boards = Board.objects.all()
        if board_id:
            boards = boards.filter(id=board_id)

        total_rescored = 0
        total_restaggered = 0

        for board in boards.iterator():
            scenarios = list(WhatIfScenario.objects.filter(board=board))
            if not scenarios:
                continue

            engine = WhatIfEngine(board)

            for scenario in scenarios:
                params = scenario.input_parameters or {}
                sim_params = {
                    'tasks_added': int(params.get('tasks_added', 0)),
                    'team_size_delta': int(params.get('team_size_delta', 0)),
                    'deadline_shift_days': int(params.get('deadline_shift_days', 0)),
                }

                existing = scenario.impact_results or {}
                # Only rewrite results that are missing or in the legacy
                # hand-seeded schema.  A scenario the user genuinely saved
                # from the dashboard already carries real engine output and
                # must be left exactly as it was scored that day.
                is_legacy = 'projected' not in existing
                if not is_legacy:
                    continue

                try:
                    results = engine.simulate(sim_params)
                except Exception as exc:  # pragma: no cover - defensive
                    self.stderr.write(
                        f'  ! board {board.id} scenario {scenario.id} '
                        f'({scenario.name}): simulate failed: {exc}'
                    )
                    continue

                old_score = existing.get('feasibility_score')
                new_score = results.get('feasibility_score')
                self.stdout.write(
                    f'  board {board.id} · {scenario.name}: '
                    f'feasibility {old_score} -> {new_score}'
                )
                total_rescored += 1

                if not dry_run:
                    with transaction.atomic():
                        scenario.impact_results = results
                        scenario.save(update_fields=['impact_results'])

            # --- Stagger the bulk-seeded timestamps ---
            by_name = {s.name: s for s in scenarios}
            seeded = [by_name[n] for n in SEEDED_ORDER if n in by_name]
            if len(seeded) == len(SEEDED_ORDER):
                # They were all written in the same second by the seeder;
                # only restagger when that's still true, so we never disturb
                # timestamps a user has already seen spread out.
                stamps = {s.created_at.replace(microsecond=0) for s in seeded}
                if len(stamps) == 1:
                    anchor = seeded[-1].created_at
                    for scenario, offset in zip(seeded, SEEDED_DAY_OFFSETS):
                        new_dt = anchor - timedelta(days=offset)
                        self.stdout.write(
                            f'  board {board.id} · {scenario.name}: '
                            f'created_at -> {new_dt:%Y-%m-%d %H:%M}'
                        )
                        total_restaggered += 1
                        if not dry_run:
                            # .update() bypasses auto_now_add on created_at.
                            WhatIfScenario.objects.filter(pk=scenario.pk).update(
                                created_at=new_dt,
                            )

        prefix = '[dry-run] ' if dry_run else ''
        self.stdout.write(self.style.SUCCESS(
            f'{prefix}Rescored {total_rescored} scenario(s), '
            f'restaggered {total_restaggered} timestamp(s).'
        ))
