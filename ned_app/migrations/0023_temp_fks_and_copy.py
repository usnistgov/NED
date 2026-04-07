import django.db.models.deletion
from django.db import migrations, models


def copy_fragility_model_fks(apps, schema_editor):
    """
    Copy FK links from old fragility_model (CharField PK) to fragility_model_new
    (to_field='fragility_model_id') on bridges and curves.
    """
    ExperimentFragilityModelBridge = apps.get_model(
        'ned_app', 'ExperimentFragilityModelBridge'
    )
    ComponentFragilityModelBridge = apps.get_model(
        'ned_app', 'ComponentFragilityModelBridge'
    )
    FragilityCurve = apps.get_model('ned_app', 'FragilityCurve')
    FragilityModel = apps.get_model('ned_app', 'FragilityModel')

    # Build lookup from old PK to new fragility_model_id
    fm_lookup = dict(
        FragilityModel.objects.values_list('id', 'fragility_model_id')
    )

    # Copy ExperimentFragilityModelBridge
    exp_bridges = ExperimentFragilityModelBridge.objects.all()
    for bridge in exp_bridges:
        new_fm = FragilityModel.objects.get(
            fragility_model_id=fm_lookup[bridge.fragility_model_id]
        )
        bridge.fragility_model_new = new_fm
        bridge.save()
    assert ExperimentFragilityModelBridge.objects.filter(
        fragility_model_new__isnull=True
    ).count() == 0, 'Some ExperimentFragilityModelBridges have null fragility_model_new'

    # Copy ComponentFragilityModelBridge
    comp_bridges = ComponentFragilityModelBridge.objects.all()
    for bridge in comp_bridges:
        new_fm = FragilityModel.objects.get(
            fragility_model_id=fm_lookup[bridge.fragility_model_id]
        )
        bridge.fragility_model_new = new_fm
        bridge.save()
    assert ComponentFragilityModelBridge.objects.filter(
        fragility_model_new__isnull=True
    ).count() == 0, 'Some ComponentFragilityModelBridges have null fragility_model_new'

    # Copy FragilityCurve
    curves = FragilityCurve.objects.all()
    for curve in curves:
        new_fm = FragilityModel.objects.get(
            fragility_model_id=fm_lookup[curve.fragility_model_id]
        )
        curve.fragility_model_new = new_fm
        curve.save()
    assert FragilityCurve.objects.filter(
        fragility_model_new__isnull=True
    ).count() == 0, 'Some FragilityCurves have null fragility_model_new'


class Migration(migrations.Migration):
    dependencies = [
        ('ned_app', '0022_populate_fragilitymodel_fields'),
    ]

    operations = [
        # Add temporary FK fields pointing to fragility_model_id
        migrations.AddField(
            model_name='experimentfragilitymodelbridge',
            name='fragility_model_new',
            field=models.ForeignKey(
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name='+',
                to='ned_app.fragilitymodel',
                to_field='fragility_model_id',
                help_text='Fragility model ID',
            ),
        ),
        migrations.AddField(
            model_name='componentfragilitymodelbridge',
            name='fragility_model_new',
            field=models.ForeignKey(
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name='+',
                to='ned_app.fragilitymodel',
                to_field='fragility_model_id',
                help_text='Fragility model ID',
            ),
        ),
        migrations.AddField(
            model_name='fragilitycurve',
            name='fragility_model_new',
            field=models.ForeignKey(
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name='+',
                to='ned_app.fragilitymodel',
                to_field='fragility_model_id',
                help_text='Id of the fragility model this fragility belongs to.',
            ),
        ),
        # Copy FK data
        migrations.RunPython(
            copy_fragility_model_fks,
            reverse_code=migrations.RunPython.noop,
        ),
    ]
