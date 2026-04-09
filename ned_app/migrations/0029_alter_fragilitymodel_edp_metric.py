from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('ned_app', '0028_remove_fragilitycurve_fields_add_constraints'),
    ]

    operations = [
        migrations.AlterField(
            model_name='fragilitymodel',
            name='edp_metric',
            field=models.CharField(
                blank=True,
                choices=[
                    ('Story Drift Ratio', 'Sdr'),
                    ('Story Drift Ratio, bi-directional', 'Sdr 2D'),
                    ('Peak Floor Acceleration, horizontal', 'Pfa H'),
                    ('Peak Table Acceleration, horizontal', 'Pfa Table H'),
                    ('Peak Floor Acceleration, vertical', 'Pfa V'),
                    ('Peak Floor Velocity', 'Pfv'),
                    ('Joint Rotation', 'Rot Joint'),
                    ('Force, tension', 'Force T'),
                    ('Force, compression', 'Force C'),
                    ('Force, bending', 'Force M'),
                    ('Force, lateral', 'Force V'),
                    ('Custom', 'Custom'),
                ],
                help_text='Measure of the engineering demand parameter (EDP), e.g, peak story drift ratio.',
                max_length=255,
                verbose_name='edp metric',
            ),
        ),
    ]
