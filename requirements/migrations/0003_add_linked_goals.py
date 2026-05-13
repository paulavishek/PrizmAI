from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('requirements', '0002_add_ai_cache_and_history_choices'),
        ('kanban', '0072_add_organization_goal_model'),
    ]

    operations = [
        migrations.AddField(
            model_name='requirement',
            name='linked_goals',
            field=models.ManyToManyField(
                blank=True,
                related_name='linked_requirements',
                to='kanban.organizationgoal',
            ),
        ),
    ]
