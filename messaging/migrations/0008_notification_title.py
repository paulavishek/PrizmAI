from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('messaging', '0007_spectra_access_requests'),
    ]

    operations = [
        migrations.AddField(
            model_name='notification',
            name='title',
            field=models.CharField(
                blank=True,
                help_text='Short headline for the notification',
                max_length=255,
                null=True,
            ),
        ),
    ]
