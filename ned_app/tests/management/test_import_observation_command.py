"""
Tests for the import_observation management command.

The importer tests run on a temporary data directory seeded with the example
reference and component. The dry-run tests run migrate and ingest in a
subprocess, so they use a tiny seeded data directory and are kept few.
"""

import csv
import json
import os
import shutil
import tempfile
from io import StringIO

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import SimpleTestCase, TestCase

from ned_app.management import import_utils
from ned_app.management.commands.import_observation import (
    FACILITY_COLUMNS,
    SPECIMEN_COLUMNS,
    TEMPLATE_COLUMNS,
    TEST_COLUMNS,
)

EXAMPLE_DIR = 'resources/example_data'
EXAMPLE_CSV = os.path.join(EXAMPLE_DIR, 'observation_example.csv')
TEMPLATE = 'resources/import_templates/observation_template.csv'
HIERARCHY_FILES = [
    'facility.json',
    'program.json',
    'specimen.json',
    'test.json',
    'observation.json',
]

JONES = {
    'reference_label': '',
    'study_type': 'Experiment',
    'comp_type': 'Walls',
    'csl_data': {
        'type': 'article-journal',
        'title': 'Another study',
        'author': [{'family': 'Jones', 'given': 'Ann'}],
        'issued': {'date-parts': [[2021]]},
    },
}


def _read_text(path):
    # Text mode, so a CRLF checkout of the example files still compares equal.
    with open(path, 'r', encoding='utf-8') as f:
        return f.read()


class ImportObservationTestMixin:
    """A temporary data directory seeded with the example reference and component."""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.temp_dir, ignore_errors=True)
        self.data_dir = os.path.join(self.temp_dir, 'data')
        os.makedirs(self.data_dir)
        for name in ('reference.json', 'component.json'):
            shutil.copy(os.path.join(EXAMPLE_DIR, name), self.data_dir)
        _, self.example_rows = import_utils.read_csv(EXAMPLE_CSV)

    def _path(self, name):
        return os.path.join(self.data_dir, name)

    def _read(self, name):
        with open(self._path(name), encoding='utf-8') as f:
            return json.load(f)

    def _write(self, name, records):
        with open(self._path(name), 'w', encoding='utf-8') as f:
            json.dump(records, f)

    def _snapshot(self):
        snapshot = {}
        for name in sorted(os.listdir(self.data_dir)):
            with open(self._path(name), 'rb') as f:
                snapshot[name] = f.read()
        return snapshot

    def _csv(self, *rows):
        """Write a CSV of the example's first row, with each row's overrides."""
        path = os.path.join(self.temp_dir, 'import.csv')
        with open(path, 'w', encoding='utf-8', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=TEMPLATE_COLUMNS)
            writer.writeheader()
            for overrides in rows:
                writer.writerow({**self.example_rows[0], **overrides})
        return path

    def _import(self, path, **options):
        """Run the importer; return (stdout, stderr, the CommandError or None)."""
        out, err = StringIO(), StringIO()
        try:
            call_command(
                'import_observation',
                input_file=path,
                data_dir=self.data_dir,
                stdout=out,
                stderr=err,
                **options,
            )
        except CommandError as exc:
            return out.getvalue(), err.getvalue(), exc
        return out.getvalue(), err.getvalue(), None

    def _import_example(self):
        _, err, exc = self._import(EXAMPLE_CSV)
        self.assertIsNone(exc, err)

    def _assert_fails(self, path, *fragments):
        """Import must fail, write nothing, and report every fragment."""
        before = self._snapshot()
        _, err, exc = self._import(path)
        self.assertIsNotNone(exc, 'the import should have failed')
        for fragment in fragments:
            self.assertIn(fragment, err)
        self.assertEqual(self._snapshot(), before)
        return err


class ImportObservationCommandTests(ImportObservationTestMixin, SimpleTestCase):
    """The importer's identity and consistency checks, and what it writes."""

    # -- the example and the template -------------------------------------

    def test_example_csv_reproduces_the_example_json(self):
        out, _, _ = self._import(EXAMPLE_CSV)
        for name in HIERARCHY_FILES:
            with self.subTest(name=name):
                self.assertEqual(
                    _read_text(self._path(name)),
                    _read_text(os.path.join(EXAMPLE_DIR, name)),
                )
        self.assertIn("New facility 'Example_Lab' has a blank name", out)
        self.assertIn('--dry_run', out)
        self.assertIn('dumpdata', out)

    def test_reimporting_the_example_fails_on_the_duplicates(self):
        self._import_example()
        err = self._assert_fails(
            EXAMPLE_CSV,
            "Row 2, column 'observation': 'obs01' names existing observation "
            "'Smith-2020|W1|1|obs01'",
        )
        self.assertIn('Found 4 error(s)', err)

    def test_template_header_is_all_recognized_and_matches_the_example(self):
        template_columns, _ = import_utils.read_csv(TEMPLATE)
        example_columns, _ = import_utils.read_csv(EXAMPLE_CSV)
        self.assertEqual(
            import_utils.find_unknown_columns(template_columns, TEMPLATE_COLUMNS), []
        )
        self.assertEqual(template_columns, TEMPLATE_COLUMNS)
        self.assertEqual(template_columns, example_columns)

    # -- existing parents ---------------------------------------------------

    def test_adding_observations_to_an_existing_test_writes_only_observations(self):
        self._import_example()
        before = self._snapshot()
        # Blank parent cells are not restated; restated ones must match.
        parent_columns = [*FACILITY_COLUMNS, *SPECIMEN_COLUMNS, *TEST_COLUMNS]
        blank = {c: '' for c in parent_columns if c != 'facility'}
        path = self._csv(
            {'observation': 'obs03'},
            {**blank, 'facility': 'Example_Lab', 'observation': 'obs04'},
        )
        _, err, exc = self._import(path)
        self.assertIsNone(exc, err)
        after = self._snapshot()
        changed = [name for name in after if after[name] != before[name]]
        self.assertEqual(changed, ['observation.json'])
        labels = [r['label'] for r in self._read('observation.json')]
        self.assertEqual(labels[-2:], ['obs03', 'obs04'])

    def test_adding_tests_to_an_existing_specimen_writes_tests_and_observations(
        self,
    ):
        self._import_example()
        before = self._snapshot()
        path = self._csv(
            {'test': '3', 'test_order': '3', 'observation': 'obs01'},
            {'test': '3', 'test_order': '3', 'observation': 'obs02'},
        )
        _, err, exc = self._import(path)
        self.assertIsNone(exc, err)
        after = self._snapshot()
        changed = sorted(name for name in after if after[name] != before[name])
        self.assertEqual(changed, ['observation.json', 'test.json'])
        new_test = self._read('test.json')[-1]
        self.assertEqual(new_test['specimen'], 'Smith-2020|W1')
        self.assertEqual((new_test['label'], new_test['test_order']), ('3', 3))

    def test_restated_parent_with_a_different_value_fails(self):
        self._import_example()
        cases = [
            ('facility_location', 'Elsewhere', 'Example City, CA', 'facility'),
            ('component', 'B.20.1.1', 'A.10.1.1.A', 'specimen'),
            (
                'comp_description',
                'Other',
                'Steel-framed gypsum partition wall, 12 ft tall',
                'specimen',
            ),
            ('peak_test_amplitude', '3% drift', '2.5% drift', 'test'),
            ('test_order', '5', '1', 'test'),
        ]
        for column, value, stored, level in cases:
            with self.subTest(column=column):
                path = self._csv({column: value, 'observation': 'obs09'})
                self._assert_fails(
                    path,
                    f"Row 2, column '{column}': '{value}' differs from the "
                    f"stored value '{stored}' of existing {level}",
                )

    def test_restating_with_other_line_endings_and_spaces_matches(self):
        self._import_example()
        specimens = self._read('specimen.json')
        specimens[0]['notes'] = 'line one\nline two'
        self._write('specimen.json', specimens)
        path = self._csv({
            'specimen_notes': '  line one\r\nline two ',
            'observation': 'obs03',
        })
        _, err, exc = self._import(path)
        self.assertIsNone(exc, err)

    def test_case_only_differences_name_both_spellings(self):
        self._import_example()
        cases = [
            ('reference', 'smith-2020', "the stored reference_id 'Smith-2020'"),
            ('facility', 'example_lab', "'Example_Lab' (the stored label)"),
            ('specimen', 'w1', "'W1' (the stored label)"),
        ]
        for column, value, fragment in cases:
            with self.subTest(column=column):
                path = self._csv({column: value, 'observation': 'obs03'})
                self._assert_fails(
                    path,
                    f"Row 2, column '{column}': '{value}' differs only in case "
                    f'from {fragment}',
                )

    # -- programs -------------------------------------------------------------

    def test_program_rules(self):
        references = self._read('reference.json') + [JONES]
        self._write('reference.json', references)
        self._write(
            'program.json',
            [
                {
                    'label': 'Jones_A',
                    'name': '',
                    'notes': '',
                    'reference': 'Jones-2021',
                }
            ],
        )
        cases = [
            (
                {'reference': 'Nope-1999'},
                (
                    "Row 2, column 'reference': 'Nope-1999' is not an existing "
                    'reference_id'
                ),
            ),
            (
                {'program': 'Jones_A'},
                (
                    "Row 2, column 'reference': 'Smith-2020' differs from "
                    "'Jones-2021', the reference of existing program 'Jones_A'"
                ),
            ),
            (
                {'reference': 'Jones-2021'},
                (
                    "Row 2, column 'program': blank, but reference 'Jones-2021' has "
                    "only labelled programs ('Jones_A')"
                ),
            ),
        ]
        for overrides, fragment in cases:
            with self.subTest(overrides=overrides):
                self._assert_fails(self._csv(overrides), fragment)

    def test_blank_program_beside_a_new_labelled_one_fails(self):
        # Batched or split, the same rows must not make a second program.
        self._assert_fails(
            self._csv({}, {'program': 'Walls_B'}),
            "Row 2, column 'program': blank, but other rows give reference "
            "'Smith-2020' a labelled program",
        )

    def test_new_labelled_program_is_written(self):
        _, err, exc = self._import(self._csv({'program': 'Smith_Walls'}))
        self.assertIsNone(exc, err)
        self.assertEqual(
            self._read('program.json'),
            [
                {
                    'label': 'Smith_Walls',
                    'name': '',
                    'notes': '',
                    'reference': 'Smith-2020',
                }
            ],
        )
        self.assertEqual(self._read('specimen.json')[0]['program'], 'Smith_Walls')

    # -- new records ------------------------------------------------------------

    def test_every_disagreement_in_a_new_parent_names_row_column_and_values(self):
        path = self._csv(
            {'observation': 'obs01'},
            {
                'observation': 'obs02',
                'facility_location': 'Other City',
                'material': 'Wood studs',
                'loading_protocol': 'CUREE',
            },
        )
        err = self._assert_fails(
            path,
            "Row 3, column 'facility_location': 'Other City' disagrees with "
            "'Example City, CA' (row 2) for new facility 'Example_Lab'",
            "Row 3, column 'material': 'Wood studs' disagrees with 'Steel studs, "
            "gypsum board' (row 2) for new specimen 'Smith-2020|W1'",
            "Row 3, column 'loading_protocol': 'CUREE' disagrees with 'FEMA 461 "
            "interstory drift protocol' (row 2) for new test 'Smith-2020|W1|1'",
        )
        self.assertIn('Found 3 error(s)', err)

    def test_blank_cell_disagrees_for_a_new_parent(self):
        path = self._csv(
            {'observation': 'obs01'}, {'observation': 'obs02', 'size_class': ''}
        )
        self._assert_fails(
            path,
            "Row 3, column 'size_class': '' disagrees with 'Full scale' (row 2)",
        )

    def test_case_variants_of_a_new_label_fail(self):
        path = self._csv(
            {'specimen': 'W9', 'observation': 'obs01'},
            {'specimen': 'w9', 'observation': 'obs02'},
        )
        self._assert_fails(
            path,
            "Row 3, column 'specimen': 'w9' differs only in case from 'W9' (row 2)",
        )

    def test_identical_tests_with_different_labels_are_two_tests(self):
        path = self._csv(
            {'test': 'a', 'test_order': '', 'observation': 'obs01'},
            {'test': 'b', 'test_order': '', 'observation': 'obs01'},
        )
        _, err, exc = self._import(path)
        self.assertIsNone(exc, err)
        tests = self._read('test.json')
        self.assertEqual([t['label'] for t in tests], ['a', 'b'])
        self.assertEqual([t['test_order'] for t in tests], [None, None])
        self.assertEqual(
            [o['test'] for o in self._read('observation.json')],
            ['Smith-2020|W1|a', 'Smith-2020|W1|b'],
        )

    def test_duplicate_observation_in_the_csv_fails(self):
        path = self._csv({'observation': 'obs01'}, {'observation': 'OBS01'})
        self._assert_fails(
            path,
            "Row 3, column 'observation': 'OBS01' repeats 'obs01' (row 2) in test "
            "'Smith-2020|W1|1'",
        )

    # -- labels and test order ------------------------------------------------

    def test_invalid_labels_are_rejected_with_a_suggested_slug(self):
        cases = [
            ('facility', 'Example Lab', 'Example_Lab'),
            ('program', 'Smith walls', 'Smith_walls'),
            ('specimen', 'Wall #2', 'Wall_2'),
            ('test', 'Test 3a', 'Test_3a'),
            ('observation', '01 crack', '01_crack'),
        ]
        for column, value, suggestion in cases:
            with self.subTest(column=column):
                err = self._assert_fails(
                    self._csv({column: value}),
                    f'Row 2, column \'{column}\': label "{value}" must be 1-100',
                    f"Suggested label: '{suggestion}'.",
                )
                self.assertIn('Found 1 error(s)', err)

    def test_mixed_width_observation_labels_warn(self):
        path = self._csv(
            *(
                {'test': 'a', 'test_order': '', 'observation': label}
                for label in ('1', '2', '10')
            )
        )
        out, err, exc = self._import(path)
        self.assertIsNone(exc, err)
        self.assertIn(
            "Warning: test 'Smith-2020|W1|a' has observation labels whose numbers "
            'differ in width (1, 2 digits)',
            out,
        )

    def test_mixed_width_warning_includes_existing_labels(self):
        self._import_example()
        out, _, _ = self._import(self._csv({'observation': 'obs03'}))
        self.assertNotIn('differ in width', out)
        out, err, exc = self._import(self._csv({'observation': 'obs4'}))
        self.assertIsNone(exc, err)
        self.assertIn("test 'Smith-2020|W1|1' has observation labels", out)

    def test_test_order_rules(self):
        self._import_example()
        cases = [
            ({'test': '3a', 'test_order': '3a'}, "'3a' is not a whole number"),
            ({'test': '9', 'test_order': '0'}, "'0' must be at least 1"),
            (
                {'test': '9', 'test_order': '2'},
                (
                    "Row 2, column 'test_order': 2 is already the order of test '2' "
                    "(stored) in specimen 'Smith-2020|W1'"
                ),
            ),
        ]
        for overrides, fragment in cases:
            with self.subTest(overrides=overrides):
                self._assert_fails(self._csv(overrides), fragment)

    def test_two_new_tests_cannot_share_an_order(self):
        path = self._csv(
            {'test': 'a', 'test_order': '7'},
            {'test': 'b', 'test_order': '07'},
        )
        self._assert_fails(
            path,
            "Row 3, column 'test_order': 7 is already the order of test 'a' "
            "(row 2) in specimen 'Smith-2020|W1'",
        )

    # -- the CSV itself ---------------------------------------------------------

    def test_blank_identity_cells_are_errors(self):
        err = self._assert_fails(
            self._csv({'specimen': '', 'observation': ''}),
            "Row 2, column 'specimen': required, but blank",
            "Row 2, column 'observation': required, but blank",
        )
        self.assertIn('Found 2 error(s)', err)

    def test_missing_identity_column_is_an_error(self):
        path = os.path.join(self.temp_dir, 'short.csv')
        with open(path, 'w', encoding='utf-8') as f:
            f.write('reference,facility,specimen,observation\nSmith-2020,L,S,o\n')
        _, _, exc = self._import(path)
        self.assertIn('Missing required column(s): test', str(exc))

    def test_records_with_a_comment_key_are_read(self):
        # The example reference.json carries a _comment, as ingest allows.
        self.assertIn('_comment', self._read('reference.json')[0])
        self._import_example()
        self.assertEqual(self._read('program.json')[0]['reference'], 'Smith-2020')


class ImportObservationRoundTripTests(ImportObservationTestMixin, TestCase):
    """The importer writes exactly what ingest reads and export_data writes."""

    def test_example_import_ingests_and_exports_unchanged(self):
        self._import_example()
        call_command(
            'ingest', data_dir=self.data_dir, stdout=StringIO(), stderr=StringIO()
        )
        export_dir = os.path.join(self.temp_dir, 'export')
        call_command('export_data', output_dir=export_dir, stdout=StringIO())
        for name in HIERARCHY_FILES:
            with self.subTest(name=name):
                self.assertEqual(
                    _read_text(os.path.join(export_dir, name)),
                    _read_text(self._path(name)),
                )


class ImportObservationDryRunTests(ImportObservationTestMixin, SimpleTestCase):
    """--dry_run: a real migrate and ingest in a subprocess, on a tiny data set."""

    def setUp(self):
        super().setUp()
        for name in HIERARCHY_FILES + ['observation_fragility_model_bridge.json']:
            self._write(name, [])

    def test_clean_import_passes_and_writes_nothing(self):
        before = self._snapshot()
        out, err, exc = self._import(EXAMPLE_CSV, dry_run=True)
        self.assertIsNone(exc, out + err)
        self.assertIn('Specimen processing complete: 1 created', out)
        self.assertIn('ingest and the JSON guards accept the import', out)
        self.assertEqual(self._snapshot(), before)

    def test_reports_what_ingest_and_the_guards_reject(self):
        # An exact duplicate key: the one failure ingest accepts silently.
        lab = {'label': 'Lab', 'name': '', 'location': '', 'notes': ''}
        self._write('facility.json', [lab, lab])
        before = self._snapshot()
        path = self._csv(
            {'specimen': 'W1', 'test_type': 'Bogus'},
            {'specimen': 'W2', 'component': 'B.99.9.9'},
        )
        out, err, exc = self._import(path, dry_run=True)
        self.assertIsNotNone(exc, out + err)
        self.assertIn('"Bogus" is not a valid choice', err)
        self.assertIn('component_id=B.99.9.9 does not exist', err)
        self.assertIn('facility.json: Lab: duplicates Lab', err)
        self.assertEqual(self._snapshot(), before)
