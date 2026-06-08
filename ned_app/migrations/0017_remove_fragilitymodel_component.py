"""Remove component FK from FragilityModel."""

from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ('ned_app', '0016_populate_component_fragility_bridge'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='fragilitymodel',
            name='component',
        ),
    ]
