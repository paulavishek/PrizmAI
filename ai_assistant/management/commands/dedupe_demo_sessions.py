"""
One-time cleanup of duplicate seeded demo AI Assistant sessions.

The demo seeder used to call ``AIAssistantSession.objects.create(...)``
without dedup, so every run added another copy of each demo session
title (6x duplicates observed in the user's audit). After patching the
seeder to use ``get_or_create``, this command collapses the existing
duplicates: keep the oldest row per (user, board, title) and delete the rest.
"""

from collections import defaultdict

from django.core.management.base import BaseCommand
from django.db import transaction

from ai_assistant.models import AIAssistantSession, AIAssistantMessage


class Command(BaseCommand):
    help = 'Collapse duplicate seeded demo AI Assistant sessions.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Report which sessions would be removed without writing.',
        )

    def handle(self, *args, **opts):
        dry_run = opts['dry_run']

        # Group demo sessions by (user_id, board_id, title) — the natural identity.
        groups = defaultdict(list)
        for s in AIAssistantSession.objects.filter(is_demo=True).order_by('id'):
            key = (s.user_id, s.board_id, s.title)
            groups[key].append(s)

        dup_groups = [g for g in groups.values() if len(g) > 1]
        if not dup_groups:
            self.stdout.write(self.style.SUCCESS('No duplicate demo sessions found.'))
            return

        kept = 0
        removed = 0
        for group in dup_groups:
            # Keep the oldest (lowest id). Re-anchor any messages on the duplicates
            # to the survivor before deleting, so we never lose conversation history.
            survivor = group[0]
            for dup in group[1:]:
                if dup.message_count > survivor.message_count:
                    # Swap so we keep the row with more content as the survivor.
                    survivor, dup = dup, survivor
            for dup in group:
                if dup.id == survivor.id:
                    continue
                self.stdout.write(
                    f'  REMOVE id={dup.id} title={dup.title!r} user_id={dup.user_id} '
                    f'board_id={dup.board_id} (survivor id={survivor.id})'
                )
                if not dry_run:
                    with transaction.atomic():
                        # Reassign any messages from duplicate to survivor.
                        AIAssistantMessage.objects.filter(session=dup).update(session=survivor)
                        dup.delete()
                removed += 1
            kept += 1

        self.stdout.write(self.style.SUCCESS(
            f'\nDone. groups={len(dup_groups)} survivors={kept} removed={removed}'
            + (' (dry-run)' if dry_run else '')
        ))
