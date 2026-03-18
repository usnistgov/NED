"""Create ComponentFragilityModelBridge table."""

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('ned_app', '0014_alter_component_component_id_alter_component_id_and_more'),
    ]

    operations = [
        migrations.CreateModel(
            name='ComponentFragilityModelBridge',
            fields=[
                (
                    'id',
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name='ID',
                    ),
                ),
                (
                    'component',
                    models.ForeignKey(
                        help_text='Component ID (component_id)',
                        on_delete=django.db.models.deletion.PROTECT,
                        to='ned_app.component',
                        to_field='component_id',
                    ),
                ),
                (
                    'fragility_model',
                    models.ForeignKey(
                        help_text='Fragility model ID',
                        on_delete=django.db.models.deletion.PROTECT,
                        to='ned_app.fragilitymodel',
                    ),
                ),
            ],
            options={
                'verbose_name': 'Component - Fragility Pair',
                'verbose_name_plural': 'Component - Fragility Pairs',
            },
        ),
    ]
