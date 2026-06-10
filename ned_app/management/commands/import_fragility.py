from collections import defaultdict

from django.core.management.base import BaseCommand

from ned_app.management.import_utils import (
    build_fk_set,
    build_pk_set,
    coerce_value,
    fragility_model_id,
    load_json,
    read_csv,
    write_json,
)
from ned_app.models import (
    EDPMetricChoices,
    EDPUnitChoices,
    StudyTypeChoices,
)

_MODEL_REQUIRED = ['model_id', 'comp_description', 'edp_metric', 'edp_unit']
_CURVE_REQUIRED = ['ds_description', 'median', 'beta', 'probability']

_MODEL_CHOICE_FIELDS = {
    'edp_metric': EDPMetricChoices,
    'edp_unit': EDPUnitChoices,
}
_CURVE_CHOICE_FIELDS = {
    'basis': StudyTypeChoices,
}

_MODEL_FIELDS = [
    'reference', 'model_id', 'comp_description', 'comp_detail', 'edp_metric',
    'edp_unit', 'p58_fragility', 'material', 'size_class', 'reviewer', 'source',
]

# All model-scoped columns — must be identical across every row sharing (reference, model_id)
_CONSISTENCY_FIELDS = _MODEL_FIELDS + ['component_ids']

_FLOAT_CURVE = {'median', 'beta', 'probability'}
_INT_CURVE = {'ds_rank', 'num_observations'}


def _validate_row(row, row_num):
    errors = []

    for field in _MODEL_REQUIRED + _CURVE_REQUIRED:
        if not row.get(field, '').strip():
            errors.append(f"Row {row_num}: missing required field '{field}'")

    for field, choices_class in {**_MODEL_CHOICE_FIELDS, **_CURVE_CHOICE_FIELDS}.items():
        val = row.get(field, '').strip()
        if val and val not in choices_class.values:
            errors.append(
                f"Row {row_num}: invalid value '{val}' for '{field}'. "
                f"Valid: {list(choices_class.values)}"
            )

    for field in _FLOAT_CURVE:
        val = row.get(field, '').strip()
        if val:
            try:
                float(val)
            except ValueError:
                errors.append(f"Row {row_num}: '{field}' must be a number, got '{val}'")

    for field in _INT_CURVE:
        val = row.get(field, '').strip()
        if val:
            try:
                int(val)
            except ValueError:
                errors.append(f"Row {row_num}: '{field}' must be an integer, got '{val}'")

    return errors


class Command(BaseCommand):
    help = (
        'Import fragility models, curves, and component links from a flat '
        'join CSV and append them to the canonical JSON source data in '
        'resources/data/. Run `python manage.py ingest` afterwards.'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--input_file',
            type=str,
            required=True,
            help='Path to the fragility import CSV file.',
        )
        parser.add_argument(
            '--dry_run',
            action='store_true',
            help='Validate the CSV and report results without writing any changes.',
        )

    def handle(self, *args, **options):
        input_file = options['input_file']
        dry_run = options['dry_run']

        try:
            rows = read_csv(input_file)
        except FileNotFoundError:
            self.stderr.write(f"CSV file not found: '{input_file}'")
            return

        if not rows:
            self.stdout.write('No data rows found in CSV file.')
            return

        # ------------------------------------------------------------------
        # Pass 1: row-level validation
        # ------------------------------------------------------------------
        all_errors = []
        for row_num, row in enumerate(rows, start=2):
            all_errors.extend(_validate_row(row, row_num))

        if all_errors:
            self._report_errors(all_errors)
            return

        # ------------------------------------------------------------------
        # Pass 2: group rows by (reference, model_id)
        # ------------------------------------------------------------------
        groups = defaultdict(list)
        for row_num, row in enumerate(rows, start=2):
            key = (row.get('reference', '').strip(), row.get('model_id', '').strip())
            groups[key].append((row_num, row))

        self.stdout.write(
            f'Found {len(groups)} unique fragility model(s) in CSV.'
        )

        # ------------------------------------------------------------------
        # Pass 3: consistency check — model-scoped fields must be identical
        #         across every row that shares the same (reference, model_id)
        # ------------------------------------------------------------------
        for (ref, model_id), group_rows in groups.items():
            _, first_row = group_rows[0]
            for row_num, row in group_rows[1:]:
                for field in _CONSISTENCY_FIELDS:
                    expected = first_row.get(field, '').strip()
                    actual = row.get(field, '').strip()
                    if actual != expected:
                        all_errors.append(
                            f"Row {row_num}: inconsistent '{field}' for model "
                            f"'{model_id}' — expected '{expected}', got '{actual}'"
                        )

        if all_errors:
            self._report_errors(all_errors)
            return

        # ------------------------------------------------------------------
        # Pass 4: FK validation and duplicate detection
        # ------------------------------------------------------------------
        existing_ref_ids = build_fk_set('reference.json', 'reference_id')
        existing_component_ids = build_fk_set('component.json', 'component_id')

        existing_fm_pks = build_pk_set(
            load_json('fragility_model.json'), ['reference', 'model_id']
        )
        existing_curve_pks = build_pk_set(
            load_json('fragility_curve.json'), ['fragility_model', 'ds_rank']
        )
        existing_bridge_pks = build_pk_set(
            load_json('component_fragility_model_bridge.json'), ['component', 'fragility_model']
        )

        seen_fm_pks = set(existing_fm_pks)
        seen_curve_pks = set(existing_curve_pks)
        seen_bridge_pks = set(existing_bridge_pks)

        new_models = []
        new_curves = []
        new_bridges = []
        skipped_models = []
        skipped_curves = []
        skipped_bridges = []

        for (ref, model_id), group_rows in groups.items():
            fm_id = fragility_model_id(ref, model_id)
            _, first_row = group_rows[0]

            # FK: reference
            if ref and ref not in existing_ref_ids:
                all_errors.append(
                    f"Reference '{ref}' (model '{model_id}') not found in reference.json"
                )
                continue

            # Duplicate fragility model
            fm_pk = (ref, model_id)
            if fm_pk in seen_fm_pks:
                skipped_models.append(fm_id)
            else:
                seen_fm_pks.add(fm_pk)
                model_record = {
                    field: first_row.get(field, '').strip() for field in _MODEL_FIELDS
                }
                new_models.append(model_record)

            # Bridge records (derived from component_ids on the first row)
            component_ids_raw = first_row.get('component_ids', '').strip()
            for comp_id in component_ids_raw.split(';'):
                comp_id = comp_id.strip()
                if not comp_id:
                    continue
                if comp_id not in existing_component_ids:
                    all_errors.append(
                        f"Component '{comp_id}' (model '{fm_id}') "
                        f"not found in component.json"
                    )
                    continue
                bridge_pk = (comp_id, fm_id)
                if bridge_pk in seen_bridge_pks:
                    skipped_bridges.append(bridge_pk)
                else:
                    seen_bridge_pks.add(bridge_pk)
                    new_bridges.append({'component': comp_id, 'fragility_model': fm_id})

            # Curve records (one per row in the group)
            for _, row in group_rows:
                ds_rank_raw = row.get('ds_rank', '').strip()
                ds_rank = int(ds_rank_raw) if ds_rank_raw else None
                curve_pk = (fm_id, str(ds_rank) if ds_rank is not None else '')
                if curve_pk in seen_curve_pks:
                    skipped_curves.append(curve_pk)
                else:
                    seen_curve_pks.add(curve_pk)
                    new_curves.append({
                        'fragility_model': fm_id,
                        'ds_rank': ds_rank,
                        'ds_description': row.get('ds_description', '').strip(),
                        'median': coerce_value('median', row.get('median', '').strip()),
                        'beta': coerce_value('beta', row.get('beta', '').strip()),
                        'probability': coerce_value('probability', row.get('probability', '').strip()),
                        'basis': row.get('basis', '').strip(),
                        'num_observations': coerce_value(
                            'num_observations', row.get('num_observations', '').strip()
                        ),
                    })

        if all_errors:
            self._report_errors(all_errors)
            return

        # ------------------------------------------------------------------
        # Report skipped duplicates
        # ------------------------------------------------------------------
        if skipped_models:
            self.stdout.write(
                self.style.WARNING(
                    f'\nSkipped {len(skipped_models)} duplicate fragility model(s):'
                )
            )
            for fm_id in skipped_models:
                self.stdout.write(f'  {fm_id}')

        if skipped_curves:
            self.stdout.write(
                self.style.WARNING(
                    f'\nSkipped {len(skipped_curves)} duplicate fragility curve(s).'
                )
            )

        if skipped_bridges:
            self.stdout.write(
                self.style.WARNING(
                    f'\nSkipped {len(skipped_bridges)} duplicate component bridge(s).'
                )
            )

        if not new_models and not new_curves and not new_bridges:
            self.stdout.write('No new records to add (all rows were duplicates).')
            return

        if dry_run:
            self.stdout.write(
                self.style.SUCCESS(
                    f'\n[DRY RUN] Would append:\n'
                    f'  {len(new_models)} fragility model(s) → fragility_model.json\n'
                    f'  {len(new_curves)} fragility curve(s)  → fragility_curve.json\n'
                    f'  {len(new_bridges)} component bridge(s)  → component_fragility_model_bridge.json\n'
                    'No changes written.'
                )
            )
            return

        # ------------------------------------------------------------------
        # Atomic write to all three JSON files
        # ------------------------------------------------------------------
        fm_data = load_json('fragility_model.json')
        fm_data.extend(new_models)
        write_json('fragility_model.json', fm_data)

        curve_data = load_json('fragility_curve.json')
        curve_data.extend(new_curves)
        write_json('fragility_curve.json', curve_data)

        bridge_data = load_json('component_fragility_model_bridge.json')
        bridge_data.extend(new_bridges)
        write_json('component_fragility_model_bridge.json', bridge_data)

        self.stdout.write(
            self.style.SUCCESS(
                f'\nSuccessfully appended:\n'
                f'  {len(new_models)} fragility model(s) → fragility_model.json\n'
                f'  {len(new_curves)} fragility curve(s)  → fragility_curve.json\n'
                f'  {len(new_bridges)} component bridge(s)  → component_fragility_model_bridge.json\n'
                'Run `python manage.py ingest` to load them into the database.'
            )
        )

    def _report_errors(self, errors):
        self.stderr.write(f'\nFound {len(errors)} error(s):')
        for err in errors:
            self.stderr.write(f'  - {err}')
        self.stderr.write('\nNo records were imported. Fix the errors above and retry.')
