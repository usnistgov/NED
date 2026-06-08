from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('ned_app', '0027_populate_fragilitymodel_curve_fields'),
    ]

    operations = [
        # Remove fields from FragilityCurve
        migrations.RemoveField(
            model_name='fragilitycurve',
            name='reviewer',
        ),
        migrations.RemoveField(
            model_name='fragilitycurve',
            name='source',
        ),
        migrations.RemoveField(
            model_name='fragilitycurve',
            name='edp_metric',
        ),
        migrations.RemoveField(
            model_name='fragilitycurve',
            name='edp_unit',
        ),
        migrations.RemoveField(
            model_name='fragilitycurve',
            name='reference',
        ),
        # Add CheckConstraints to FragilityModel
        migrations.AddConstraint(
            model_name='fragilitymodel',
            constraint=models.CheckConstraint(
                condition=models.Q(reference__isnull=True)
                | ~models.Q(edp_metric=''),
                name='non_legacy_requires_edp_metric',
            ),
        ),
        migrations.AddConstraint(
            model_name='fragilitymodel',
            constraint=models.CheckConstraint(
                condition=models.Q(reference__isnull=True) | ~models.Q(edp_unit=''),
                name='non_legacy_requires_edp_unit',
            ),
        ),
    ]
