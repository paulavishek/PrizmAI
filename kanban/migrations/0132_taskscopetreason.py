from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('kanban', '0131_boardstatusreport_history'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='TaskScopeReason',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('reason', models.CharField(
                    choices=[
                        ('requirement_change', 'Requirement Change'),
                        ('stakeholder_request', 'Stakeholder Request'),
                        ('discovered_complexity', 'Discovered Complexity'),
                        ('gold_plating', 'Gold Plating'),
                        ('initial_planning', 'Initial Planning'),
                        ('other', 'Other'),
                        ('unrecorded', 'Unrecorded'),
                    ],
                    default='unrecorded',
                    max_length=50,
                )),
                ('note', models.TextField(blank=True)),
                ('recorded_at', models.DateTimeField(auto_now_add=True)),
                ('board', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='task_scope_reasons',
                    to='kanban.board',
                )),
                ('recorded_by', models.ForeignKey(
                    blank=True,
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    to=settings.AUTH_USER_MODEL,
                )),
                ('task', models.OneToOneField(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='scope_reason',
                    to='kanban.task',
                )),
            ],
            options={
                'indexes': [
                    models.Index(fields=['board', 'reason'], name='kanban_task_board_i_reason_idx'),
                ],
            },
        ),
    ]
