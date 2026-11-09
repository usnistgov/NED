import json
import os
import tempfile
from typing import ClassVar
from unittest.mock import patch

from django.apps import apps
from django.core.management import call_command
from django.db import connection
from django.test import SimpleTestCase, TestCase, TransactionTestCase, tag

from ned_app.json_guards import (
    DERIVE_ID,
    check_data_dir,
    derived_id_problems,
    label_problems,
    parent_problems,
)
from ned_app.models import (
    Component,
    ComponentFragilityModelBridge,
    Facility,
    FragilityCurve,
    FragilityModel,
    Observation,
    ObservationFragilityModelBridge,
    Program,
    Reference,
    Specimen,
    Test,
)


@tag('integrity')
class DataIntegrityTests(TransactionTestCase):
    fixtures: ClassVar[list[str]] = ['initial_data.json']
    # The round trip keys rows by pk, and flush resets the sequences before
    # ingest recreates the rows. Start from reset sequences too, so the rows
    # seeded here get the same pks as their re-ingested copies.
    reset_sequences = True

    def setUp(self):
        self.temp_dir_path = tempfile.mkdtemp()

    # Every model in the app, in ingest order. test_db_round_trip asserts this
    # list is complete, so a new model can't be left out of the round trip.
    ROUND_TRIP_MODELS: ClassVar[list] = [
        Reference,
        Component,
        Facility,
        Program,
        Specimen,
        Test,
        FragilityModel,
        ComponentFragilityModelBridge,
        Observation,
        ObservationFragilityModelBridge,
        FragilityCurve,
    ]

    def _seed_hierarchy(self):
        """
        Seed synthetic Facility/Program/Specimen/Test rows and link an observation.

        The converted data never has a labelled program or a specimen with its
        own reference, so these rows cover those cases. They use references
        with no program yet, so the unlabelled program doesn't clash.
        """
        reference, other_reference = Reference.objects.filter(
            program__isnull=True
        ).order_by('pk')[:2]
        component = Component.objects.order_by('pk').first()
        facility = Facility.objects.create(
            label='Synthetic_Lab', name='Synthetic Lab', location='Nowhere'
        )
        unlabelled_program = Program.objects.create(reference=reference)
        labelled_program = Program.objects.create(
            label='Synthetic_Program', name='A program', reference=reference
        )
        specimen = Specimen.objects.create(
            program=unlabelled_program,
            facility=facility,
            label='S1',
            component=component,
            comp_description='Synthetic specimen',
        )
        Specimen.objects.create(
            program=labelled_program,
            facility=facility,
            reference=other_reference,
            label='S2',
            component=component,
            comp_description='Synthetic specimen with its own reference',
        )
        ordered_test = Test.objects.create(
            specimen=specimen,
            label='T1',
            test_order=1,
            test_type='Dynamic, uniaxial',
        )
        Test.objects.create(
            specimen=specimen,
            label='T2',
            test_type='Dynamic, uniaxial',
        )
        # Relabelling re-derives the observation_id, so pick an observation
        # with no bridge rows; otherwise they would be left dangling.
        observation = (
            Observation.objects
            .exclude(observationfragilitymodelbridge__isnull=False)
            .order_by('pk')
            .first()
        )
        observation.test = ordered_test
        observation.label = '01'
        observation.damage_location = 'Base'
        observation.save()

    def test_db_round_trip(self):
        self.assertCountEqual(
            self.ROUND_TRIP_MODELS, apps.get_app_config('ned_app').get_models()
        )

        self._seed_hierarchy()

        initial_rows = {}
        for model in self.ROUND_TRIP_MODELS:
            initial_rows[model] = list(model.objects.all())
            self.assertTrue(
                initial_rows[model], f'{model.__name__} has no rows to round-trip'
            )

        call_command('export_data', output_dir=self.temp_dir_path)

        call_command('flush', '--noinput')

        def mock_build_json_data_file_path(filename):
            return os.path.join(self.temp_dir_path, filename)

        with patch(
            'ned_app.management.commands.ingest.build_json_data_file_path',
            side_effect=mock_build_json_data_file_path,
        ):
            call_command('ingest')

        def field_values(row):
            return {k: v for k, v in row.__dict__.items() if k != '_state'}

        # Keyed by .pk, which works for string and integer keys alike.
        for model in self.ROUND_TRIP_MODELS:
            final_rows = {row.pk: row for row in model.objects.all()}
            self.assertEqual(
                len(initial_rows[model]), len(final_rows), model.__name__
            )
            for initial_row in initial_rows[model]:
                self.assertEqual(
                    field_values(initial_row),
                    field_values(final_rows[initial_row.pk]),
                )

        # A second ingest must find every row by its lookup (derived ids
        # included) and create nothing.
        counts = {model: model.objects.count() for model in self.ROUND_TRIP_MODELS}
        with patch(
            'ned_app.management.commands.ingest.build_json_data_file_path',
            side_effect=mock_build_json_data_file_path,
        ):
            call_command('ingest')
        self.assertEqual(
            counts,
            {model: model.objects.count() for model in self.ROUND_TRIP_MODELS},
        )

    def test_json_to_db_to_json_round_trip_is_lossless(self):
        temp_export_dir = tempfile.mkdtemp()

        try:
            call_command('ingest')

            call_command('export_data', output_dir=temp_export_dir)

            canonical_data_dir = 'resources/data'

            # Map each JSON file to its sort key function
            # For tables with composite keys, use tuple sorting
            json_files = {
                'reference.json': lambda x: x['csl_data']['title'],
                'component.json': lambda x: x['component_id'],
                'fragility_model.json': lambda x: (
                    x['reference'],
                    x['model_id'],
                ),
                'observation.json': lambda x: (x['test'], x['label'].lower()),
                'component_fragility_model_bridge.json': lambda x: (
                    x['component'],
                    x['fragility_model'],
                ),
                'observation_fragility_model_bridge.json': lambda x: (
                    x['observation'],
                    x['fragility_model'],
                ),
                'fragility_curve.json': lambda x: (
                    x['fragility_model'],
                    x['ds_rank'],
                ),
                'facility.json': lambda x: x['label'].lower(),
                'program.json': lambda x: (x['reference'], x['label']),
                'specimen.json': lambda x: (x['program'], x['label'].lower()),
                'test.json': lambda x: (x['specimen'], x['label'].lower()),
            }

            for json_file, sort_func in json_files.items():
                canonical_path = os.path.join(canonical_data_dir, json_file)
                with open(canonical_path, 'r') as f:
                    canonical_data = json.load(f)

                exported_path = os.path.join(temp_export_dir, json_file)
                with open(exported_path, 'r') as f:
                    exported_data = json.load(f)

                # Sort both datasets by their key(s) to ensure order-independent comparison
                canonical_data_sorted = sorted(canonical_data, key=sort_func)
                exported_data_sorted = sorted(exported_data, key=sort_func)

                self.assertEqual(
                    canonical_data_sorted,
                    exported_data_sorted,
                    f'Mismatch in {json_file}: canonical and exported data differ',
                )

        finally:
            import shutil

            shutil.rmtree(temp_export_dir)


class CanonicalReferenceDataTests(SimpleTestCase):
    """
    Guards on the canonical reference.json source data (no DB needed).

    reference_id is derived at ingest, not stored; the derived ids themselves
    are checked by CanonicalHierarchyDataTests.
    """

    REFERENCE_JSON = 'resources/data/reference.json'

    def _load_references(self):
        with open(self.REFERENCE_JSON, 'r', encoding='utf-8') as f:
            return [r for r in json.load(f) if '_comment' not in r]

    def test_no_stored_reference_id_or_csl_id(self):
        # The id is derived (reference_id) or stripped (csl_data 'id') at ingest,
        # so neither may be committed to the source data.
        offenders = []
        for ref in self._load_references():
            title = ref.get('csl_data', {}).get('title', '<no title>')
            if 'reference_id' in ref:
                offenders.append(f'stored reference_id in {title!r}')
            if 'id' in ref.get('csl_data', {}):
                offenders.append(f"csl_data 'id' in {title!r}")
        self.assertEqual(
            offenders,
            [],
            'reference.json must not store a reference_id or a csl_data id:\n'
            + '\n'.join(offenders),
        )


class CanonicalHierarchyDataTests(SimpleTestCase):
    """
    Runs the JSON guards (ned_app.json_guards) on the canonical data.

    Derived ids are rebuilt at ingest and every child file stores its parent's
    derived id, so the guards catch an id that can't be built, a case-only
    duplicate and a dangling parent before ingest does. Two references deriving
    the same id would otherwise merge silently on ingest. The guards themselves
    are unit-tested in HierarchyGuardTests.
    """

    def test_canonical_data_passes_the_json_guards(self):
        problems = check_data_dir('resources/data')
        self.assertEqual(
            problems,
            [],
            'resources/data/ fails the JSON guards (fix the data, or add a '
            'reference_label for a duplicate reference id):\n' + '\n'.join(problems),
        )


class HierarchyGuardTests(SimpleTestCase):
    """Unit tests for the hierarchy guard helpers, on small bad inputs."""

    def test_clean_records_pass(self):
        programs = [
            {'label': '', 'reference': 'Smith-2020'},
            {'label': 'P1', 'reference': 'Smith-2020'},
        ]
        self.assertEqual(derived_id_problems(programs, DERIVE_ID['program']), [])
        self.assertEqual(label_problems(programs, allow_blank=True), [])
        self.assertEqual(parent_problems(programs, 'reference', {'Smith-2020'}), [])

    def test_case_only_duplicate_id_is_reported(self):
        specimens = [
            {'program': 'P1', 'label': 'S6'},
            {'program': 'P1', 'label': 's6'},
        ]
        problems = derived_id_problems(specimens, DERIVE_ID['specimen'])
        self.assertEqual(len(problems), 1)
        self.assertIn('P1|s6', problems[0])

    def test_underivable_id_is_reported(self):
        tests = [{'label': 'T1'}]
        problems = derived_id_problems(tests, DERIVE_ID['test'])
        self.assertEqual(len(problems), 1)
        self.assertIn('cannot be derived', problems[0])

    def test_bad_label_is_reported(self):
        tests = [{'specimen': 'P1|S1', 'label': 'T 1'}]
        self.assertEqual(len(label_problems(tests)), 1)

    def test_blank_label_is_reported_unless_allowed(self):
        records = [{'label': ''}]
        self.assertEqual(len(label_problems(records)), 1)
        self.assertEqual(label_problems(records, allow_blank=True), [])

    def test_wrong_case_parent_is_reported(self):
        tests = [{'specimen': 'P1|s1', 'label': 'T1'}]
        problems = parent_problems(tests, 'specimen', {'P1|S1'})
        self.assertEqual(len(problems), 1)
        self.assertIn("'P1|s1'", problems[0])

    def test_unresolved_observation_test_is_reported(self):
        observations = [
            {'test': 'P1|S1|T1', 'label': '01'},
            {'test': 'P1|S1|T9', 'label': '01'},
        ]
        problems = parent_problems(observations, 'test', {'P1|S1|T1'})
        self.assertEqual(problems, ["record 1: test 'P1|S1|T9' does not resolve"])

    def test_case_only_duplicate_observation_id_is_reported(self):
        observations = [
            {'test': 'P1|S1|T1', 'label': 'a01'},
            {'test': 'P1|S1|T1', 'label': 'A01'},
        ]
        problems = derived_id_problems(observations, DERIVE_ID['observation'])
        self.assertEqual(len(problems), 1)
        self.assertIn('P1|S1|T1|A01', problems[0])

    def test_null_parent_is_reported_unless_nullable(self):
        specimens = [{'program': 'P1', 'label': 'S1', 'reference': None}]
        self.assertEqual(len(parent_problems(specimens, 'reference', set())), 1)
        self.assertEqual(
            parent_problems(specimens, 'reference', set(), nullable=True), []
        )

    def test_check_data_dir_names_the_file(self):
        files = {
            'reference.json': [
                {
                    'csl_data': {
                        'author': [{'family': 'Smith'}],
                        'issued': {'date-parts': [[2020]]},
                    }
                }
            ],
            'component.json': [{'component_id': 'A.10.1.1'}],
            'facility.json': [{'label': 'Lab'}],
            'program.json': [{'label': '', 'reference': 'Smith-2020'}],
            'specimen.json': [
                {
                    'program': 'Smith-2020',
                    'facility': 'Lab',
                    'reference': None,
                    'component': 'A.10.1.1',
                    'label': 'S1',
                }
            ],
            'test.json': [{'specimen': 'smith-2020|S1', 'label': 'T1'}],
            'observation.json': [],
            'observation_fragility_model_bridge.json': [],
        }
        with tempfile.TemporaryDirectory() as data_dir:
            for name, records in files.items():
                with open(os.path.join(data_dir, name), 'w') as f:
                    json.dump(records, f)
            self.assertEqual(
                check_data_dir(data_dir),
                ["test.json: record 0: specimen 'smith-2020|S1' does not resolve"],
            )


class CanonicalJsonFormatTests(SimpleTestCase):
    """
    Guards that resources/data/ is byte-identical to what export_data writes.

    The round-trip tests above compare parsed JSON, so they are blind to key
    order and formatting: a hand-edit that renames a key in place still passes
    them, while leaving the file out of canonical order. The drift then surfaces
    as a large unexplained diff for whoever next runs export_data. This compares
    the bytes instead, and needs no database.
    """

    DATA_DIR = 'resources/data'

    # Mirrors the json.dump call in every export_* method of the export_data
    # command; keep the two in step.
    INDENT = 4
    SORT_KEYS = True

    def test_source_data_is_in_canonical_export_format(self):
        offenders = []
        for filename in sorted(os.listdir(self.DATA_DIR)):
            if not filename.endswith('.json'):
                continue
            path = os.path.join(self.DATA_DIR, filename)
            with open(path, 'r', encoding='utf-8') as f:
                raw = f.read()
            canonical = json.dumps(
                json.loads(raw), indent=self.INDENT, sort_keys=self.SORT_KEYS
            )
            if raw != canonical:
                offenders.append(filename)
        self.assertEqual(
            offenders,
            [],
            'These files are not in canonical export format (most often a key '
            'renamed in place rather than through the schema):\n'
            + '\n'.join(offenders)
            + '\n\nRegenerate them from the database instead of editing by '
            'hand:\n    python manage.py export_data --output_dir '
            'resources/data/',
        )


class NoStoredViewTests(TestCase):
    """A stored view would break the migrations that drop the columns it reads."""

    def test_migrated_database_stores_no_view(self):
        with connection.cursor() as cursor:
            cursor.execute("SELECT name FROM sqlite_master WHERE type = 'view'")
            self.assertEqual(cursor.fetchall(), [])
