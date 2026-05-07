from django.db import migrations


def populate_curve_fields(apps, schema_editor):
    """
    For each FragilityModel with curves:
    - Assert all curves share the same reviewer, source, edp_metric, edp_unit
    - Copy these values from the first curve to the FragilityModel
    For legacy FMs without curves: fields stay blank (default).
    """
    FragilityModel = apps.get_model('ned_app', 'FragilityModel')
    FragilityCurve = apps.get_model('ned_app', 'FragilityCurve')

    total_fms = FragilityModel.objects.count()
    fms_with_curves = 0
    fms_without_curves = 0

    for fm in FragilityModel.objects.all():
        curves = FragilityCurve.objects.filter(fragility_model=fm.fragility_model_id)

        if curves.exists():
            # Verify consistency: all curves must share the same values
            distinct_reviewers = curves.values_list('reviewer', flat=True).distinct()
            distinct_sources = curves.values_list('source', flat=True).distinct()
            distinct_edp_metrics = curves.values_list(
                'edp_metric', flat=True
            ).distinct()
            distinct_edp_units = curves.values_list('edp_unit', flat=True).distinct()

            assert list(distinct_reviewers).__len__() == 1, (
                f'FragilityModel {fm.fragility_model_id} has curves with '
                f'inconsistent reviewers: {list(distinct_reviewers)}'
            )
            assert list(distinct_sources).__len__() == 1, (
                f'FragilityModel {fm.fragility_model_id} has curves with '
                f'inconsistent sources: {list(distinct_sources)}'
            )
            assert list(distinct_edp_metrics).__len__() == 1, (
                f'FragilityModel {fm.fragility_model_id} has curves with '
                f'inconsistent edp_metrics: {list(distinct_edp_metrics)}'
            )
            assert list(distinct_edp_units).__len__() == 1, (
                f'FragilityModel {fm.fragility_model_id} has curves with '
                f'inconsistent edp_units: {list(distinct_edp_units)}'
            )

            # Copy values from first curve
            first_curve = curves.first()
            fm.reviewer = first_curve.reviewer
            fm.source = first_curve.source
            fm.edp_metric = first_curve.edp_metric
            fm.edp_unit = first_curve.edp_unit
            fm.save()
            fms_with_curves += 1
        else:
            fms_without_curves += 1

    # Verification assertions
    assert fms_with_curves + fms_without_curves == total_fms, (
        f'Processed {fms_with_curves + fms_without_curves} FMs but expected {total_fms}'
    )
    assert fms_with_curves == FragilityModel.objects.exclude(reviewer='').count(), (
        f'Expected {fms_with_curves} FMs with reviewer set, '
        f'got {FragilityModel.objects.exclude(reviewer="").count()}'
    )


class Migration(migrations.Migration):
    dependencies = [
        ('ned_app', '0026_fragilitymodel_add_curve_fields'),
    ]

    operations = [
        migrations.RunPython(
            populate_curve_fields,
            reverse_code=migrations.RunPython.noop,
        ),
    ]
