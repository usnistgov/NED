import os
import re
import shutil
import subprocess
import sys
import tempfile
from collections import defaultdict

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError

from ned_app.json_guards import DERIVE_ID, check_data_dir
from ned_app.management.import_utils import (
    FIXTURE_STEPS,
    coerce_value,
    find_unknown_columns,
    load_json,
    looks_semicolon_delimited,
    read_csv,
    write_json_files,
)
from ned_app.serialization.file_and_path_utiles import DATA_DIR
from ned_app.validators import suggest_label, validate_label

# Required in the header and non-blank on every row.
IDENTITY_COLUMNS = ['reference', 'facility', 'specimen', 'test', 'observation']

# CSV column -> record key, per level. A parent's columns must agree across
# its rows, and with the stored record when it already exists.
FACILITY_COLUMNS = {'facility_location': 'location'}
SPECIMEN_COLUMNS = {
    'facility': 'facility',
    'specimen_name': 'name',
    'contributor': 'contributor',
    'component': 'component',
    'comp_detail': 'comp_detail',
    'material': 'material',
    'size_class': 'size_class',
    'design_objective': 'design_objective',
    'governing_design_standard': 'governing_design_standard',
    'comp_description': 'comp_description',
    'specimen_notes': 'notes',
}
TEST_COLUMNS = {
    'test_order': 'test_order',
    'test_type': 'test_type',
    'loading_protocol': 'loading_protocol',
    'peak_test_amplitude': 'peak_test_amplitude',
    'prior_damage': 'prior_damage',
    'prior_damage_repaired': 'prior_damage_repaired',
    'test_notes': 'notes',
}
OBSERVATION_COLUMNS = [
    'damage_location',
    'ds_description',
    'ds_class',
    'edp_metric',
    'edp_unit',
    'edp_value',
    'alt_edp_metric',
    'alt_edp_unit',
    'alt_edp_value',
    'notes',
]

# The template's columns, in its order.
TEMPLATE_COLUMNS = [
    'reference',
    'program',
    'facility',
    'facility_location',
    'specimen',
    *[c for c in SPECIMEN_COLUMNS if c != 'facility'],
    'test',
    *TEST_COLUMNS,
    'observation',
    *OBSERVATION_COLUMNS,
]

# The files this command appends to, in the order ingest reads them.
FILES = ['facility', 'program', 'specimen', 'test', 'observation']


def _clean(value):
    """Strip a cell and normalize its line endings; a missing cell is blank."""
    return (value or '').replace('\r\n', '\n').replace('\r', '\n').strip()


def _stored(value):
    """A stored value as text, for comparison with a CSV cell."""
    return '' if value is None else _clean(str(value))


def _rows(nums):
    """'Row 2' or 'Rows 2, 5, 7'."""
    nums = sorted(set(nums))
    if len(nums) == 1:
        return f'Row {nums[0]}'
    return f'Rows {", ".join(map(str, nums))}'


def _index(records, derive):
    """Map each record's lowercased derived id to (id, record)."""
    index = {}
    for record in records:
        try:
            derived = derive(record)
        except (KeyError, IndexError, TypeError):
            continue
        index.setdefault(derived.lower(), (derived, record))
    return index


def _digit_width(label):
    """The length of a label's first run of digits, or None if it has none."""
    match = re.search(r'[0-9]+', label)
    return len(match.group()) if match else None


class Command(BaseCommand):
    help = (
        'Import observations from one flat CSV (resources/import_templates/'
        'observation_template.csv), splitting each row across the facility, '
        'program, specimen, test and observation JSON files. Parents may '
        'already exist; every disagreement is an error and nothing is written. '
        'Only identity and consistency are checked here: use --dry_run to have '
        'ingest check everything else. A dry run rebuilds the whole database '
        'in a scratch file, which takes minutes.'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--input_file',
            type=str,
            required=True,
            help='Path to the observation import CSV file.',
        )
        parser.add_argument(
            '--dry_run',
            action='store_true',
            help=(
                'Import into a scratch copy of the data directory, then run '
                'migrate and ingest into a scratch database and the JSON guards. '
                'Writes nothing. Takes minutes on the full data.'
            ),
        )
        parser.add_argument(
            '--data_dir',
            default=DATA_DIR,
            help='The JSON data directory (default: resources/data/).',
        )

    def handle(self, *args, **options):
        input_file = options['input_file']
        data_dir = options['data_dir']

        try:
            columns, raw_rows = read_csv(input_file)
        except FileNotFoundError:
            raise CommandError(f"CSV file not found: '{input_file}'")

        if looks_semicolon_delimited(columns):
            raise CommandError(
                'This CSV appears to be semicolon-delimited. Re-save it as a '
                'comma-delimited CSV (in Excel: "CSV UTF-8 (Comma delimited)") '
                'and try again.'
            )

        missing = [c for c in IDENTITY_COLUMNS if c not in columns]
        if missing:
            raise CommandError(f'Missing required column(s): {", ".join(missing)}.')

        if not raw_rows:
            self.stdout.write('No data rows found in CSV file.')
            return

        unknown = find_unknown_columns(columns, TEMPLATE_COLUMNS)
        if unknown:
            self.stdout.write(
                self.style.WARNING(
                    f'Warning: unrecognized column(s) in CSV header: {unknown}.\n'
                    'These columns will be ignored. Check for typos against the '
                    'template.'
                )
            )

        rows = [
            (num, {c: _clean(row.get(c)) for c in TEMPLATE_COLUMNS})
            for num, row in enumerate(raw_rows, start=2)
        ]

        # ------------------------------------------------------------------
        # Resolve each level against the data directory's JSON, top down.
        # Errors are collected (one line per problem, naming every row it
        # affects) and reported together; nothing is written if there are any.
        # ------------------------------------------------------------------
        self.errors = defaultdict(list)
        self.warnings = []
        self.stored = {
            name: load_json(f'{name}.json', data_dir)
            for name in [*FILES, 'reference']
        }
        self.new = {name: [] for name in FILES}

        rows = self._check_required(rows)
        program_of = self._resolve_programs(rows)
        facility_of = self._resolve_facilities(rows)
        specimen_of = self._resolve_specimens(rows, program_of, facility_of)
        test_of = self._resolve_tests(rows, specimen_of)
        self._build_observations(rows, test_of)

        for warning in self.warnings:
            self.stdout.write(self.style.WARNING(f'Warning: {warning}'))

        if self.errors:
            self._report_errors()
            raise CommandError(
                'No records were imported. Fix the errors above and retry.'
            )

        summary = ''.join(
            f'  {len(self.new[name])} {name} record(s) -> {name}.json\n'
            for name in FILES
        )
        files = {
            f'{name}.json': self.stored[name] + self.new[name]
            for name in FILES
            if self.new[name]
        }

        if options['dry_run']:
            self.stdout.write(f'\n[DRY RUN] Would append:\n{summary}')
            self._dry_run(data_dir, files)
            return

        write_json_files(files, data_dir=data_dir)
        for record in self.new['facility']:
            self.stdout.write(
                self.style.WARNING(
                    f"New facility '{record['label']}' has a blank name; set it "
                    'in facility.json.'
                )
            )
        self.stdout.write(
            self.style.SUCCESS(
                f'\nAppended:\n{summary}'
                'Run with --dry_run before a real import, so ingest checks the '
                f'result first.\n{FIXTURE_STEPS}'
            )
        )

    # -- errors -----------------------------------------------------------

    def _error(self, nums, column, message):
        if isinstance(nums, int):
            nums = [nums]
        self.errors[(column, message)].extend(nums)

    def _report_errors(self):
        lines = sorted(
            (min(nums), f'{_rows(nums)}, column {column!r}: {message}')
            for (column, message), nums in self.errors.items()
        )
        self.stderr.write(f'\nFound {len(lines)} error(s):')
        for _, line in lines:
            self.stderr.write(f'  - {line}')

    def _check_label(self, nums, column, label):
        try:
            validate_label(label)
        except ValidationError as exc:
            suggestion = suggest_label(label)
            hint = f" Suggested label: '{suggestion}'." if suggestion else ''
            self._error(nums, column, f'{exc.messages[0]}{hint}')

    def _check_spelling(self, group, column, canonical, source):
        """Report rows whose label differs only in case from the canonical one."""
        for num, row in group:
            if row[column] != canonical:
                self._error(
                    num,
                    column,
                    f'{row[column]!r} differs only in case from {canonical!r} '
                    f'({source}); use one spelling',
                )

    def _check_attributes(self, group, columns, level, key, stored):
        """
        Check a parent's columns across its rows.

        An existing record's blank cells are not restated, and a non-blank cell
        must equal the stored value; a new record's rows must all agree.

        Returns:
            dict: The new record's values by record key (the first row's).
        """
        first_num, first = group[0]
        for column, field in columns.items():
            if stored is not None:
                want = _stored(stored.get(field))
                for num, row in group:
                    if row[column] and row[column] != want:
                        self._error(
                            num,
                            column,
                            f'{row[column]!r} differs from the stored value '
                            f'{want!r} of existing {level} {key!r}',
                        )
            else:
                for num, row in group[1:]:
                    if row[column] != first[column]:
                        self._error(
                            num,
                            column,
                            f'{row[column]!r} disagrees with {first[column]!r} '
                            f'(row {first_num}) for new {level} {key!r}',
                        )
        return {field: first[column] for column, field in columns.items()}

    # -- levels -----------------------------------------------------------

    def _check_required(self, rows):
        """Report blank identity cells; return the rows that have them all."""
        complete = []
        for num, row in rows:
            blank = [c for c in IDENTITY_COLUMNS if not row[c]]
            for column in blank:
                self._error(num, column, 'required, but blank')
            if not blank:
                complete.append((num, row))
        return complete

    def _resolve_programs(self, rows):
        """Map each row to its program_id, creating new programs as needed."""
        references = _index(self.stored['reference'], DERIVE_ID['reference'])
        programs = _index(self.stored['program'], DERIVE_ID['program'])
        groups = defaultdict(list)
        ref_of = {}
        blank_new = []
        for num, row in rows:
            ref, _ = references.get(row['reference'].lower(), (None, None))
            if ref is None:
                self._error(
                    num,
                    'reference',
                    f'{row["reference"]!r} is not an existing reference_id '
                    '(import the reference first)',
                )
                ref = row['reference']
            elif ref != row['reference']:
                self._error(
                    num,
                    'reference',
                    f'{row["reference"]!r} differs only in case from the stored '
                    f'reference_id {ref!r}',
                )
            ref_of[num] = ref
            program_id = row['program'] or self._default_program(num, ref, programs)
            if program_id is not None:
                groups[program_id.lower()].append((num, row))
                if not row['program'] and program_id.lower() not in programs:
                    blank_new.append((num, ref))

        # A blank program beside a new labelled one would make two programs.
        labelled = {ref_of[num] for num, row in rows if row['program']}
        for num, ref in blank_new:
            if ref in labelled:
                self._error(
                    num,
                    'program',
                    f'blank, but other rows give reference {ref!r} a labelled '
                    'program; name the program on every row',
                )

        program_of = {}
        for key, group in groups.items():
            first_num, first = group[0]
            existing = programs.get(key)
            if existing is not None:
                program_id, record = existing
                for num, row in group:
                    if row['program'] and row['program'] != program_id:
                        self._error(
                            num,
                            'program',
                            f'{row["program"]!r} differs only in case from the '
                            f'stored program_id {program_id!r}',
                        )
                    if ref_of[num] != record['reference']:
                        self._error(
                            num,
                            'reference',
                            f'{ref_of[num]!r} differs from {record["reference"]!r}, '
                            f'the reference of existing program {program_id!r}',
                        )
            else:
                ref = ref_of[first_num]
                program_id = first['program'] or ref
                if first['program']:
                    self._check_label(first_num, 'program', first['program'])
                for num, row in group[1:]:
                    for column, value, want in (
                        ('program', row['program'], first['program']),
                        ('reference', ref_of[num], ref),
                    ):
                        if value != want:
                            self._error(
                                num,
                                column,
                                f'{value!r} disagrees with {want!r} (row '
                                f'{first_num}) for new program {program_id!r}',
                            )
                self.new['program'].append({
                    'label': first['program'],
                    'name': '',
                    'notes': '',
                    'reference': ref,
                })
            for num, _ in group:
                program_of[num] = program_id
        return program_of

    def _default_program(self, num, ref, programs):
        """The program a blank 'program' cell names: the reference's unlabelled one."""
        under = [
            record
            for _, record in programs.values()
            if record.get('reference') == ref
        ]
        if any(not record.get('label') for record in under):
            return ref
        if under:
            labels = ', '.join(sorted(repr(r['label']) for r in under))
            self._error(
                num,
                'program',
                f'blank, but reference {ref!r} has only labelled programs '
                f'({labels}); name one, or give a new label',
            )
            return None
        return ref

    def _resolve_facilities(self, rows):
        """Map each row to its facility label, creating new facilities as needed."""
        facilities = _index(self.stored['facility'], DERIVE_ID['facility'])
        groups = defaultdict(list)
        for num, row in rows:
            groups[row['facility'].lower()].append((num, row))

        facility_of = {}
        for key, group in groups.items():
            first_num, first = group[0]
            existing = facilities.get(key)
            if existing is not None:
                label, record = existing
                self._check_spelling(group, 'facility', label, 'the stored label')
            else:
                label, record = first['facility'], None
                self._check_label(first_num, 'facility', label)
                self._check_spelling(group, 'facility', label, f'row {first_num}')
            values = self._check_attributes(
                group, FACILITY_COLUMNS, 'facility', label, record
            )
            if record is None:
                self.new['facility'].append({
                    'label': label,
                    'name': '',
                    'location': values['location'],
                    'notes': '',
                })
            for num, _ in group:
                facility_of[num] = label
        return facility_of

    def _resolve_specimens(self, rows, program_of, facility_of):
        """Map each row to its specimen_id, creating new specimens as needed."""
        specimens = _index(self.stored['specimen'], DERIVE_ID['specimen'])
        groups = defaultdict(list)
        for num, row in rows:
            if num not in program_of:
                continue
            # Compare the facility as resolved, so a case error isn't repeated.
            row['facility'] = facility_of[num]
            program_id = program_of[num]
            groups[f'{program_id}|{row["specimen"]}'.lower()].append((num, row))

        specimen_of = {}
        for key, group in groups.items():
            first_num, first = group[0]
            program_id = program_of[first_num]
            existing = specimens.get(key)
            if existing is not None:
                specimen_id, record = existing
                label = record['label']
                self._check_spelling(group, 'specimen', label, 'the stored label')
            else:
                label, record = first['specimen'], None
                specimen_id = f'{program_id}|{label}'
                self._check_label(first_num, 'specimen', label)
                self._check_spelling(group, 'specimen', label, f'row {first_num}')
            values = self._check_attributes(
                group, SPECIMEN_COLUMNS, 'specimen', specimen_id, record
            )
            if record is None:
                self.new['specimen'].append({
                    'program': program_id,
                    'reference': None,
                    'label': label,
                    **values,
                })
            for num, _ in group:
                specimen_of[num] = specimen_id
        return specimen_of

    def _resolve_tests(self, rows, specimen_of):
        """Map each row to its test_id, creating new tests as needed."""
        tests = _index(self.stored['test'], DERIVE_ID['test'])
        groups = defaultdict(list)
        for num, row in rows:
            if num not in specimen_of:
                continue
            order = row['test_order']
            if order and not re.fullmatch(r'[0-9]+', order):
                self._error(
                    num,
                    'test_order',
                    f'{order!r} is not a whole number. Put a paper identifier '
                    "such as '3a' in the 'test' label, and give whole numbers "
                    'that keep its order here (see the template)',
                )
            elif order and int(order) < 1:
                self._error(num, 'test_order', f'{order!r} must be at least 1')
            elif order:
                row['test_order'] = str(int(order))
            groups[f'{specimen_of[num]}|{row["test"]}'.lower()].append((num, row))

        # Orders already taken in each specimen: lowercased specimen_id ->
        # {order: (test label, where it comes from)}.
        orders = defaultdict(dict)
        for _, record in tests.values():
            if record.get('test_order') is not None:
                orders[record['specimen'].lower()][str(record['test_order'])] = (
                    record['label'],
                    'stored',
                )

        test_of = {}
        for key, group in groups.items():
            first_num, first = group[0]
            specimen_id = specimen_of[first_num]
            existing = tests.get(key)
            if existing is not None:
                test_id, record = existing
                label = record['label']
                self._check_spelling(group, 'test', label, 'the stored label')
            else:
                label, record = first['test'], None
                test_id = f'{specimen_id}|{label}'
                self._check_label(first_num, 'test', label)
                self._check_spelling(group, 'test', label, f'row {first_num}')
            values = self._check_attributes(
                group, TEST_COLUMNS, 'test', test_id, record
            )
            if record is None:
                order = values['test_order']
                taken = orders[specimen_id.lower()]
                if order in taken:
                    other, source = taken[order]
                    self._error(
                        first_num,
                        'test_order',
                        f'{order} is already the order of test {other!r} '
                        f'({source}) in specimen {specimen_id!r}',
                    )
                elif order:
                    taken[order] = (label, f'row {first_num}')
                values['test_order'] = coerce_value('test_order', order)
                self.new['test'].append({
                    'specimen': specimen_id,
                    'label': label,
                    **values,
                })
            for num, _ in group:
                test_of[num] = test_id
        return test_of

    def _build_observations(self, rows, test_of):
        """One new observation per row; warn on mixed-width labels per test."""
        observations = _index(self.stored['observation'], DERIVE_ID['observation'])
        seen = {}
        labels = defaultdict(list)
        for num, row in rows:
            if num not in test_of:
                continue
            test_id = test_of[num]
            label = row['observation']
            observation_id = f'{test_id}|{label}'
            key = observation_id.lower()
            self._check_label(num, 'observation', label)
            if key in observations:
                self._error(
                    num,
                    'observation',
                    f'{label!r} names existing observation {observations[key][0]!r}',
                )
                continue
            if key in seen:
                other_num, other = seen[key]
                self._error(
                    num,
                    'observation',
                    f'{label!r} repeats {other!r} (row {other_num}) in test '
                    f'{test_id!r}',
                )
                continue
            seen[key] = (num, label)
            labels[test_id].append(label)
            self.new['observation'].append({
                'test': test_id,
                'label': label,
                **{c: coerce_value(c, row[c]) for c in OBSERVATION_COLUMNS},
                'legacy_ds_rank': None,
                'legacy_prior_damage': '',
                'legacy_prior_damage_repaired': '',
            })

        stored = defaultdict(list)
        for _, record in observations.values():
            stored[record['test'].lower()].append(record['label'])
        for test_id, new_labels in labels.items():
            all_labels = stored[test_id.lower()] + new_labels
            widths = {_digit_width(label) for label in all_labels}
            widths.discard(None)
            if len(widths) > 1:
                self.warnings.append(
                    f'test {test_id!r} has observation labels whose numbers '
                    f'differ in width ({", ".join(map(str, sorted(widths)))} '
                    "digits). Labels sort as text, so zero-pad them ('01', '02')."
                )

    # -- dry run ----------------------------------------------------------

    def _dry_run(self, data_dir, files):
        """
        Import into a scratch copy, then run migrate, ingest and the JSON guards.

        Django fixes its database path at startup, so migrate and ingest run in
        a subprocess pointed at a scratch database.
        """
        scratch = tempfile.mkdtemp(prefix='ned_dry_run_')
        failed = False
        try:
            copy = os.path.join(scratch, 'data')
            shutil.copytree(data_dir, copy)
            write_json_files(files, data_dir=copy)
            env = {
                **os.environ,
                'NED_DATABASE_PATH': os.path.join(scratch, 'db.sqlite3'),
                'PYTHONIOENCODING': 'utf-8',
            }
            manage = os.path.join(settings.BASE_DIR, 'manage.py')
            self.stdout.write(
                f'[DRY RUN] Paths below are in a scratch copy; fix the same files '
                f'in {data_dir}.'
            )
            for step in (
                ['migrate', '--verbosity', '0'],
                ['ingest', '--data_dir', copy],
            ):
                self.stdout.write(f'\n[DRY RUN] manage.py {step[0]}')
                result = subprocess.run(
                    [sys.executable, manage, *step],
                    check=False,
                    cwd=settings.BASE_DIR,
                    env=env,
                    capture_output=True,
                )
                self.stdout.write(
                    result.stdout.decode('utf-8', 'replace'), ending=''
                )
                self.stderr.write(
                    result.stderr.decode('utf-8', 'replace'), ending=''
                )
                if result.returncode:
                    failed = True
                    break

            self.stdout.write('\n[DRY RUN] JSON guards')
            problems = check_data_dir(copy)
            for problem in problems:
                self.stderr.write(f'  - {problem}')
            failed = failed or bool(problems)
        finally:
            # Windows can hold a file open briefly; leftovers are harmless.
            shutil.rmtree(scratch, ignore_errors=True)

        if failed:
            raise CommandError(
                'Dry run failed: see the errors above. No changes were written.'
            )
        self.stdout.write(
            self.style.SUCCESS(
                '\n[DRY RUN] ingest and the JSON guards accept the import. '
                'No changes written.'
            )
        )
