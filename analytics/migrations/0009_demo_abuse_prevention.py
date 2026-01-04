# Generated migration for DemoAbusePrevention model
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('analytics', '0008_demosession_browser_fingerprint_and_more'),
    ]

    operations = [
        migrations.CreateModel(
            name='DemoAbusePrevention',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('ip_address', models.GenericIPAddressField(db_index=True)),
                ('browser_fingerprint', models.CharField(blank=True, db_index=True, help_text='SHA256 hash of browser attributes', max_length=64, null=True)),
                ('total_ai_generations', models.IntegerField(default=0, help_text='Total AI generations across all demo sessions')),
                ('total_projects_created', models.IntegerField(default=0, help_text='Total projects created across all demo sessions')),
                ('total_export_attempts', models.IntegerField(default=0, help_text='Total export attempts across all demo sessions')),
                ('total_sessions_created', models.IntegerField(default=1, help_text='Number of demo sessions created from this IP')),
                ('is_flagged', models.BooleanField(default=False, help_text='Flagged for suspicious activity')),
                ('flag_reason', models.TextField(blank=True, help_text='Reason for flagging')),
                ('is_blocked', models.BooleanField(default=False, help_text='Blocked from demo access')),
                ('first_seen', models.DateTimeField(auto_now_add=True)),
                ('last_seen', models.DateTimeField(auto_now=True)),
                ('last_session_created', models.DateTimeField(blank=True, help_text='When the last demo session was started', null=True)),
                ('sessions_last_hour', models.IntegerField(default=0, help_text='Sessions created in the last hour (for rate limiting)')),
                ('sessions_last_24h', models.IntegerField(default=0, help_text='Sessions created in the last 24 hours')),
                ('last_rate_limit_reset', models.DateTimeField(blank=True, help_text='When rate limit counters were last reset', null=True)),
                ('session_ids', models.JSONField(blank=True, default=list, help_text='List of all session IDs from this IP/fingerprint')),
            ],
            options={
                'verbose_name': 'Demo Abuse Prevention',
                'verbose_name_plural': 'Demo Abuse Prevention Records',
            },
        ),
        migrations.AddIndex(
            model_name='demoabuseprevention',
            index=models.Index(fields=['ip_address', 'browser_fingerprint'], name='analytics_d_ip_addr_abuse_idx'),
        ),
        migrations.AddIndex(
            model_name='demoabuseprevention',
            index=models.Index(fields=['is_flagged'], name='analytics_d_is_flag_idx'),
        ),
        migrations.AddIndex(
            model_name='demoabuseprevention',
            index=models.Index(fields=['is_blocked'], name='analytics_d_is_bloc_idx'),
        ),
        migrations.AddIndex(
            model_name='demoabuseprevention',
            index=models.Index(fields=['last_seen'], name='analytics_d_last_se_idx'),
        ),
        migrations.AddConstraint(
            model_name='demoabuseprevention',
            constraint=models.UniqueConstraint(fields=['ip_address', 'browser_fingerprint'], name='unique_ip_fingerprint'),
        ),
    ]
