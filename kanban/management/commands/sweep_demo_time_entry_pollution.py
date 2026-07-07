"""
Sweep real-user TimeEntry pollution off demo boards the user does not own.

Background
----------
The time-tracking dashboard is a *personal* timesheet filtered by
``user=request.user`` and scoped to the user's own sandbox boards. Demo time
entries are seeded persona-owned and cloned per user by ``_duplicate_board``,
which remaps ``priya.sharma``'s rows to the sandbox owner.

If a real user ever comes to own ``TimeEntry`` rows on the **official template
board** (invariant violation — see ``project_demo_reset_official_board_invariants``),
``_duplicate_board`` used to clone those rows verbatim into every new sandbox as
that user's own, inflating their Total Hours on every reset (e.g. one user
showing 327h while others show 181h). The clone is now guarded to copy only
persona-owned rows, and reset self-heals the resetting user, but existing
databases still carry the stray rows on the template board and on *other* users'
sandbox copies. This command removes that pre-existing pollution.

A "real user" is any account whose email is not on the ``@demo.prizmai.local``
domain — the reliable persona test, since the ``is_demo_account`` flag is only
set for the priya/elena/marcus team, not the alex/sam/jordan persona team.

It deletes real-user TimeEntry rows that sit on a board the user does **not**
own:
  * on any ``is_official_demo_board=True`` board, and
  * on any ``is_sandbox_copy=True`` board whose ``owner`` is not the entry's user.

Self-logged entries on the user's own sandbox board (``board.owner == user``) and
all persona-owned seed entries are preserved.

Dry-run by default: pass ``--apply`` to actually delete.
"""

from django.core.management.base import BaseCommand
from django.db.models import F


class Command(BaseCommand):
    help = ("Delete real-user TimeEntry rows polluting official demo boards or "
            "other users' sandbox copies (dry-run unless --apply).")

    def add_arguments(self, parser):
        parser.add_argument(
            '--apply',
            action='store_true',
            help='Actually delete. Without this flag the command only reports counts.',
        )

    def handle(self, *args, **options):
        from kanban.budget_models import TimeEntry

        apply = options['apply']

        _PERSONA_DOMAIN = '@demo.prizmai.local'

        # Real user (non-persona email) owning entries on the official template board.
        official = TimeEntry.objects.filter(
            task__column__board__is_official_demo_board=True,
        ).exclude(user__email__iendswith=_PERSONA_DOMAIN)

        # Real user owning entries on a sandbox copy that is NOT theirs.
        cross = TimeEntry.objects.filter(
            task__column__board__is_sandbox_copy=True,
        ).exclude(
            user__email__iendswith=_PERSONA_DOMAIN,
        ).exclude(
            task__column__board__owner=F('user'),
        )

        targets = [
            ('official-template pollution', official),
            ('cross-owner sandbox pollution', cross),
        ]

        total = 0
        for label, qs in targets:
            # Per-user breakdown for transparency before any delete.
            breakdown = (
                qs.values('user__username',
                          'task__column__board_id',
                          'task__column__board__name')
                  .order_by()
            )
            from django.db.models import Count, Sum
            rows = breakdown.annotate(n=Count('id'), h=Sum('hours_spent')).order_by('-n')
            count = qs.count()
            total += count
            if count == 0:
                self.stdout.write(f'  {label}: 0 (clean)')
                continue
            self.stdout.write(self.style.WARNING(f'  {label}: {count} rows'))
            for r in rows:
                self.stdout.write(
                    f"      user={r['user__username']} "
                    f"board={r['task__column__board_id']} "
                    f"({r['task__column__board__name']}): "
                    f"{r['n']} rows, {r['h']}h"
                )
            if apply:
                deleted, _ = qs.delete()
                self.stdout.write(self.style.SUCCESS(f'    deleted {count} rows'))

        if total == 0:
            self.stdout.write(self.style.SUCCESS('No demo time-entry pollution found — database is clean.'))
        elif not apply:
            self.stdout.write(self.style.WARNING(
                f'Total pollution rows: {total} (dry run — nothing deleted; re-run with --apply).'))
        else:
            self.stdout.write(self.style.SUCCESS(f'Swept {total} polluting time-entry rows.'))
