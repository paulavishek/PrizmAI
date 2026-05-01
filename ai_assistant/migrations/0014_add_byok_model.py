from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('ai_assistant', '0013_organizationaisettings_useraisettings'),
    ]

    operations = [
        migrations.AddField(
            model_name='organizationaisettings',
            name='byok_model',
            field=models.CharField(
                blank=True,
                help_text=(
                    "Model to use when a BYOK key is active. If null, the router falls back "
                    "to the complexity-based platform defaults (GEMINI_MODEL_COMPLEX/SIMPLE etc.). "
                    "Store the exact model string e.g. 'claude-sonnet-4-6', 'gpt-4o', 'gemini-2.5-pro'."
                ),
                max_length=100,
                null=True,
            ),
        ),
        migrations.AddField(
            model_name='useraisettings',
            name='byok_model',
            field=models.CharField(
                blank=True,
                help_text=(
                    "Model to use when a personal BYOK key is active. If null, the router falls back "
                    "to the complexity-based platform defaults (GEMINI_MODEL_COMPLEX/SIMPLE etc.). "
                    "Store the exact model string e.g. 'claude-sonnet-4-6', 'gpt-4o', 'gemini-2.5-flash'."
                ),
                max_length=100,
                null=True,
            ),
        ),
    ]
