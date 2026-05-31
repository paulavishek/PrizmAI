"""
Delete stale PrizmAI-synced events from a user's Google Calendar.

Removes every event carrying the PrizmAI marker — including *orphaned* events
whose Task pointer was lost during a demo reset — and clears the matching
``Task.google_calendar_event_id`` rows so the DB and the calendar agree again.

Examples:
    # Preview what would be deleted for one user (no changes made)
    python manage.py purge_calendar_events --user testuser1 --dry-run

    # Actually delete them
    python manage.py purge_calendar_events --user testuser1

    # Look the user up by email instead of username
    python manage.py purge_calendar_events --user paul.biotech10@gmail.com

    # Every connected user
    python manage.py purge_calendar_events --all
"""
from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth import get_user_model
from django.db.models import Q

from accounts.models import GoogleCalendarToken
from accounts.tasks import purge_calendar_events_for_user

User = get_user_model()


class Command(BaseCommand):
    help = "Delete stale PrizmAI-synced events from connected Google Calendars."

    def add_arguments(self, parser):
        parser.add_argument(
            '--user',
            help='Username or email of the user whose calendar to purge.',
        )
        parser.add_argument(
            '--all',
            action='store_true',
            help='Purge every user that has a calendar connection.',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be deleted without deleting anything.',
        )

    def handle(self, *args, **options):
        user_arg = options.get('user')
        do_all = options.get('all')
        dry_run = options.get('dry_run')

        if not user_arg and not do_all:
            raise CommandError("Provide --user <username|email> or --all.")
        if user_arg and do_all:
            raise CommandError("Use either --user or --all, not both.")

        if do_all:
            user_ids = list(
                GoogleCalendarToken.objects.values_list('user_id', flat=True)
            )
            if not user_ids:
                self.stdout.write("No calendar connections found.")
                return
        else:
            try:
                user = User.objects.get(
                    Q(username=user_arg) | Q(email__iexact=user_arg)
                )
            except User.DoesNotExist:
                raise CommandError(f"No user matching '{user_arg}'.")
            except User.MultipleObjectsReturned:
                raise CommandError(
                    f"'{user_arg}' matches multiple users; use the username."
                )
            user_ids = [user.id]

        if dry_run:
            self.stdout.write(self.style.WARNING("DRY RUN — nothing will be deleted.\n"))

        totals = {'found': 0, 'deleted': 0, 'failed': 0, 'cleared': 0}
        for uid in user_ids:
            uname = (
                User.objects.filter(pk=uid).values_list('username', flat=True).first()
                or uid
            )
            try:
                r = purge_calendar_events_for_user(uid, dry_run=dry_run)
            except Exception as e:
                self.stderr.write(self.style.ERROR(f"  {uname}: error — {e}"))
                continue

            for k in totals:
                totals[k] += r.get(k, 0)

            verb = 'would delete' if dry_run else 'deleted'
            self.stdout.write(
                f"  {uname}: found {r['found']}, {verb} {r['deleted']}, "
                f"failed {r['failed']}, cleared {r['cleared']} task pointer(s)"
            )

        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS(
            f"Total: found {totals['found']}, "
            f"{'would delete' if dry_run else 'deleted'} {totals['deleted']}, "
            f"failed {totals['failed']}, cleared {totals['cleared']}"
        ))
