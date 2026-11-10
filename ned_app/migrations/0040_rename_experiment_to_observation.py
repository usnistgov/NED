from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ('ned_app', '0039_specimen_test'),
    ]

    # Hand-written: makemigrations offers Delete + Create for both models (and
    # recreates the bridge because its FK is renamed at the same time), which
    # would empty the tables. RenameModel and RenameField keep every row. The
    # canonical JSON in resources/data/ is then regenerated from the migrated
    # database via `export_data`, never hand-edited.
    operations = [
        migrations.RenameModel(
            old_name='Experiment',
            new_name='Observation',
        ),
        migrations.RenameModel(
            old_name='ExperimentFragilityModelBridge',
            new_name='ObservationFragilityModelBridge',
        ),
        migrations.RenameField(
            model_name='observationfragilitymodelbridge',
            old_name='experiment',
            new_name='observation',
        ),
    ]
