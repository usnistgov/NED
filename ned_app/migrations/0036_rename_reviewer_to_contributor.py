from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('ned_app', '0035_alter_experiment_edp_metric_and_more'),
    ]

    # RenameField (not Remove + Add) so existing values are carried through the
    # rename. The canonical JSON in resources/data/ is then regenerated from the
    # migrated database via `export_data`, never hand-edited.
    operations = [
        migrations.RenameField(
            model_name='experiment',
            old_name='reviewer',
            new_name='contributor',
        ),
        migrations.RenameField(
            model_name='fragilitymodel',
            old_name='reviewer',
            new_name='contributor',
        ),
        migrations.AlterField(
            model_name='experiment',
            name='contributor',
            field=models.CharField(
                blank=True,
                help_text='Individual or institution responsible for documenting this particular fragility in the database.',
                max_length=50,
                verbose_name='contributor',
            ),
        ),
        migrations.AlterField(
            model_name='fragilitymodel',
            name='contributor',
            field=models.CharField(
                blank=True,
                help_text='Person or party responsible for uploading this fragility model to the database.',
                max_length=255,
                verbose_name='contributor',
            ),
        ),
    ]
