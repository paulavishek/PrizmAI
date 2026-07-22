from django.db import migrations


def backfill_gap_questions_original(apps, schema_editor):
    """Adopt existing gap_questions as the canonical checklist.

    Memories flagged before anchored progressive tracking (migration 0005) have
    no gap_questions_original, so the completeness progress bar is suppressed for
    them. Seed it from their current gap_questions so the bar works for already-
    flagged memories, matching the lazy backfill in edit_manual_memory.
    """
    MemoryNode = apps.get_model('knowledge_graph', 'MemoryNode')
    for node in MemoryNode.objects.filter(
        gap_questions_original__isnull=True, gap_questions__isnull=False
    ):
        node.gap_questions_original = node.gap_questions
        node.save(update_fields=['gap_questions_original'])


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('knowledge_graph', '0005_memorynode_gap_questions_original'),
    ]

    operations = [
        migrations.RunPython(backfill_gap_questions_original, noop_reverse),
    ]
