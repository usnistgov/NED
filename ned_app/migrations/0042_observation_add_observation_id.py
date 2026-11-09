from django.db import migrations, models


def populate_observation_id(apps, schema_editor):
    """
    Derive Observation.observation_id as '{test_id}|{label}'.

    Historical models don't run the custom save(), so the id is computed here.
    Every observation must already have a test and a label (Stage 8).
    """
    Observation = apps.get_model('ned_app', 'Observation')

    observations = list(Observation.objects.all())
    for obs in observations:
        assert obs.test_id, f'Observation {obs.pk} has no test'
        assert obs.label, f'Observation {obs.pk} has no label'
        obs.observation_id = f'{obs.test_id}|{obs.label}'
    Observation.objects.bulk_update(observations, ['observation_id'], batch_size=500)

    missing = Observation.objects.filter(observation_id__isnull=True).count()
    assert missing == 0, f'{missing} observations have no observation_id'


class Migration(migrations.Migration):
    dependencies = [
        ('ned_app', '0041_observation_test_label_damage_location'),
    ]

    operations = [
        # Step 1: Add observation_id (nullable until populated, then tightened
        # in 0045).
        migrations.AddField(
            model_name='observation',
            name='observation_id',
            field=models.CharField(
                editable=False,
                help_text="Derived: '{test_id}|{label}'.",
                max_length=255,
                null=True,
                unique=True,
                verbose_name='observation id',
            ),
        ),
        # Step 2: Populate it. Irreversible: no reverse_code, so reversing
        # raises IrreversibleError. Roll back by reverting and rebuilding from
        # JSON.
        migrations.RunPython(populate_observation_id),
    ]
