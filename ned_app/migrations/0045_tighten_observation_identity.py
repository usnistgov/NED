import django.db.models.deletion
import django.db.models.functions.text
import ned_app.validators
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('ned_app', '0044_swap_observation_pk'),
    ]

    operations = [
        # The swap (0042-0045) is irreversible: roll back by reverting and
        # rebuilding from JSON. This no-op has no reverse_code, so reversing
        # raises IrreversibleError here, before anything changes, rather than
        # failing partway through 0044.
        migrations.RunPython(migrations.RunPython.noop),
        # Step 1: Make observation_id non-nullable
        migrations.AlterField(
            model_name='observation',
            name='observation_id',
            field=models.CharField(
                editable=False,
                help_text="Derived: '{test_id}|{label}'.",
                max_length=255,
                unique=True,
                verbose_name='observation id',
            ),
        ),
        # Step 2: Require test and label
        migrations.AlterField(
            model_name='observation',
            name='test',
            field=models.ForeignKey(
                help_text='The test this observation belongs to.',
                on_delete=django.db.models.deletion.PROTECT,
                to='ned_app.test',
                to_field='test_id',
            ),
        ),
        migrations.AlterField(
            model_name='observation',
            name='label',
            field=models.CharField(
                help_text='Identifier within the test; observations are ordered by label.',
                max_length=100,
                validators=[ned_app.validators.validate_label],
                verbose_name='label',
            ),
        ),
        # Step 3: Labels are unique within a test, regardless of case
        migrations.AddConstraint(
            model_name='observation',
            constraint=models.UniqueConstraint(
                django.db.models.functions.text.Lower('label'),
                models.F('test'),
                name='observation_label_ci_unique_in_test',
            ),
        ),
    ]
