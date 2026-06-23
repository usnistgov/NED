from django.core.management.base import BaseCommand

from ned_app.management.import_utils import (
    coerce_value,
    find_unknown_columns,
    load_json,
    read_csv,
    write_json,
    build_pk_set,
)
from ned_app.serialization.serializer import (
    ReferenceSerializer,
    ExperimentSerializer,
    ExperimentFragilityModelBridgeSerializer,
)

_MODEL_CONFIG = {
    'Reference': {
        'json_file': 'reference.json',
        'pk_fields': ['reference_id'],
        'serializer': ReferenceSerializer,
    },
    'Experiment': {
        'json_file': 'experiment.json',
        'pk_fields': ['id'],
        'serializer': ExperimentSerializer,
    },
    'ExperimentFragilityModelBridge': {
        'json_file': 'experiment_fragility_model_bridge.json',
        'pk_fields': ['experiment', 'fragility_model'],
        'serializer': ExperimentFragilityModelBridgeSerializer,
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
    """
    Parse a semicolon-delimited author string into CSL author objects.

    Args:
        authors_str (str): Authors separated by ';', each optionally
            'Family, Given'.

    Returns:
        list[dict]: CSL-JSON author entries.
    """
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
    """
    Reconstruct nested CSL-JSON from the flattened csl_* CSV columns.

    Args:
        row (dict): A CSV row.

    Returns:
        dict: CSL-JSON citation data.
    """
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


def _row_to_record(row, model_name):
    """
    Convert a CSV row into a canonical JSON record.

    For Reference, the flattened csl_* columns are reconstructed into nested
    csl_data and the remaining columns are type-coerced. For all other models,
    every column is type-coerced.

    Args:
        row (dict): A CSV row.
        model_name (str): The model being imported.

    Returns:
        dict: A record ready to append to the canonical JSON file.
    """
    if model_name == 'Reference':
        record = {}
        for key, val in row.items():
            if not key or key in _CSL_COLUMNS:
                continue
            if isinstance(val, str):
                val = val.strip()
            record[key] = coerce_value(key, val)
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


def _expected_columns(model_name, serializer_class):
    """
    Build the set of CSV columns accepted for a model.

    Derived from the serializer's fields (the single source of truth) so it
    cannot drift from the model. Reference is special-cased because its nested
    csl_data is supplied via flattened csl_* columns.

    Args:
        model_name (str): The model being imported.
        serializer_class: The DRF serializer for the model.

    Returns:
        set[str]: Accepted column names.
    """
    fields = set(serializer_class().fields)
    if model_name == 'Reference':
        fields -= {'csl_data', 'title', 'author', 'year'}
        fields |= _CSL_COLUMNS
    return fields


class Command(BaseCommand):
    help = (
        'Import new records from a CSV file and append them to the '
        'canonical JSON source data in resources/data/. The data is not '
        'validated here; run `python manage.py ingest` and the test suite '
        'afterwards to validate the new records.'
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
                'Report what would be appended without writing any changes '
                'to the JSON files.'
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

        try:
            columns, rows = read_csv(input_file)
        except FileNotFoundError:
            self.stderr.write(f"CSV file not found: '{input_file}'")
            return

        if not rows:
            self.stdout.write('No data rows found in CSV file.')
            return

        unknown = find_unknown_columns(
            columns, _expected_columns(model_name, config['serializer'])
        )
        if unknown:
            self.stdout.write(
                self.style.WARNING(
                    f'Warning: unrecognized column(s) in CSV header: {unknown}.\n'
                    'These columns will be ignored. Check for typos against the '
                    'template.'
                )
            )

        new_records = []
        skipped_duplicates = []
        seen_pks = set(existing_pk_set)

        for row_num, row in enumerate(rows, start=2):
            record = _row_to_record(row, model_name)
            pk_tuple = tuple(
                str(record.get(f, '') or '') for f in config['pk_fields']
            )

            if pk_tuple in seen_pks:
                skipped_duplicates.append((row_num, pk_tuple))
                continue

            seen_pks.add(pk_tuple)
            new_records.append(record)

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

        if not new_records:
            self.stdout.write('No new records to add (all rows were duplicates).')
            return

        if dry_run:
            self.stdout.write(
                self.style.SUCCESS(
                    f'\n[DRY RUN] {len(new_records)} record(s) would be '
                    f'appended to {config["json_file"]}. No changes written.'
                )
            )
            return

        existing_records.extend(new_records)
        write_json(config['json_file'], existing_records)
        self.stdout.write(
            self.style.SUCCESS(
                f'\nAppended {len(new_records)} record(s) '
                f'to {config["json_file"]}.\n'
                'Run `python manage.py ingest` and the test suite to validate '
                'the new records.'
            )
        )
