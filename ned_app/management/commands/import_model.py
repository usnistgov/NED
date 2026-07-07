from django.core.management.base import BaseCommand

from ned_app.management.import_utils import (
    _FLOAT_FIELDS,
    _INT_FIELDS,
    build_fk_set,
    build_pk_set,
    coerce_value,
    load_json,
    read_csv,
    write_json,
)
from ned_app.models import (
    DSClassChoices,
    EDPMetricChoices,
    EDPUnitChoices,
    StudyTypeChoices,
    TestTypeChoices,
)

_MODEL_CONFIG = {
    'Reference': {
        'json_file': 'reference.json',
        'pk_fields': ['reference_id'],
        'required_fields': [
            'reference_id',
            'study_type',
            'csl_type',
            'csl_title',
            'csl_year',
            'csl_authors',
        ],
        'choice_fields': {'study_type': StudyTypeChoices},
        'fk_fields': {},
    },
    'Experiment': {
        'json_file': 'experiment.json',
        'pk_fields': ['id'],
        'required_fields': [
            'id',
            'reference',
            'component',
            'test_type',
            'comp_description',
            'ds_description',
            'edp_metric',
            'edp_unit',
            'ds_class',
        ],
        'choice_fields': {
            'test_type': TestTypeChoices,
            'edp_metric': EDPMetricChoices,
            'edp_unit': EDPUnitChoices,
            'alt_edp_metric': EDPMetricChoices,
            'alt_edp_unit': EDPUnitChoices,
            'ds_class': DSClassChoices,
        },
        'fk_fields': {
            'reference': ('reference.json', 'reference_id'),
            'component': ('component.json', 'component_id'),
        },
    },
    'ExperimentFragilityModelBridge': {
        'json_file': 'experiment_fragility_model_bridge.json',
        'pk_fields': ['experiment', 'fragility_model'],
        'required_fields': ['experiment', 'fragility_model'],
        'choice_fields': {},
        'fk_fields': {
            'experiment': ('experiment.json', 'id'),
            'fragility_model': ('fragility_model.json', '_fragility_model_id'),
        },
    },
}

_CSL_COLUMNS = {
    'csl_type',
    'csl_title',
    'csl_year',
    'csl_authors',
    'csl_doi',
    'csl_url',
    'csl_journal',
    'csl_volume',
    'csl_issue',
    'csl_page',
    'csl_publisher',
}

_CSL_OPTIONAL_MAP = {
    'csl_doi': 'DOI',
    'csl_url': 'URL',
    'csl_journal': 'container-title',
    'csl_volume': 'volume',
    'csl_issue': 'issue',
    'csl_page': 'page',
    'csl_publisher': 'publisher',
}


def _parse_authors(authors_str):
    authors = []
    for part in authors_str.split(';'):
        part = part.strip()
        if not part:
            continue
        if ',' in part:
            family, _, given = part.partition(',')
            authors.append({'family': family.strip(), 'given': given.strip()})
        else:
            authors.append({'literal': part})
    return authors


def _build_csl_data(row):
    csl_data = {
        'type': row.get('csl_type', '').strip(),
        'id': row.get('reference_id', '').strip(),
        'title': row.get('csl_title', '').strip(),
        'issued': {'date-parts': [[int(row['csl_year'])]]},
        'author': _parse_authors(row.get('csl_authors', '')),
    }
    for csv_col, csl_key in _CSL_OPTIONAL_MAP.items():
        val = row.get(csv_col, '').strip()
        if val:
            csl_data[csl_key] = val
    return csl_data


def _validate_row(row, config, fk_sets):
    errors = []

    for field in config['required_fields']:
        if not row.get(field, '').strip():
            errors.append(f"Missing required field '{field}'")

    for field, choices_class in config['choice_fields'].items():
        val = row.get(field, '').strip()
        if val and val not in choices_class.values:
            errors.append(
                f"Invalid value '{val}' for '{field}'. "
                f'Valid values: {list(choices_class.values)}'
            )

    for fk_field, fk_set in fk_sets.items():
        val = row.get(fk_field, '').strip()
        if val and val not in fk_set:
            errors.append(
                f"FK '{fk_field}' value '{val}' not found in existing records."
            )

    for field in _INT_FIELDS:
        val = row.get(field, '').strip()
        if val:
            try:
                int(val)
            except ValueError:
                errors.append(f"'{field}' must be an integer, got '{val}'")

    for field in _FLOAT_FIELDS:
        val = row.get(field, '').strip()
        if val:
            try:
                float(val)
            except ValueError:
                errors.append(f"'{field}' must be a number, got '{val}'")

    if 'csl_year' in row:
        val = row.get('csl_year', '').strip()
        if val:
            try:
                int(val)
            except ValueError:
                errors.append(f"'csl_year' must be an integer, got '{val}'")

    return errors


def _row_to_record(row, model_name):
    if model_name == 'Reference':
        record = {}
        for key, val in row.items():
            if not key or key in _CSL_COLUMNS:
                continue
            record[key] = val.strip() if isinstance(val, str) else val
        record['csl_data'] = _build_csl_data(row)
        return record

    record = {}
    for key, val in row.items():
        if not key:
            continue
        if isinstance(val, str):
            val = val.strip()
        record[key] = coerce_value(key, val)
    return record


class Command(BaseCommand):
    help = (
        'Import new records from a CSV file and append them to the '
        'canonical JSON source data in resources/data/.'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--list-models',
            action='store_true',
            help='List all models that support CSV import.',
        )
        parser.add_argument(
            '--model',
            type=str,
            required=False,
            help=(
                'Model name to import (e.g., Experiment, Reference). '
                'Use --list-models to see all importable models.'
            ),
        )
        parser.add_argument(
            '--input_file',
            type=str,
            required=False,
            help='Path to the CSV file to import.',
        )
        parser.add_argument(
            '--dry_run',
            action='store_true',
            help=(
                'Validate the CSV and report results without writing '
                'any changes to the JSON files.'
            ),
        )

    def handle(self, *args, **options):
        if options['list_models']:
            self.stdout.write(self.style.SUCCESS('Models that support CSV import:'))
            for name in sorted(_MODEL_CONFIG):
                self.stdout.write(f'  • {name}')
            return

        model_name = options['model']
        input_file = options['input_file']
        dry_run = options['dry_run']

        if not model_name or not input_file:
            self.stderr.write(
                'Error: --model and --input_file are required. '
                'Use --list-models to see available models.'
            )
            return

        if model_name not in _MODEL_CONFIG:
            self.stderr.write(f"Model '{model_name}' does not support CSV import.")
            self.stderr.write('Use --list-models to see all importable models.')
            return

        config = _MODEL_CONFIG[model_name]

        existing_records = load_json(config['json_file'])
        existing_pk_set = build_pk_set(existing_records, config['pk_fields'])

        fk_sets = {}
        for fk_field, (fk_file, fk_key) in config['fk_fields'].items():
            fk_sets[fk_field] = build_fk_set(fk_file, fk_key)

        try:
            rows = read_csv(input_file)
        except FileNotFoundError:
            self.stderr.write(f"CSV file not found: '{input_file}'")
            return

        if not rows:
            self.stdout.write('No data rows found in CSV file.')
            return

        valid_records = []
        skipped_duplicates = []
        all_errors = []
        seen_pks = set(existing_pk_set)

        for row_num, row in enumerate(rows, start=2):
            row_errors = _validate_row(row, config, fk_sets)
            if row_errors:
                all_errors.append((row_num, row_errors))
                continue

            record = _row_to_record(row, model_name)
            pk_tuple = tuple(
                str(record.get(f, '') or '') for f in config['pk_fields']
            )

            if pk_tuple in seen_pks:
                skipped_duplicates.append((row_num, pk_tuple))
                continue

            seen_pks.add(pk_tuple)
            valid_records.append(record)

        if skipped_duplicates:
            self.stdout.write(
                self.style.WARNING(
                    f'\nSkipped {len(skipped_duplicates)} duplicate(s) '
                    f'(already present in {config["json_file"]}):'
                )
            )
            for row_num, pk in skipped_duplicates:
                pk_str = ' | '.join(pk)
                self.stdout.write(f'  Row {row_num}: {pk_str}')

        if all_errors:
            self.stderr.write(
                f'\nFound {len(all_errors)} row(s) with validation errors:'
            )
            for row_num, errors in all_errors:
                self.stderr.write(f'  Row {row_num}:')
                for err in errors:
                    self.stderr.write(f'    - {err}')
            self.stderr.write(
                '\nNo records were imported. Fix validation errors and retry.'
            )
            return

        if not valid_records:
            self.stdout.write(
                'No new records to add (all rows were duplicates or invalid).'
            )
            return

        if dry_run:
            self.stdout.write(
                self.style.SUCCESS(
                    f'\n[DRY RUN] {len(valid_records)} record(s) would be '
                    f'appended to {config["json_file"]}. No changes written.'
                )
            )
            return

        existing_records.extend(valid_records)
        write_json(config['json_file'], existing_records)
        self.stdout.write(
            self.style.SUCCESS(
                f'\nSuccessfully appended {len(valid_records)} record(s) '
                f'to {config["json_file"]}.\n'
                'Run `python manage.py ingest` to load them into the database.'
            )
        )
