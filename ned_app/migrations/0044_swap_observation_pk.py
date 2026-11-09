from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('ned_app', '0043_observation_bridge_fk_to_observation_id'),
    ]

    operations = [
        # Step 1: Remove the old string PK (nothing references it after 0043)
        migrations.RemoveField(
            model_name='observation',
            name='id',
        ),
        # Step 2: Add a BigAutoField PK (DEFAULT_AUTO_FIELD)
        migrations.AddField(
            model_name='observation',
            name='id',
            field=models.BigAutoField(
                auto_created=True,
                primary_key=True,
                serialize=False,
                verbose_name='ID',
            ),
        ),
    ]
