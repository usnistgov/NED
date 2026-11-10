from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ('ned_app', '0045_tighten_observation_identity'),
    ]

    operations = [
        # Step 1: Keep the three per-observation fields under legacy_ names.
        # Hand-written: makemigrations offers these as remove + add, which
        # loses the values; RenameField renames the column in place.
        migrations.RenameField(
            model_name='observation',
            old_name='ds_rank',
            new_name='legacy_ds_rank',
        ),
        migrations.RenameField(
            model_name='observation',
            old_name='prior_damage',
            new_name='legacy_prior_damage',
        ),
        migrations.RenameField(
            model_name='observation',
            old_name='prior_damage_repaired',
            new_name='legacy_prior_damage_repaired',
        ),
        # Step 2: Drop the fields that moved to Specimen, Test and Facility
        # (the reference now comes from the specimen or its program).
        migrations.RemoveField(model_name='observation', name='reference'),
        migrations.RemoveField(model_name='observation', name='specimen'),
        migrations.RemoveField(
            model_name='observation', name='specimen_inspection_sequence'
        ),
        migrations.RemoveField(model_name='observation', name='contributor'),
        migrations.RemoveField(model_name='observation', name='component'),
        migrations.RemoveField(model_name='observation', name='comp_detail'),
        migrations.RemoveField(model_name='observation', name='material'),
        migrations.RemoveField(model_name='observation', name='size_class'),
        migrations.RemoveField(model_name='observation', name='test_type'),
        migrations.RemoveField(model_name='observation', name='loading_protocol'),
        migrations.RemoveField(model_name='observation', name='peak_test_amplitude'),
        migrations.RemoveField(model_name='observation', name='location'),
        migrations.RemoveField(
            model_name='observation', name='governing_design_standard'
        ),
        migrations.RemoveField(model_name='observation', name='design_objective'),
        migrations.RemoveField(model_name='observation', name='comp_description'),
        # Irreversible: the dropped columns were required with no default. To
        # roll back, revert and rebuild from JSON. This no-op has no
        # reverse_code, so reversing raises IrreversibleError before any change.
        migrations.RunPython(migrations.RunPython.noop),
    ]
