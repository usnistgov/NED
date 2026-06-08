import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('ned_app', '0017_remove_fragilitymodel_component'),
    ]

    operations = [
        # Step 1: Add reference_id CharField to Reference (nullable temporarily)
        migrations.AddField(
            model_name='reference',
            name='reference_id',
            field=models.CharField(
                max_length=255,
                null=True,
                unique=True,
                verbose_name='reference id',
                help_text='Unique identifier for the reference.',
            ),
        ),
        # Step 2: Add temporary FK on Experiment pointing to Reference via reference_id
        migrations.AddField(
            model_name='experiment',
            name='reference_new',
            field=models.ForeignKey(
                help_text='Temporary reference field for migration purposes',
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name='+',
                to='ned_app.reference',
                to_field='reference_id',
            ),
        ),
        # Step 3: Add temporary FK on FragilityCurve pointing to Reference via reference_id
        migrations.AddField(
            model_name='fragilitycurve',
            name='reference_new',
            field=models.ForeignKey(
                help_text='Temporary reference field for migration purposes',
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name='+',
                to='ned_app.reference',
                to_field='reference_id',
            ),
        ),
    ]
