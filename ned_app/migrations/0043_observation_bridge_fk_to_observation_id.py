import django.db.models.deletion
from django.db import migrations, models


def copy_bridge_observation_fks(apps, schema_editor):
    """
    Copy ObservationFragilityModelBridge.observation (old string pk) into
    observation_new (to_field='observation_id').
    """
    Observation = apps.get_model('ned_app', 'Observation')
    Bridge = apps.get_model('ned_app', 'ObservationFragilityModelBridge')

    # Old pk -> observation_id
    observation_id_of = dict(Observation.objects.values_list('id', 'observation_id'))

    bridges = list(Bridge.objects.all())
    for bridge in bridges:
        assert bridge.observation_id in observation_id_of, (
            f'Bridge {bridge.pk} points at unknown observation {bridge.observation_id}'
        )
        bridge.observation_new_id = observation_id_of[bridge.observation_id]
    Bridge.objects.bulk_update(bridges, ['observation_new'], batch_size=500)

    missing = Bridge.objects.filter(observation_new__isnull=True).count()
    assert missing == 0, f'{missing} bridges have null observation_new'


class Migration(migrations.Migration):
    dependencies = [
        ('ned_app', '0042_observation_add_observation_id'),
    ]

    operations = [
        # Step 1: Add a temporary FK pointing to Observation via observation_id
        migrations.AddField(
            model_name='observationfragilitymodelbridge',
            name='observation_new',
            field=models.ForeignKey(
                help_text='Temporary observation field for migration purposes',
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name='+',
                to='ned_app.observation',
                to_field='observation_id',
            ),
        ),
        # Step 2: Copy the links. Irreversible: no reverse_code.
        migrations.RunPython(copy_bridge_observation_fks),
        # Step 3: Remove the old FK (pointing to the string pk)
        migrations.RemoveField(
            model_name='observationfragilitymodelbridge',
            name='observation',
        ),
        # Step 4: Rename the temporary FK to its final name and make it
        # non-null
        migrations.RenameField(
            model_name='observationfragilitymodelbridge',
            old_name='observation_new',
            new_name='observation',
        ),
        migrations.AlterField(
            model_name='observationfragilitymodelbridge',
            name='observation',
            field=models.ForeignKey(
                help_text='Experiment model ID',
                on_delete=django.db.models.deletion.PROTECT,
                to='ned_app.observation',
                to_field='observation_id',
            ),
        ),
    ]
