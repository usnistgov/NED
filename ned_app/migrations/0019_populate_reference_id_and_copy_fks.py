from django.db import migrations


def populate_reference_id_and_copy_fks(apps, schema_editor):
    """
    Copy Reference.id -> Reference.reference_id, then copy FK links
    from Experiment.reference and FragilityCurve.reference to their
    respective _new fields.
    """
    Reference = apps.get_model('ned_app', 'Reference')
    Experiment = apps.get_model('ned_app', 'Experiment')
    FragilityCurve = apps.get_model('ned_app', 'FragilityCurve')

    # Step 1: Populate reference_id from id on all References
    references = Reference.objects.all()
    ref_count = references.count()
    for ref in references:
        ref.reference_id = ref.id
        ref.save()

    populated_count = Reference.objects.filter(reference_id__isnull=False).count()
    assert populated_count == ref_count, (
        f'Expected {ref_count} references with reference_id, got {populated_count}'
    )

    # Step 2: Copy Experiment.reference -> Experiment.reference_new
    experiments = Experiment.objects.all()
    exp_count = experiments.count()
    for exp in experiments:
        exp.reference_new = exp.reference
        exp.save()

    exp_populated = Experiment.objects.filter(reference_new__isnull=False).count()
    assert exp_populated == exp_count, (
        f'Expected {exp_count} experiments with reference_new, got {exp_populated}'
    )

    # Step 3: Copy FragilityCurve.reference -> FragilityCurve.reference_new
    curves = FragilityCurve.objects.all()
    curve_count = curves.count()
    for curve in curves:
        curve.reference_new = curve.reference
        curve.save()

    curve_populated = FragilityCurve.objects.filter(
        reference_new__isnull=False
    ).count()
    assert curve_populated == curve_count, (
        f'Expected {curve_count} curves with reference_new, got {curve_populated}'
    )


class Migration(migrations.Migration):
    dependencies = [
        ('ned_app', '0018_reference_add_reference_id_and_temp_fks'),
    ]

    operations = [
        migrations.RunPython(populate_reference_id_and_copy_fks),
    ]
