import csv
import json
import os

from django.core.management.base import BaseCommand

from ned_app.models import (
    DSClassChoices,
    EDPMetricChoices,
    EDPUnitChoices,
    StudyTypeChoices,
    TestTypeChoices,
)
from ned_app.serialization.file_and_path_utiles import build_json_data_file_path


_INT_FIELDS = {'ds_rank', 'num_observations'}
_FLOAT_FIELDS = {'edp_value', 'alt_edp_value', 'median', 'beta', 'probability'}

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
    'Component': {
        'json_file': 'component.json',
        'pk_fields': ['component_id'],
        'required_fields': ['name', 'component_id'],
        'choice_fields': {},
        'fk_fields': {},
    },
    'FragilityModel': {
        'json_file': 'fragility_model.json',
        'pk_fields': ['reference', 'model_id'],
        'required_fields': [
            'model_id',
            'comp_description',
            'edp_metric',
            'edp_unit',
        ],
        'choice_fields': {
            'edp_metric': EDPMetricChoices,
            'edp_unit': EDPUnitChoices,
        },
        'fk_fields': {
            'reference': ('reference.json', 'reference_id'),
        },
    },
    'FragilityCurve': {
        'json_file': 'fragility_curve.json',
        'pk_fields': ['fragility_model', 'ds_rank'],
        'required_fields': [
            'fragility_model',
            'ds_description',
            'median',
            'beta',
            'probability',
        ],
        'choice_fields': {'basis': StudyTypeChoices},
        'fk_fields': {
            'fragility_model': ('fragility_model.json', '_fragility_model_id'),
        },
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
    'ComponentFragilityModelBridge': {
        'json_file': 'component_fragility_model_bridge.json',
        'pk_fields': ['component', 'fragility_model'],
        'required_fields': ['component', 'fragility_model'],
        'choice_fields': {},
        'fk_fields': {
            'component': ('component.json', 'component_id'),
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
    """
    Parse a semicolon-separated author string into a CSL author list.

    Each author should be formatted as 'Family, Given'. Authors without
    a comma are stored as a literal name.

    Args:
        authors_str (str): Semicolon-separated author entries, e.g.
            'Smith, John; Doe, Jane'.

    Returns:
        list[dict]: CSL-JSON author objects.
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
    Reconstruct a csl_data dict from flat CSV columns.

    Args:
        row (dict): A CSV row containing csl_* columns.

    Returns:
        dict: A CSL-JSON compatible citation object.
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


def _coerce_value(field, val):
    """
    Coerce a CSV string value to the appropriate Python type for JSON.

    Args:
        field (str): The field name.
        val (str): The raw string value from the CSV.

    Returns:
        int | float | str | None: The coerced value.
    """
    if val == '' or val is None:
        if field in _INT_FIELDS or field in _FLOAT_FIELDS:
            return None
        return val
    if field in _INT_FIELDS:
        try:
            return int(val)
        except ValueError:
            return val
    if field in _FLOAT_FIELDS:
        try:
            return float(val)
        except ValueError:
            return val
    return val


class Command(BaseCommand):
    """
    Django management command to import new records from a CSV file.

    Appends validated records to the canonical JSON source files in
    resources/data/. Performs duplicate detection and FK validation
    before writing. Does not ingest into the database — run
    `python manage.py ingest` after importing.
    """

    help = (
        'Import new records from a CSV file and append them to the '
        'canonical JSON source data in resources/data/.'
    )

    def add_arguments(self, parser):
        """
        Define command-line arguments.

        Args:
            parser: The argument parser instance.
        """
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
                'Model name to import (e.g., Experiment, FragilityModel). '
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
        """
        Execute the import command.

        Args:
            *args: Positional arguments (unused).
            **options: Parsed command-line options.
        """
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

        existing_records = self._load_json(config['json_file'])
        existing_pk_set = self._build_pk_set(existing_records, config['pk_fields'])

        fk_sets = {}
        for fk_field, (fk_file, fk_key) in config['fk_fields'].items():
            fk_sets[fk_field] = self._build_fk_set(fk_file, fk_key)

        try:
            rows = self._read_csv(input_file)
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
            row_errors = self._validate_row(row, config, fk_sets)
            if row_errors:
                all_errors.append((row_num, row_errors))
                continue

            record = self._row_to_record(row, model_name)
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
        self._write_json(config['json_file'], existing_records)
        self.stdout.write(
            self.style.SUCCESS(
                f'\nSuccessfully appended {len(valid_records)} record(s) '
                f'to {config["json_file"]}.\n'
                'Run `python manage.py ingest` to load them into the database.'
            )
        )

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _load_json(self, filename):
        """
        Load the contents of a canonical JSON data file.

        Args:
            filename (str): JSON filename within resources/data/.

        Returns:
            list[dict]: Parsed records, or an empty list if the file
                does not exist.
        """
        filepath = build_json_data_file_path(filename)
        if not os.path.exists(filepath):
            return []
        with open(filepath, 'r', encoding='utf-8') as f:
            return json.load(f)

    def _write_json(self, filename, data):
        """
        Write records back to a canonical JSON data file.

        Args:
            filename (str): JSON filename within resources/data/.
            data (list[dict]): Records to serialize.
        """
        filepath = build_json_data_file_path(filename)
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=4, sort_keys=True, ensure_ascii=True)
            f.write('\n')

    def _build_pk_set(self, records, pk_fields):
        """
        Build a set of existing primary-key tuples from loaded JSON records.

        Args:
            records (list[dict]): Existing JSON records.
            pk_fields (list[str]): Field names composing the primary key.

        Returns:
            set[tuple[str, ...]]: Set of primary key tuples.
        """
        pk_set = set()
        for rec in records:
            if '_comment' in rec:
                continue
            pk_tuple = tuple(str(rec.get(f, '') or '') for f in pk_fields)
            pk_set.add(pk_tuple)
        return pk_set

    def _build_fk_set(self, json_file, key):
        """
        Build a set of valid foreign key values from a JSON reference file.

        The special sentinel key '_fragility_model_id' derives the
        auto-generated fragility_model_id by combining the reference and
        model_id fields (e.g. 'REF-2020|fra001'), matching the value
        stored in dependent JSON files.

        Args:
            json_file (str): JSON filename within resources/data/.
            key (str): Field name to extract, or '_fragility_model_id'.

        Returns:
            set[str]: Set of valid key values.
        """
        records = self._load_json(json_file)
        if key == '_fragility_model_id':
            result = set()
            for rec in records:
                if '_comment' in rec:
                    continue
                ref = rec.get('reference', '')
                model_id = rec.get('model_id', '')
                result.add(f'{ref}|{model_id}' if ref else model_id)
            return result
        return {
            str(rec[key]) for rec in records if '_comment' not in rec and key in rec
        }

    def _read_csv(self, filepath):
        """
        Read all rows from a CSV file.

        Args:
            filepath (str): Path to the CSV file.

        Returns:
            list[dict]: Rows as dicts keyed by header column names.

        Raises:
            FileNotFoundError: If the CSV file does not exist.
        """
        with open(filepath, 'r', encoding='utf-8-sig', newline='') as f:
            reader = csv.DictReader(f)
            return list(reader)

    def _validate_row(self, row, config, fk_sets):
        """
        Validate a single CSV row against required fields, choices, and FKs.

        Also validates that integer and float fields contain parseable values.

        Args:
            row (dict): A single CSV row.
            config (dict): Model config entry from _MODEL_CONFIG.
            fk_sets (dict[str, set[str]]): Pre-loaded FK lookup sets.

        Returns:
            list[str]: Validation error messages; empty list if the row is valid.
        """
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

    def _row_to_record(self, row, model_name):
        """
        Convert a validated CSV row to a JSON-compatible record dict.

        For Reference records, strips csl_* columns and reconstructs the
        nested csl_data object. For all other models, passes fields through
        with appropriate type coercion for numeric fields.

        Args:
            row (dict): A validated CSV row.
            model_name (str): The model name being imported.

        Returns:
            dict: Record ready to be appended to the JSON data file.
        """
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
            if not key:  # skip empty column names from trailing commas
                continue
            if isinstance(val, str):
                val = val.strip()
            record[key] = _coerce_value(key, val)
        return record
