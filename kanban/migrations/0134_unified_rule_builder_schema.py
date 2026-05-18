import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('kanban', '0133_rename_kanban_task_board_i_reason_idx_kanban_task_board_i_c18196_idx'),
    ]

    operations = [
        # ── AutomationRule: shrink name, add new flat fields ──────────────────
        migrations.AlterField(
            model_name='automationrule',
            name='name',
            field=models.CharField(max_length=120),
        ),
        migrations.AddField(
            model_name='automationrule',
            name='trigger_config',
            field=models.JSONField(default=dict),
        ),
        migrations.AddField(
            model_name='automationrule',
            name='condition_logic',
            field=models.CharField(
                choices=[('AND', 'AND'), ('OR', 'OR')],
                default='AND',
                max_length=3,
            ),
        ),
        migrations.AddField(
            model_name='automationrule',
            name='conditions',
            field=models.JSONField(default=list),
        ),
        migrations.AddField(
            model_name='automationrule',
            name='actions',
            field=models.JSONField(default=list),
        ),
        migrations.AddField(
            model_name='automationrule',
            name='otherwise_actions',
            field=models.JSONField(default=list),
        ),
        migrations.AddField(
            model_name='automationrule',
            name='updated_at',
            field=models.DateTimeField(auto_now=True),
        ),
        migrations.AddField(
            model_name='automationrule',
            name='last_execution_result',
            field=models.CharField(blank=True, max_length=10, null=True),
        ),
        migrations.AlterModelOptions(
            name='automationrule',
            options={'ordering': ['-created_at']},
        ),
        migrations.AddIndex(
            model_name='automationrule',
            index=models.Index(
                fields=['board', 'is_active', 'trigger_type'],
                name='kanban_auto_board_i_trigtype_idx',
            ),
        ),

        # ── AutomationLog: new outcome choices, new fields ────────────────────
        migrations.AlterField(
            model_name='automationlog',
            name='outcome',
            field=models.CharField(
                choices=[
                    ('success', 'Success'),
                    ('skipped', 'Skipped'),
                    ('failed',  'Failed'),
                ],
                db_index=True,
                max_length=10,
            ),
        ),
        migrations.AddField(
            model_name='automationlog',
            name='rule_name_snapshot',
            field=models.CharField(blank=True, max_length=120),
        ),
        migrations.AddField(
            model_name='automationlog',
            name='board',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name='automation_logs',
                to='kanban.board',
            ),
        ),
        migrations.AddField(
            model_name='automationlog',
            name='task_title_snapshot',
            field=models.CharField(blank=True, max_length=255),
        ),
        migrations.AddField(
            model_name='automationlog',
            name='skip_reason',
            field=models.CharField(blank=True, max_length=100),
        ),
        migrations.AddField(
            model_name='automationlog',
            name='execution_detail',
            field=models.JSONField(default=dict),
        ),
        migrations.AddIndex(
            model_name='automationlog',
            index=models.Index(
                fields=['board', 'triggered_at'],
                name='kanban_autolog_board_time_idx',
            ),
        ),
        migrations.AddIndex(
            model_name='automationlog',
            index=models.Index(
                fields=['rule', 'triggered_at'],
                name='kanban_autolog_rule_time_idx',
            ),
        ),

        # ── AutomationTemplate: add flat format fields ────────────────────────
        migrations.AlterField(
            model_name='automationtemplate',
            name='rule_definition',
            field=models.JSONField(
                blank=True,
                null=True,
                help_text='Deprecated canvas block tree — kept for rollback safety.',
            ),
        ),
        migrations.AddField(
            model_name='automationtemplate',
            name='trigger_config',
            field=models.JSONField(default=dict),
        ),
        migrations.AddField(
            model_name='automationtemplate',
            name='condition_logic',
            field=models.CharField(default='AND', max_length=3),
        ),
        migrations.AddField(
            model_name='automationtemplate',
            name='conditions',
            field=models.JSONField(default=list),
        ),
        migrations.AddField(
            model_name='automationtemplate',
            name='actions',
            field=models.JSONField(default=list),
        ),
    ]
