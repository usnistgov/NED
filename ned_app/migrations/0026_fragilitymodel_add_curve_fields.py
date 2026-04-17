from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('ned_app', '0025_alter_fragilitycurve_reference'),
    ]

    operations = [
        migrations.AddField(
            model_name='fragilitymodel',
            name='reviewer',
            field=models.CharField(
                blank=True,
                help_text='Person or party responsible for uploading this fragility model to the database.',
                max_length=255,
                verbose_name='reviewer',
            ),
        ),
        migrations.AddField(
            model_name='fragilitymodel',
            name='source',
            field=models.CharField(
                blank=True,
                help_text='Source of the fragility data.',
                max_length=255,
                verbose_name='source',
            ),
        ),
        migrations.AddField(
            model_name='fragilitymodel',
            name='edp_metric',
            field=models.CharField(
                blank=True,
                choices=[
                    ('Story Drift Ratio', 'Sdr'),
                    ('Story Drift Ratio, bi-directional', 'Sdr 2D'),
                    ('Peak Floor Acceleration, horizontal', 'Pfa H'),
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
        migrations.AddField(
            model_name='fragilitymodel',
            name='edp_unit',
            field=models.CharField(
                blank=True,
                choices=[
                    ('g', 'G'),
                    ('Ratio', 'Ratio'),
                    ('Radians', 'Rad'),
                    ('Kips', 'Kip'),
                    ('k-in', 'K In'),
                    ('Meters Per Second', 'Mps'),
                    ('Custom', 'Custom'),
                ],
                help_text='Unit of the engineering demand parameter.',
                max_length=255,
                verbose_name='edp unit',
            ),
        ),
    ]
