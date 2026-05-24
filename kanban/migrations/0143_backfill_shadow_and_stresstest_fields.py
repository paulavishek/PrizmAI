"""
Backfill data migration for the schema added in 0142:

- ShadowBranch.baseline_velocity_per_week: pre-existing branches have no
  recorded baseline velocity, so live recalcs would treat them as neutral
  forever.  Compute the board's current velocity once per branch and stamp it
  in — same logic as branch-creation captures going forward.

- StressTestSession.vaccines_applied_at_run: pre-existing sessions stored 0 by
  default.  Recompute from Vaccine.applied_at timestamps where possible so
  Session History rows look correct on first load instead of waiting for the
  next run to populate.
"""
from django.db import migrations


def backfill_baseline_velocity(apps, schema_editor):
    ShadowBranch = apps.get_model('kanban', 'ShadowBranch')
    # We can't call WhatIfEngine from a migration (model proxies don't carry
    # methods), but we can derive velocity from the same data source it uses.
    BurndownPrediction = apps.get_model('kanban', 'BurndownPrediction')
    TeamVelocitySnapshot = apps.get_model('kanban', 'TeamVelocitySnapshot')

    for branch in ShadowBranch.objects.filter(baseline_velocity_per_week__isnull=True):
        velocity = 0.0
        prediction = (
            BurndownPrediction.objects
            .filter(board_id=branch.board_id)
            .order_by('-prediction_date')
            .first()
        )
        if prediction:
            velocity = float(
                prediction.average_velocity or prediction.current_velocity or 0
            )
        if not velocity:
            snaps = list(
                TeamVelocitySnapshot.objects
                .filter(board_id=branch.board_id)
                .order_by('-period_end')[:8]
            )
            if snaps:
                counts = [float(s.tasks_completed or 0) for s in snaps]
                velocity = sum(counts) / len(counts) if counts else 0.0
        # Leave NULL if we genuinely have no signal — the recalc task auto-heals
        # by snapshotting current velocity on first run.
        if velocity > 0:
            branch.baseline_velocity_per_week = round(velocity, 2)
            branch.save(update_fields=['baseline_velocity_per_week'])


def backfill_vaccines_applied_at_run(apps, schema_editor):
    StressTestSession = apps.get_model('kanban', 'StressTestSession')
    Vaccine = apps.get_model('kanban', 'Vaccine')

    for session in StressTestSession.objects.all():
        count = Vaccine.objects.filter(
            board_id=session.board_id,
            is_applied=True,
            applied_at__lte=session.created_at,
        ).count()
        if count != session.vaccines_applied_at_run:
            session.vaccines_applied_at_run = count
            session.save(update_fields=['vaccines_applied_at_run'])


def noop_reverse(apps, schema_editor):
    # Reversing the backfill would set values to 0/NULL which is the new-row
    # default already — no destructive change to undo, so a no-op is safe.
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('kanban', '0142_shadowbranch_baseline_velocity_per_week_and_more'),
    ]

    operations = [
        migrations.RunPython(backfill_baseline_velocity, noop_reverse),
        migrations.RunPython(backfill_vaccines_applied_at_run, noop_reverse),
    ]
