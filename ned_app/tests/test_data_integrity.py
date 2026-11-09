import json
import os
import tempfile
from typing import ClassVar
from unittest.mock import patch

from django.apps import apps
from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.test import SimpleTestCase, TransactionTestCase, tag

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
    derive_reference_id,
)
from ned_app.validators import validate_label

# How each hierarchy file's derived id is rebuilt from a record, as ingest
# derives it for its lookup.
DERIVE_ID = {
    'facility': lambda r: r['label'],
    'program': lambda r: r.get('label') or r['reference'],
    'specimen': lambda r: f'{r["program"]}|{r["label"]}',
    'test': lambda r: f'{r["specimen"]}|{r["label"]}',
    'observation': lambda r: f'{r["test"]}|{r["label"]}',
}


def derived_id_problems(records, derive):
    """
    Check that every record's derived id can be derived and is unique.

    Uniqueness ignores case, as the Lower(...) constraints do.

    Args:
        records (list[dict]): Records from one JSON file.
        derive (callable): Builds a record's derived id.

    Returns:
        list[str]: One line per problem; empty when the records are clean.
    """
    seen = {}
    problems = []
    for index, record in enumerate(records):
        try:
            derived = derive(record)
        except (KeyError, TypeError) as exc:
            problems.append(f'record {index}: id cannot be derived ({exc!r})')
            continue
        if derived.lower() in seen:
            problems.append(
                f'{derived}: duplicates {seen[derived.lower()]} (ignoring case)'
            )
        else:
            seen[derived.lower()] = derived
    return problems


def label_problems(records, allow_blank=False):
    """
    Check that every label passes validate_label.

    Args:
        records (list[dict]): Records from one JSON file.
        allow_blank (bool): Skip blank labels (a program's label is optional).

    Returns:
        list[str]: One line per problem; empty when the records are clean.
    """
    problems = []
    for index, record in enumerate(records):
        label = record.get('label', '')
        if allow_blank and not label:
            continue
        try:
            validate_label(label)
        except ValidationError as exc:
            problems.append(f'record {index}: label {label!r}: {exc.messages[0]}')
    return problems


def parent_problems(records, field, parent_ids, nullable=False):
    """
    Check that every record's parent string matches a parent id exactly.

    Foreign-key lookups are exact, so a parent that differs only in case does
    not resolve, even though uniqueness ignores case.

    Args:
        records (list[dict]): Records from one JSON file.
        field (str): The foreign-key key in each record.
        parent_ids (set[str]): Every id in the parent file.
        nullable (bool): Allow a null parent (an optional foreign key).

    Returns:
        list[str]: One line per problem; empty when the records are clean.
    """
    problems = []
    for index, record in enumerate(records):
        value = record.get(field)
        if value is None and nullable:
            continue
        if value not in parent_ids:
            problems.append(f'record {index}: {field} {value!r} does not resolve')
    return problems


def derivable_ids(records, derive):
    """
    Return the ids derivable from the records, skipping any that can't be.

    Args:
        records (list[dict]): Records from one JSON file.
        derive (callable): Builds a record's derived id.

    Returns:
        set[str]: The derived ids.
    """
    ids = set()
    for record in records:
        try:
            ids.add(derive(record))
        except (KeyError, TypeError):
            continue
    return ids


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

    reference_id is derived at ingest, not stored. These checks make the two
    failure modes of that scheme legible at test time.
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

    def test_derived_reference_ids_are_derivable_and_unique(self):
        # The importer appends references without deriving/deduping, so this is
        # the first place a bad id shows up. Two references deriving the same id
        # would silently merge on ingest; a record whose csl_data can't be keyed
        # would fail ingest cryptically. Catch both here with a clean message,
        # not a raw KeyError.
        seen = {}
        problems = []
        for ref in self._load_references():
            title = ref.get('csl_data', {}).get('title', '<no title>')
            try:
                derived = derive_reference_id(
                    ref.get('reference_label', '') or '', ref['csl_data']
                )
            except (KeyError, IndexError, TypeError) as exc:
                problems.append(
                    f'{title!r}: reference_id cannot be derived ({exc!r})'
                )
                continue
            if derived in seen:
                problems.append(f'{derived}: {seen[derived]!r} vs {title!r}')
            else:
                seen[derived] = title
        self.assertEqual(
            problems,
            [],
            'reference.json has references whose derived id is missing or '
            'duplicated (add a reference_label / fix csl_data):\n'
            + '\n'.join(problems),
        )


class CanonicalHierarchyDataTests(SimpleTestCase):
    """
    Guards on the canonical facility, program, specimen, test and observation
    files, and the observation bridge.

    Derived ids are rebuilt at ingest and every child file stores its parent's
    derived id, so these checks catch an id that can't be built, a case-only
    duplicate and a dangling parent before ingest does. The guards themselves
    are unit-tested in HierarchyGuardTests, since the files may be empty.
    """

    DATA_DIR = 'resources/data'

    def _load(self, name):
        path = os.path.join(self.DATA_DIR, f'{name}.json')
        with open(path, 'r', encoding='utf-8') as f:
            return [r for r in json.load(f) if '_comment' not in r]

    def setUp(self):
        self.records = {
            name: self._load(name)
            for name in (
                'reference',
                'component',
                'facility',
                'program',
                'specimen',
                'test',
                'observation',
                'observation_fragility_model_bridge',
            )
        }
        self.ids = {
            name: derivable_ids(self.records[name], derive)
            for name, derive in DERIVE_ID.items()
        }
        self.ids['reference'] = derivable_ids(
            self.records['reference'],
            lambda r: derive_reference_id(
                r.get('reference_label', '') or '', r['csl_data']
            ),
        )
        self.ids['component'] = {
            r['component_id'] for r in self.records['component']
        }

    def test_derived_ids_are_derivable_and_unique(self):
        for name, derive in DERIVE_ID.items():
            with self.subTest(file=f'{name}.json'):
                self.assertEqual(derived_id_problems(self.records[name], derive), [])

    def test_labels_are_valid(self):
        # Specimen, test and observation labels are required; a program's
        # label is optional (blank on every converted program).
        for name in ('facility', 'specimen', 'test', 'observation'):
            with self.subTest(file=f'{name}.json'):
                self.assertEqual(label_problems(self.records[name]), [])
        with self.subTest(file='program.json'):
            self.assertEqual(
                label_problems(self.records['program'], allow_blank=True), []
            )

    def test_parents_resolve_with_exact_case(self):
        # (file, foreign-key key, parent file, nullable)
        checks = [
            ('program', 'reference', 'reference', False),
            ('specimen', 'program', 'program', False),
            ('specimen', 'facility', 'facility', False),
            ('specimen', 'reference', 'reference', True),
            ('specimen', 'component', 'component', False),
            ('test', 'specimen', 'specimen', False),
            ('observation', 'test', 'test', False),
            # Ingest's lookups are case-sensitive, so a bridge row must match
            # an observation_id exactly.
            (
                'observation_fragility_model_bridge',
                'observation',
                'observation',
                False,
            ),
        ]
        for name, field, parent, nullable in checks:
            with self.subTest(file=f'{name}.json', field=field):
                self.assertEqual(
                    parent_problems(
                        self.records[name], field, self.ids[parent], nullable
                    ),
                    [],
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


class ArchiveSnapshotTests(SimpleTestCase):
    """
    Guards the frozen pre-split snapshot (resources/archive/, Stage 8).

    The reconstruction audit and the record-count acceptance checks compare
    against this file, so losing, emptying or replacing it would make them
    compare against the wrong baseline.
    """

    SNAPSHOT_JSON = 'resources/archive/observation_pre_split.json'
    # Observation rows in resources/data/observation.json when it was frozen.
    EXPECTED_RECORDS = 2409

    def test_snapshot_exists_with_the_frozen_record_count(self):
        with open(self.SNAPSHOT_JSON, 'r', encoding='utf-8') as f:
            records = json.load(f)
        self.assertEqual(len(records), self.EXPECTED_RECORDS)
        # Every record keeps its pre-split id, which the audit matches on.
        ids = [r['id'] for r in records]
        self.assertEqual(len(set(ids)), len(ids))


class ObservationIdMapTests(SimpleTestCase):
    """
    Guards the old id -> observation_id map (resources/archive/, Stage 10).

    The audit and the Streamlit baseline comparison match pre-split records
    to current ones through it.
    """

    ID_MAP_JSON = 'resources/archive/observation_id_map.json'
    SNAPSHOT_JSON = 'resources/archive/observation_pre_split.json'
    OBSERVATION_JSON = 'resources/data/observation.json'

    def _load(self, path):
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)

    def test_one_entry_per_archived_observation(self):
        id_map = self._load(self.ID_MAP_JSON)
        snapshot_ids = {r['id'] for r in self._load(self.SNAPSHOT_JSON)}
        self.assertEqual(set(id_map), snapshot_ids)

    def test_values_are_unique_current_observation_ids(self):
        # A subset, not equality, so observations added later don't break it.
        # Exact case: the ids are matched as stored.
        values = list(self._load(self.ID_MAP_JSON).values())
        self.assertEqual(len(set(values)), len(values))
        current = derivable_ids(
            self._load(self.OBSERVATION_JSON), DERIVE_ID['observation']
        )
        self.assertEqual(sorted(set(values) - current), [])
