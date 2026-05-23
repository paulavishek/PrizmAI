from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0015_userprofile_presence_fields'),
    ]

    operations = [
        migrations.AddField(
            model_name='googlecalendartoken',
            name='last_synced_at',
            field=models.DateTimeField(
                blank=True,
                null=True,
                help_text='Timestamp of the most recent successful calendar sync.',
            ),
        ),
        migrations.AddField(
            model_name='googlecalendartoken',
            name='last_sync_error',
            field=models.TextField(
                blank=True,
                default='',
                help_text='Error message from the most recent failed sync attempt, if any.',
            ),
        ),
    ]
