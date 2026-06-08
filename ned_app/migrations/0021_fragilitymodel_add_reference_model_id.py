import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('ned_app', '0020_swap_reference_pk'),
    ]

    operations = [
        migrations.AddField(
            model_name='fragilitymodel',
            name='reference',
            field=models.ForeignKey(
                blank=True,
                help_text='Identifier of a Reference documenting this fragility model.',
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                to='ned_app.reference',
                to_field='reference_id',
            ),
        ),
        migrations.AddField(
            model_name='fragilitymodel',
            name='model_id',
            field=models.CharField(
                help_text='Model identifier, unique within a given reference.',
                max_length=255,
                null=True,
                verbose_name='model id',
            ),
        ),
        migrations.AddField(
            model_name='fragilitymodel',
            name='fragility_model_id',
            field=models.CharField(
                help_text='Auto-generated unique identifier (reference_id|model_id).',
                max_length=255,
                null=True,
                unique=True,
                verbose_name='fragility model id',
            ),
        ),
    ]
