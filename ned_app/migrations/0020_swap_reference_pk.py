import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('ned_app', '0019_populate_reference_id_and_copy_fks'),
    ]

    operations = [
        # Step 1: Remove old reference FKs (pointing to Reference.id CharField PK)
        migrations.RemoveField(
            model_name='experiment',
            name='reference',
        ),
        migrations.RemoveField(
            model_name='fragilitycurve',
            name='reference',
        ),
        # Step 2: Rename temporary FKs to final names
        migrations.RenameField(
            model_name='experiment',
            old_name='reference_new',
            new_name='reference',
        ),
        migrations.RenameField(
            model_name='fragilitycurve',
            old_name='reference_new',
            new_name='reference',
        ),
        # Step 3: Remove old CharField PK from Reference
        migrations.RemoveField(
            model_name='reference',
            name='id',
        ),
        # Step 4: Add BigAutoField PK to Reference
        migrations.AddField(
            model_name='reference',
            name='id',
            field=models.BigAutoField(
                auto_created=True,
                primary_key=True,
                serialize=False,
                verbose_name='ID',
            ),
        ),
        # Step 5: Make reference_id non-nullable
        migrations.AlterField(
            model_name='reference',
            name='reference_id',
            field=models.CharField(
                max_length=255,
                unique=True,
                verbose_name='reference id',
                help_text='Unique identifier for the reference.',
            ),
        ),
        # Step 6: Enforce non-null on renamed FK fields
        migrations.AlterField(
            model_name='experiment',
            name='reference',
            field=models.ForeignKey(
                help_text='ID of the published reference documenting this experimental observation.',
                on_delete=django.db.models.deletion.PROTECT,
                to='ned_app.reference',
                to_field='reference_id',
            ),
        ),
        migrations.AlterField(
            model_name='fragilitycurve',
            name='reference',
            field=models.ForeignKey(
                help_text='ID of the published reference documenting this fragility curve.',
                on_delete=django.db.models.deletion.PROTECT,
                to='ned_app.reference',
                to_field='reference_id',
            ),
        ),
    ]
