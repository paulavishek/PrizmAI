"""
One-time management command to reset all SpectraConversationState records
that are stuck in a non-normal (action-collecting) mode back to 'normal'.

With v1.0 disabling all action flows, any leftover state from prior
sessions would cause confusing behaviour until the user's state naturally
times out. Running this once ensures a clean slate.

Usage:
    python manage.py reset_stale_spectra_states          # dry-run
    python manage.py reset_stale_spectra_states --apply   # actually reset
"""
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Reset all non-normal SpectraConversationState rows to 'normal' mode."

    def add_arguments(self, parser):
        parser.add_argument(
            '--apply',
            action='store_true',
            help='Actually perform the reset (default is dry-run).',
        )

    def handle(self, *args, **options):
        from ai_assistant.models import SpectraConversationState

        stale = SpectraConversationState.objects.exclude(mode='normal')
        count = stale.count()

        if count == 0:
            self.stdout.write(self.style.SUCCESS('No stale states found. Nothing to do.'))
            return

        self.stdout.write(f'Found {count} stale conversation state(s):')
        for s in stale[:20]:
            self.stdout.write(
                f'  {s.user.username} | board={s.board} | mode={s.mode} '
                f'| pending={s.pending_action} | updated={s.updated_at}'
            )
        if count > 20:
            self.stdout.write(f'  ... and {count - 20} more')

        if not options['apply']:
            self.stdout.write(self.style.WARNING('Dry-run. Pass --apply to reset these rows.'))
            return

        updated = stale.update(mode='normal', collected_data={}, pending_action='')
        self.stdout.write(self.style.SUCCESS(f'Reset {updated} row(s) to normal mode.'))
