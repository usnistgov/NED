"""Populate ComponentFragilityModelBridge from FragilityModel.component FK."""

from django.db import migrations


def populate_bridge(apps, schema_editor):
    """Copy component FK from FragilityModel into bridge table and verify."""
    FragilityModel = apps.get_model('ned_app', 'FragilityModel')
    ComponentFragilityModelBridge = apps.get_model(
        'ned_app', 'ComponentFragilityModelBridge'
    )

    fragility_models = FragilityModel.objects.all()
    fm_count = fragility_models.count()

    for fm in fragility_models:
        ComponentFragilityModelBridge.objects.create(
            component=fm.component,
            fragility_model=fm,
        )

    # Verify: bridge count matches FragilityModel count
    bridge_count = ComponentFragilityModelBridge.objects.count()
    if bridge_count != fm_count:
        raise ValueError(
            f'Bridge count ({bridge_count}) does not match '
            f'FragilityModel count ({fm_count}).'
        )

    # Verify: every bridge row's component matches the original FM's component
    for fm in fragility_models:
        bridge = ComponentFragilityModelBridge.objects.get(fragility_model=fm)
        if bridge.component_id != fm.component_id:
            raise ValueError(
                f'Bridge component mismatch for FragilityModel {fm.id}: '
                f'bridge has {bridge.component_id}, '
                f'FM has {fm.component_id}.'
            )


def reverse_bridge(apps, schema_editor):
    """No reverse needed; the bridge table will be dropped by reversing 0015."""
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('ned_app', '0015_componentfragilitymodelbridge'),
    ]

    operations = [
        migrations.RunPython(populate_bridge, reverse_bridge),
    ]
