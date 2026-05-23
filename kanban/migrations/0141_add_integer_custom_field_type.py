from django.db import migrations, models


class Migration(migrations.Migration):
    """
    Adds 'integer' to FIELD_TYPE_CHOICES on CustomFieldDefinition.

    CharField choices are Django-level validation only — no DB column change is
    needed. SeparateDatabaseAndState records the change in Django's migration
    state without issuing any SQL, which avoids SQLite's full-table-rewrite on
    AlterField and its associated constraint checks.
    """

    dependencies = [
        ('kanban', '0140_alter_scopetimelineevent_source_type'),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[],
            state_operations=[
                migrations.AlterField(
                    model_name='customfielddefinition',
                    name='field_type',
                    field=models.CharField(
                        max_length=20,
                        choices=[
                            ('text', 'Text'),
                            ('long_text', 'Long Text'),
                            ('number', 'Number'),
                            ('integer', 'Integer'),
                            ('date', 'Date'),
                            ('boolean', 'Boolean'),
                            ('list', 'List'),
                        ],
                    ),
                ),
            ],
        ),
    ]
