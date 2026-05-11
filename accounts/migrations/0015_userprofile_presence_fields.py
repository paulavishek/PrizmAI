from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0014_googlecalendartoken'),
    ]

    operations = [
        migrations.AddField(
            model_name='userprofile',
            name='last_seen',
            field=models.DateTimeField(
                blank=True,
                null=True,
                help_text='Last time a WebSocket heartbeat or connect/disconnect event was recorded.',
            ),
        ),
        migrations.AddField(
            model_name='userprofile',
            name='show_last_seen',
            field=models.BooleanField(
                default=True,
                help_text=(
                    "Whether other users can see this user's last-seen timestamp. "
                    "When False the timestamp is hidden for others but the user can still see others'."
                ),
            ),
        ),
    ]
