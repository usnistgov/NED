# Generated by Django 4.2.16 on 2025-04-11 22:29

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='Nistir',
            fields=[
                ('id', models.CharField(max_length=5, primary_key=True, serialize=False, verbose_name='id')),
                ('sub_element', models.CharField(max_length=255, verbose_name='sub-element name')),
                ('element_id', models.CharField(max_length=5, verbose_name='element id')),
                ('element', models.CharField(max_length=255, verbose_name='element name')),
                ('group_id', models.CharField(max_length=3, verbose_name='group id')),
                ('group', models.CharField(max_length=50, verbose_name='group name')),
                ('major_group_id', models.CharField(max_length=1, verbose_name='major group id')),
                ('major_group', models.CharField(choices=[('Substructure', 'A'), ('Shell', 'B'), ('Interiors', 'C'), ('Services', 'D'), ('Equipment & Furnishings', 'E'), ('Special Construction & Demolition', 'F')], max_length=50, verbose_name='major group name')),
            ],
        ),
        migrations.CreateModel(
            name='Reference',
            fields=[
                ('id', models.CharField(max_length=255, primary_key=True, serialize=False, verbose_name='id')),
                ('name', models.CharField(max_length=255, verbose_name='name')),
                ('author', models.CharField(max_length=255, verbose_name='author')),
                ('year', models.IntegerField(verbose_name='year')),
                ('study_type', models.CharField(choices=[('Experiment', 'Experiment'), ('Historical Event', 'Recon'), ('Analytical Study', 'Analytical'), ('Lit Review', 'Lit Review'), ('Other', 'Other')], default='Other', max_length=50, verbose_name='study type')),
                ('comp_type', models.CharField(blank=True, max_length=255, verbose_name='component type')),
                ('doi', models.URLField(null=True, verbose_name='doi')),
                ('citation', models.CharField(blank=True, max_length=255, verbose_name='citation')),
                ('publication_type', models.CharField(blank=True, max_length=50, verbose_name='publication type')),
                ('pdf_saved', models.BooleanField(default=False, verbose_name='pdf saved')),
            ],
        ),
        migrations.CreateModel(
            name='Fragility',
            fields=[
                ('id', models.CharField(max_length=255, primary_key=True, serialize=False, verbose_name='id')),
                ('group_id', models.CharField(max_length=255, verbose_name='group id')),
                ('reviewer', models.CharField(max_length=255, verbose_name='reviewer')),
                ('source', models.CharField(max_length=255, verbose_name='source')),
                ('basis', models.CharField(blank=True, choices=[('Experiment', 'Experiment'), ('Historical Event', 'Recon'), ('Analytical Study', 'Analytical'), ('Lit Review', 'Lit Review'), ('Other', 'Other')], max_length=50, verbose_name='basis')),
                ('num_observations', models.IntegerField(blank=True, null=True, verbose_name='number of observations')),
                ('p58_fragility', models.CharField(blank=True, max_length=50, verbose_name='FEMA P-58 fragility id')),
                ('comp_type', models.CharField(max_length=255, verbose_name='component type')),
                ('sub_type', models.CharField(blank=True, max_length=255, verbose_name='component sub-type')),
                ('detailing', models.CharField(blank=True, max_length=255, verbose_name='connection detail')),
                ('material', models.CharField(blank=True, max_length=255, verbose_name='material classification')),
                ('size_class', models.CharField(blank=True, max_length=255, verbose_name='size classification')),
                ('comp_description', models.TextField(verbose_name='component description')),
                ('edp_metric', models.CharField(choices=[('Story Drift Ratio', 'Sdr'), ('Story Drift Ratio, bi-directional', 'Sdr 2D'), ('Peak Floor Acceleration, horizontal', 'Pfa H'), ('Peak Floor Acceleration, vertical', 'Pfa V'), ('Peak Floor Velocity', 'Pfv'), ('Joint Rotation', 'Rot Joint'), ('Force, tension', 'Force T'), ('Force, compression', 'Force C'), ('Force, bending', 'Force M'), ('Force, lateral', 'Force V'), ('Custom', 'Custom')], max_length=255, verbose_name='edp metric')),
                ('edp_unit', models.CharField(choices=[('g', 'G'), ('Ratio', 'Ratio'), ('Radians', 'Rad'), ('Kips', 'Kip'), ('k-in', 'K In'), ('Meters Per Second', 'Mps'), ('Custom', 'Custom')], max_length=255, verbose_name='edp unit')),
                ('ds_rank', models.IntegerField(verbose_name='damage state rank')),
                ('ds_description', models.TextField(verbose_name='damage state description')),
                ('median', models.DecimalField(decimal_places=3, max_digits=9, null=True, verbose_name='median')),
                ('beta', models.DecimalField(decimal_places=2, max_digits=3, null=True, verbose_name='beta')),
                ('probability', models.DecimalField(decimal_places=2, max_digits=3, null=True, verbose_name='probability')),
                ('nistir', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to='ned.nistir')),
                ('reference', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to='ned.reference')),
            ],
        ),
        migrations.CreateModel(
            name='Experiment',
            fields=[
                ('id', models.CharField(max_length=255, primary_key=True, serialize=False, verbose_name='id')),
                ('specimen', models.CharField(blank=True, max_length=255, verbose_name='specimen')),
                ('specimen_inspection_sequence', models.CharField(blank=True, max_length=255, verbose_name='specimen inspection sequence')),
                ('reviewer', models.CharField(max_length=50, verbose_name='reviewer')),
                ('p58_fragility', models.CharField(blank=True, max_length=50, verbose_name='FEMA P-58 fragility id')),
                ('fragility_id', models.CharField(blank=True, max_length=50, verbose_name='Fragility Identifier Foriegn Key')),
                ('comp_type', models.CharField(max_length=255, verbose_name='component type')),
                ('sub_type', models.CharField(blank=True, max_length=255, verbose_name='component sub-type')),
                ('detailing', models.CharField(blank=True, max_length=255, verbose_name='connection detail')),
                ('material', models.CharField(blank=True, max_length=255, verbose_name='material classification')),
                ('size_class', models.CharField(blank=True, max_length=255, verbose_name='size classification')),
                ('test_type', models.CharField(choices=[('Dynamic, uniaxial', 'Dyna 1D'), ('Dynamic, bi-directional', 'Dyna 2D'), ('Dynamic, 3D', 'Dyna 3D'), ('Monotonic, compression', 'Mono C'), ('Monotonic, tension', 'Mono T'), ('Monotonic, bending', 'Mono M'), ('Quasi-static Cyclic, uniaxial', 'Quasi 1D'), ('Quasi-static Cyclic, bi-directional', 'Quasi 2D')], max_length=50, verbose_name='test type')),
                ('loading_protocol', models.CharField(blank=True, max_length=255, verbose_name='loading protocol')),
                ('peak_test_amplitude', models.CharField(blank=True, max_length=255, verbose_name='peak test amplitute')),
                ('location', models.CharField(blank=True, max_length=255, verbose_name='location')),
                ('governing_design_standard', models.CharField(blank=True, max_length=255, verbose_name='governing design standard')),
                ('design_objective', models.CharField(blank=True, max_length=255, verbose_name='design objective')),
                ('comp_description', models.TextField(verbose_name='component description')),
                ('ds_description', models.TextField(verbose_name='damage state description')),
                ('prior_damage', models.CharField(blank=True, max_length=255, verbose_name='prior damage')),
                ('prior_damage_repaired', models.BooleanField(null=True, verbose_name='is prior damage repaired')),
                ('edp_metric', models.CharField(choices=[('Story Drift Ratio', 'Sdr'), ('Story Drift Ratio, bi-directional', 'Sdr 2D'), ('Peak Floor Acceleration, horizontal', 'Pfa H'), ('Peak Table Acceleration, horizontal', 'Pfa Table H'), ('Peak Floor Acceleration, vertical', 'Pfa V'), ('Peak Floor Velocity', 'Pfv'), ('Joint Rotation', 'Rot Joint'), ('Force, tension', 'Force T'), ('Force, compression', 'Force C'), ('Force, bending', 'Force M'), ('Force, lateral', 'Force V'), ('Custom', 'Custom')], max_length=50, verbose_name='edp metric')),
                ('edp_unit', models.CharField(choices=[('g', 'G'), ('Ratio', 'Ratio'), ('Radians', 'Rad'), ('Kips', 'Kip'), ('k-in', 'K In'), ('Meters Per Second', 'Mps'), ('Custom', 'Custom')], max_length=50, verbose_name='edp unit')),
                ('edp_value', models.DecimalField(decimal_places=6, max_digits=12, verbose_name='edp value')),
                ('alt_edp_metric', models.CharField(choices=[('Story Drift Ratio', 'Sdr'), ('Story Drift Ratio, bi-directional', 'Sdr 2D'), ('Peak Floor Acceleration, horizontal', 'Pfa H'), ('Peak Table Acceleration, horizontal', 'Pfa Table H'), ('Peak Floor Acceleration, vertical', 'Pfa V'), ('Peak Floor Velocity', 'Pfv'), ('Joint Rotation', 'Rot Joint'), ('Force, tension', 'Force T'), ('Force, compression', 'Force C'), ('Force, bending', 'Force M'), ('Force, lateral', 'Force V'), ('Custom', 'Custom')], max_length=50, verbose_name='alternative edp metric')),
                ('alt_edp_unit', models.CharField(choices=[('g', 'G'), ('Ratio', 'Ratio'), ('Radians', 'Rad'), ('Kips', 'Kip'), ('k-in', 'K In'), ('Meters Per Second', 'Mps'), ('Custom', 'Custom')], max_length=50, verbose_name='alternative edp unit')),
                ('alt_edp_value', models.DecimalField(decimal_places=6, max_digits=12, null=True, verbose_name='alternative edp value')),
                ('ds_rank', models.IntegerField(null=True, verbose_name='damage state rank')),
                ('ds_class', models.CharField(choices=[('No damage', 'No Damage'), ('Inconsequential', 'Inconsequential'), ('Consequential', 'Consequential'), ('Unknown', 'Unknown')], default='Unknown', max_length=50, verbose_name='damage state class')),
                ('notes', models.TextField(blank=True, verbose_name='notes')),
                ('nistir', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to='ned.nistir')),
                ('reference', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to='ned.reference')),
            ],
        ),
    ]
