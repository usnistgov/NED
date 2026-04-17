from django.db import migrations


def populate_fragility_model_fields(apps, schema_editor):
    """
    For each FragilityModel:
    - Set model_id = current id (CharField PK)
    - For FMs with curves: derive reference from curves (assert exactly one)
    - For FMs without curves: leave reference null
    - Auto-populate fragility_model_id as reference_id|model_id (or just model_id)
    """
    FragilityModel = apps.get_model('ned_app', 'FragilityModel')
    FragilityCurve = apps.get_model('ned_app', 'FragilityCurve')
    Reference = apps.get_model('ned_app', 'Reference')

    total_fms = FragilityModel.objects.count()
    fms_with_reference = 0
    fms_without_reference = 0

    for fm in FragilityModel.objects.all():
        # model_id = current PK
        fm.model_id = fm.id

        # Derive reference from curves
        curve_refs = (
            FragilityCurve.objects.filter(fragility_model=fm)
            .values_list('reference_id', flat=True)
            .distinct()
        )
        curve_ref_ids = list(curve_refs)

        if curve_ref_ids:
            assert len(curve_ref_ids) == 1, (
                f'FragilityModel {fm.id} has curves pointing to multiple references: '
                f'{curve_ref_ids}'
            )
            ref = Reference.objects.get(reference_id=curve_ref_ids[0])
            fm.reference = ref
            fm.fragility_model_id = f'{ref.reference_id}|{fm.model_id}'
            fms_with_reference += 1
        else:
            fm.reference = None
            fm.fragility_model_id = fm.model_id
            fms_without_reference += 1

        fm.save()

    # Verification assertions
    assert fms_with_reference + fms_without_reference == total_fms, (
        f'Processed {fms_with_reference + fms_without_reference} FMs but expected {total_fms}'
    )
    assert FragilityModel.objects.filter(model_id__isnull=True).count() == 0, (
        'Some FragilityModels still have null model_id'
    )
    assert (
        FragilityModel.objects.filter(fragility_model_id__isnull=True).count() == 0
    ), 'Some FragilityModels still have null fragility_model_id'


class Migration(migrations.Migration):
    dependencies = [
        ('ned_app', '0021_fragilitymodel_add_reference_model_id'),
    ]

    operations = [
        migrations.RunPython(
            populate_fragility_model_fields,
            reverse_code=migrations.RunPython.noop,
        ),
    ]
