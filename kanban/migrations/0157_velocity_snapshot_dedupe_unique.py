"""Collapse duplicate TeamVelocitySnapshot buckets and enforce uniqueness.

Demo boards had accumulated 2-3 exact-duplicate snapshots per (board, period)
because the demo date-refresh re-dated snapshots onto a grid that never matched
the predictor's update_or_create key. This migration keeps one snapshot per
(board, period_start, period_end) — the one with the highest tasks_completed
(ties broken by newest id) — deletes the rest, then adds a UniqueConstraint so
duplicates can never be created again.
"""
from django.db import migrations, models


def collapse_duplicate_snapshots(apps, schema_editor):
    TeamVelocitySnapshot = apps.get_model('kanban', 'TeamVelocitySnapshot')

    seen = {}          # (board_id, period_start, period_end) -> keeper id
    ids_to_delete = []

    # Order so the "best" row is encountered first: highest tasks_completed,
    # then newest id. The first row per period key is kept, the rest deleted.
    qs = TeamVelocitySnapshot.objects.order_by(
        'board_id', 'period_start', 'period_end', '-tasks_completed', '-id'
    ).values_list('id', 'board_id', 'period_start', 'period_end')

    for snap_id, board_id, period_start, period_end in qs.iterator():
        key = (board_id, period_start, period_end)
        if key in seen:
            ids_to_delete.append(snap_id)
        else:
            seen[key] = snap_id

    if ids_to_delete:
        # Delete in chunks to keep the SQL parameter list bounded.
        for i in range(0, len(ids_to_delete), 500):
            chunk = ids_to_delete[i:i + 500]
            TeamVelocitySnapshot.objects.filter(id__in=chunk).delete()


def noop_reverse(apps, schema_editor):
    # Deleted duplicates cannot be recovered; nothing to do on reverse.
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('kanban', '0156_task_aging_detection'),
    ]

    operations = [
        migrations.RunPython(collapse_duplicate_snapshots, noop_reverse),
        migrations.AddConstraint(
            model_name='teamvelocitysnapshot',
            constraint=models.UniqueConstraint(
                fields=['board', 'period_start', 'period_end'],
                name='uniq_velocity_board_period',
            ),
        ),
    ]
