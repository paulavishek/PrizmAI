# Generated manually on 2026-05-03
# Replaces unique_together on DemoAbusePrevention with two partial UniqueConstraints:
#   1. Unique (ip_address, browser_fingerprint) when fingerprint is NOT NULL
#   2. Unique ip_address when fingerprint IS NULL
# This fixes the SQL NULL != NULL bug where multiple rows with the same IP
# and NULL fingerprint could be created, fragmenting rate-limit counters.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('analytics', '0014_add_demo_email_capture'),
    ]

    operations = [
        # Remove the old unique_together constraint
        migrations.AlterUniqueTogether(
            name='demoabuseprevention',
            unique_together=set(),
        ),
        # Add partial constraint: unique (ip, fingerprint) when fingerprint is known
        migrations.AddConstraint(
            model_name='demoabuseprevention',
            constraint=models.UniqueConstraint(
                fields=['ip_address', 'browser_fingerprint'],
                condition=models.Q(browser_fingerprint__isnull=False),
                name='unique_ip_fingerprint_when_set',
            ),
        ),
        # Add partial constraint: unique ip when fingerprint is absent
        migrations.AddConstraint(
            model_name='demoabuseprevention',
            constraint=models.UniqueConstraint(
                fields=['ip_address'],
                condition=models.Q(browser_fingerprint__isnull=True),
                name='unique_ip_when_no_fingerprint',
            ),
        ),
    ]
