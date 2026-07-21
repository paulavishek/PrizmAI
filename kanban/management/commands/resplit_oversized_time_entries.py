"""
Split oversized demo TimeEntry rows into realistic day-sized entries.

Background
----------
``populate_all_demo_data._create_budget_and_time`` used to spread a task's whole
effort across a fixed 3-6 entries. That is fine for a small task, but a 160h
task became ~4 entries of ~25h each. Every row was individually legal — the
``hours_spent`` validator caps a single ENTRY at 16h, and nothing caps a DAY —
and the Time Tracking dashboard never showed the problem because it reports
totals rather than per-day load.

The Calendar's Time Health panel reads logged hours *per day against capacity*,
which surfaces those rows as impossible days (32h logged against 6h capacity).

The seeder and ``demo_date_refresh._refresh_time_entry_dates`` are both fixed
going forward, but existing databases still carry the oversized rows. This
command repairs them in place: each entry above ``--max-hours`` is replaced by
however many day-sized entries are needed to preserve the SAME total hours, so
budget/ROI/timesheet totals are unchanged — only the distribution differs.

Replacement entries are dated forward from the original ``work_date``, skipping
weekends, and reuse the original's task/user/description/billable flag.

Dry-run by default: pass ``--apply`` to write.
"""

from datetime import timedelta
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import Q


class Command(BaseCommand):
    help = ("Split demo TimeEntry rows logging more than a plausible day into "
            "several day-sized entries, preserving total hours (dry-run unless --apply).")

    def add_arguments(self, parser):
        parser.add_argument(
            '--apply', action='store_true',
            help='Actually write the split entries (default is a dry run).',
        )
        parser.add_argument(
            '--max-hours', type=float, default=8.0,
            help='Maximum hours a single entry may log (default: 8).',
        )
        parser.add_argument(
            '--demo-only', action='store_true', default=True,
            help='Only touch entries on demo/sandbox boards (default: on).',
        )

    def handle(self, *args, **options):
        from kanban.budget_models import TimeEntry

        apply_changes = options['apply']
        max_hours = Decimal(str(options['max_hours']))

        qs = TimeEntry.objects.filter(hours_spent__gt=max_hours)
        if options['demo_only']:
            # Demo/sandbox boards only — never rewrite a real user's hand-logged
            # timesheet, which may legitimately record a long day.
            qs = qs.filter(
                Q(task__column__board__is_sandbox_copy=True) |
                Q(task__column__board__is_official_demo_board=True)
            )
        qs = qs.select_related('task', 'task__column__board').distinct()

        oversized = list(qs)
        if not oversized:
            self.stdout.write(self.style.SUCCESS(
                f'No entries above {max_hours}h — nothing to do.'
            ))
            return

        total_before = sum(e.hours_spent for e in oversized)
        created_count = 0
        plan = []

        for entry in oversized:
            # How many day-sized entries this effort really needs.
            parts = int((entry.hours_spent / max_hours).to_integral_value(rounding='ROUND_CEILING'))
            parts = max(parts, 2)
            per = (entry.hours_spent / parts).quantize(Decimal('0.01'))
            # Give the remainder to the first entry so the sum is EXACT — the
            # whole point is that budget/ROI totals do not move.
            remainder = entry.hours_spent - (per * parts)
            amounts = [per] * parts
            amounts[0] = (amounts[0] + remainder).quantize(Decimal('0.01'))

            dates = []
            day = entry.work_date
            for _ in range(parts):
                while day.weekday() >= 5:      # keep logged work on weekdays
                    day += timedelta(days=1)
                dates.append(day)
                day += timedelta(days=1)

            plan.append((entry, amounts, dates))
            created_count += parts

        if not apply_changes:
            self.stdout.write(self.style.WARNING(
                f'DRY RUN — {len(oversized)} entries above {max_hours}h would '
                f'become {created_count} entries.'
            ))
            for entry, amounts, dates in plan[:10]:
                self.stdout.write(
                    f'  {entry.work_date} {float(entry.hours_spent):.2f}h '
                    f'"{entry.task.title[:34]}" -> '
                    + ', '.join(
                        f'{d} {float(a):.2f}h' for a, d in zip(amounts, dates)
                    )
                )
            if len(plan) > 10:
                self.stdout.write(f'  ... and {len(plan) - 10} more')
            self.stdout.write(f'Total hours preserved: {float(total_before):.2f}')
            self.stdout.write('Re-run with --apply to write.')
            return

        with transaction.atomic():
            for entry, amounts, dates in plan:
                for amount, work_date in zip(amounts, dates):
                    TimeEntry.objects.create(
                        task=entry.task,
                        user=entry.user,
                        hours_spent=amount,
                        work_date=work_date,
                        description=entry.description,
                        is_billable=entry.is_billable,
                    )
                entry.delete()

        total_after = sum(
            e.hours_spent for e in TimeEntry.objects.filter(
                task__in=[e.task for e, _, _ in plan]
            )
        )
        self.stdout.write(self.style.SUCCESS(
            f'[OK] Split {len(oversized)} oversized entries into {created_count} '
            f'day-sized entries.'
        ))
        self.stdout.write(
            f'     Hours on affected tasks now total {float(total_after):.2f} '
            f'(was {float(total_before):.2f} across the split rows).'
        )
