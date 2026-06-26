from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


def backfill_aging(apps, schema_editor):
    """Set sensible defaults for existing data:
    - Disable aging on Done/Backlog-style columns (matched by name).
    - Backfill Task.column_entered_at where NULL using updated_at (fallback created_at)
      so long-untouched tasks immediately show a realistic age rather than resetting to zero.
    """
    Column = apps.get_model('kanban', 'Column')
    Task = apps.get_model('kanban', 'Task')

    # Keep this list in sync with kanban.models.AGING_DISABLED_NAME_KEYWORDS.
    keywords = (
        'done', 'complete', 'closed', 'backlog', 'archive',
        'shipped', 'deployed', 'released', 'cancelled', 'canceled',
    )
    for col in Column.objects.all().iterator():
        low = (col.name or '').lower()
        if any(kw in low for kw in keywords):
            col.aging_mode = 'disabled'
            col.save(update_fields=['aging_mode'])

    for task in Task.objects.filter(column_entered_at__isnull=True).iterator():
        task.column_entered_at = task.updated_at or task.created_at
        # Avoid triggering auto_now on updated_at via a targeted update.
        Task.objects.filter(pk=task.pk).update(column_entered_at=task.column_entered_at)


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('kanban', '0155_alter_organizationlearningprofile_options_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='board',
            name='aging_enabled',
            field=models.BooleanField(default=True, help_text='Show task-aging badges on this board (per-column overrides still apply).'),
        ),
        migrations.AddField(
            model_name='board',
            name='aging_warning_days',
            field=models.PositiveSmallIntegerField(default=7, help_text='Days a task can sit in a column before its aging badge turns amber (warning).'),
        ),
        migrations.AddField(
            model_name='board',
            name='aging_critical_days',
            field=models.PositiveSmallIntegerField(default=14, help_text='Days a task can sit in a column before its aging badge turns red (critical).'),
        ),
        migrations.AddField(
            model_name='board',
            name='aging_configured',
            field=models.BooleanField(default=False, help_text='True once anyone has saved aging settings on this board; suppresses the one-time onboarding tooltip.'),
        ),
        migrations.AddField(
            model_name='column',
            name='aging_mode',
            field=models.CharField(choices=[('inherit', 'Use board defaults'), ('custom', 'Custom for this column'), ('disabled', 'Disabled')], default='inherit', help_text='How aging badges behave for this column: inherit board defaults, custom thresholds, or disabled.', max_length=10),
        ),
        migrations.AddField(
            model_name='column',
            name='aging_warning_days',
            field=models.PositiveSmallIntegerField(blank=True, help_text="Custom warning (amber) threshold in days; used only when aging_mode='custom'.", null=True),
        ),
        migrations.AddField(
            model_name='column',
            name='aging_critical_days',
            field=models.PositiveSmallIntegerField(blank=True, help_text="Custom critical (red) threshold in days; used only when aging_mode='custom'.", null=True),
        ),
        migrations.CreateModel(
            name='AgingOnboardingDismissal',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('dismissed_at', models.DateTimeField(auto_now_add=True)),
                ('board', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='aging_onboarding_dismissals', to='kanban.board')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='aging_onboarding_dismissals', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'unique_together': {('user', 'board')},
            },
        ),
        migrations.RunPython(backfill_aging, noop_reverse),
    ]
