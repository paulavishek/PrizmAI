from django.conf import settings
from django.db import migrations


class Migration(migrations.Migration):
    """
    Remove the standalone ProjectObjective model and the objectives M2M
    from Requirement.  Any existing objective data is discarded — the
    feature has been replaced by linked_goals (migration 0003).
    """

    dependencies = [
        ('requirements', '0003_add_linked_goals'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        # Drop the objectives M2M join table first
        migrations.RemoveField(
            model_name='requirement',
            name='objectives',
        ),
        # Then drop the ProjectObjective table itself
        migrations.DeleteModel(
            name='ProjectObjective',
        ),
    ]
