# Generated manually for data migration

from django.db import migrations
from django.core.exceptions import ValidationError


def forwards_func(apps, schema_editor):
    """Synchronize denormalized fields by applying population logic directly."""
    Reference = apps.get_model('ned_app', 'Reference')

    processed_count = 0
    error_count = 0

    for ref in Reference.objects.all():
        try:
            # --- START: Copied and adapted logic from the model's save() method ---
            if ref.csl_data:
                # Validation
                if 'title' not in ref.csl_data or not ref.csl_data['title']:
                    raise ValidationError(
                        "csl_data must contain a non-empty 'title' field"
                    )
                if 'author' not in ref.csl_data or not ref.csl_data['author']:
                    raise ValidationError(
                        "csl_data must contain a non-empty 'author' field"
                    )
                if (
                    'issued' not in ref.csl_data
                    or 'date-parts' not in ref.csl_data['issued']
                    or not ref.csl_data['issued']['date-parts']
                ):
                    raise ValidationError(
                        "csl_data must contain a valid 'issued' field with 'date-parts'"
                    )

                # Population
                ref.title = ref.csl_data.get('title', '')
                ref.year = ref.csl_data.get('issued', {}).get(
                    'date-parts', [[None]]
                )[0][0]

                authors = ref.csl_data.get('author', [])
                if authors:
                    family_names = [
                        author.get('family')
                        for author in authors
                        if author.get('family')
                    ]
                    if len(family_names) == 1:
                        ref.author = family_names[0]
                    elif len(family_names) == 2:
                        ref.author = f'{family_names[0]} and {family_names[1]}'
                    else:
                        ref.author = f'{family_names[0]} et al.'
                else:
                    ref.author = ''  # Ensure author is not left with old data if csl_data has no authors
            else:
                raise ValidationError('csl_data is required and cannot be empty')
            # --- END: Copied logic ---

            ref.save()
            processed_count += 1
        except Exception as e:
            print(f'Error processing reference {ref.id}: {e}')
            error_count += 1

    print(
        f'Synchronization completed. Processed: {processed_count}, Errors: {error_count}'
    )


class Migration(migrations.Migration):
    dependencies = [
        ('ned_app', '0004_remove_reference_citation_remove_reference_doi_and_more'),
    ]

    operations = [
        migrations.RunPython(forwards_func, migrations.RunPython.noop),
    ]
