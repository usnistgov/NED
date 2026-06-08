from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('ned_app', '0023_temp_fks_and_copy'),
    ]

    operations = [
        # Step 1: Remove old FK fields (pointing to CharField PK)
        migrations.RemoveField(
            model_name='experimentfragilitymodelbridge',
            name='fragility_model',
        ),
        migrations.RemoveField(
            model_name='componentfragilitymodelbridge',
            name='fragility_model',
        ),
        migrations.RemoveField(
            model_name='fragilitycurve',
            name='fragility_model',
        ),
        # Step 2: Rename _new fields to original names
        migrations.RenameField(
            model_name='experimentfragilitymodelbridge',
            old_name='fragility_model_new',
            new_name='fragility_model',
        ),
        migrations.RenameField(
            model_name='componentfragilitymodelbridge',
            old_name='fragility_model_new',
            new_name='fragility_model',
        ),
        migrations.RenameField(
            model_name='fragilitycurve',
            old_name='fragility_model_new',
            new_name='fragility_model',
        ),
        # Step 3: Remove CharField PK from FragilityModel
        migrations.RemoveField(
            model_name='fragilitymodel',
            name='id',
        ),
        # Step 4: Add auto BigAutoField PK
        migrations.AddField(
            model_name='fragilitymodel',
            name='id',
            field=models.BigAutoField(
                auto_created=True,
                primary_key=True,
                serialize=False,
                verbose_name='ID',
            ),
        ),
        # Step 5: Make model_id and fragility_model_id non-nullable
        migrations.AlterField(
            model_name='fragilitymodel',
            name='model_id',
            field=models.CharField(
                help_text='Model identifier, unique within a given reference.',
                max_length=255,
                verbose_name='model id',
            ),
        ),
        migrations.AlterField(
            model_name='fragilitymodel',
            name='fragility_model_id',
            field=models.CharField(
                help_text='Auto-generated unique identifier (reference_id|model_id).',
                max_length=255,
                unique=True,
                verbose_name='fragility model id',
            ),
        ),
        # Step 6: Make renamed FK fields non-nullable
        migrations.AlterField(
            model_name='experimentfragilitymodelbridge',
            name='fragility_model',
            field=models.ForeignKey(
                help_text='Fragility model ID',
                on_delete=models.PROTECT,
                to='ned_app.fragilitymodel',
                to_field='fragility_model_id',
            ),
        ),
        migrations.AlterField(
            model_name='componentfragilitymodelbridge',
            name='fragility_model',
            field=models.ForeignKey(
                help_text='Fragility model ID',
                on_delete=models.PROTECT,
                to='ned_app.fragilitymodel',
                to_field='fragility_model_id',
            ),
        ),
        migrations.AlterField(
            model_name='fragilitycurve',
            name='fragility_model',
            field=models.ForeignKey(
                help_text='Id of the fragility model this fragility belongs to.',
                on_delete=models.PROTECT,
                to='ned_app.fragilitymodel',
                to_field='fragility_model_id',
            ),
        ),
        # Step 7: Add UniqueConstraints for (reference, model_id)
        migrations.AddConstraint(
            model_name='fragilitymodel',
            constraint=models.UniqueConstraint(
                condition=models.Q(('reference__isnull', False)),
                fields=('reference', 'model_id'),
                name='unique_ref_model',
            ),
        ),
        migrations.AddConstraint(
            model_name='fragilitymodel',
            constraint=models.UniqueConstraint(
                condition=models.Q(('reference__isnull', True)),
                fields=('model_id',),
                name='unique_legacy_model',
            ),
        ),
    ]
