"""
Backfill embeddings for existing ProjectKnowledgeBase rows.

Usage:
    python manage.py backfill_kb_embeddings              # all rows missing embeddings
    python manage.py backfill_kb_embeddings --limit 50   # only embed 50 rows
    python manage.py backfill_kb_embeddings --reembed    # re-generate even if present
    python manage.py backfill_kb_embeddings --board 42   # restrict to one board

Rate-limited: 200 ms between calls to stay well under Gemini's per-minute
embedding quota. Cache hits skip the API call entirely.
"""

import time

from django.core.management.base import BaseCommand
from django.utils import timezone


class Command(BaseCommand):
    help = 'Backfill or refresh KB embeddings via Gemini text-embedding-004.'

    def add_arguments(self, parser):
        parser.add_argument('--limit', type=int, default=None,
                            help='Maximum rows to process this run.')
        parser.add_argument('--reembed', action='store_true',
                            help='Re-generate embeddings even if already present.')
        parser.add_argument('--board', type=int, default=None,
                            help='Restrict to a single board id.')
        parser.add_argument('--sleep-ms', type=int, default=200,
                            help='Sleep between API calls in milliseconds.')

    def handle(self, *args, **opts):
        from ai_assistant.models import ProjectKnowledgeBase
        from ai_assistant.utils.ai_clients import embed_text, GEMINI_EMBEDDING_MODEL

        qs = ProjectKnowledgeBase.objects.filter(is_active=True)
        if opts['board']:
            qs = qs.filter(board_id=opts['board'])
        if not opts['reembed']:
            qs = qs.filter(embedding__isnull=True)
        if opts['limit']:
            qs = qs[:opts['limit']]

        total = qs.count()
        if total == 0:
            self.stdout.write(self.style.SUCCESS('Nothing to backfill.'))
            return

        self.stdout.write(f'Backfilling embeddings for {total} KB rows…')
        ok = 0
        skipped = 0
        sleep_s = max(0, opts['sleep_ms']) / 1000.0

        for i, row in enumerate(qs.iterator(), start=1):
            text = f'{row.title}\n\n{row.content or ""}'.strip()
            if not text:
                skipped += 1
                continue
            vec = embed_text(text, task_type='RETRIEVAL_DOCUMENT')
            if not vec:
                skipped += 1
                self.stdout.write(self.style.WARNING(
                    f'  [{i}/{total}] id={row.pk}: embed_text returned None'
                ))
                continue
            ProjectKnowledgeBase.objects.filter(pk=row.pk).update(
                embedding=vec,
                embedding_model=GEMINI_EMBEDDING_MODEL,
                embedding_updated_at=timezone.now(),
            )
            ok += 1
            if i % 10 == 0:
                self.stdout.write(f'  [{i}/{total}] ok={ok} skipped={skipped}')
            if sleep_s:
                time.sleep(sleep_s)

        self.stdout.write(self.style.SUCCESS(
            f'Done. Embedded {ok}/{total} rows. Skipped {skipped}.'
        ))
