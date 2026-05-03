# Generated manually on 2026-05-03

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('analytics', '0013_remove_demo_session_expiry_fields'),
    ]

    operations = [
        migrations.CreateModel(
            name='DemoEmailCapture',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('session_id', models.CharField(db_index=True, max_length=255)),
                ('demo_session', models.ForeignKey(
                    blank=True,
                    help_text='Associated demo session (nullable in case session is later deleted)',
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='email_captures',
                    to='analytics.demosession',
                )),
                ('email', models.EmailField(max_length=254)),
                ('captured_at', models.DateTimeField(auto_now_add=True)),
            ],
            options={
                'verbose_name': 'Demo Email Capture',
                'verbose_name_plural': 'Demo Email Captures',
                'ordering': ['-captured_at'],
                'indexes': [
                    models.Index(fields=['captured_at'], name='analytics_d_capture_idx'),
                ],
            },
        ),
    ]
